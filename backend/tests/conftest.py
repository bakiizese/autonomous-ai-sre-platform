import os
import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _use_isolated_test_database() -> None:
    """Point the whole app at `<db>_test` before anything binds an engine.

    The tests assume empty tables, so they must not share a database with a
    running dev stack (docker compose seeds real repos and subscribers into it).
    TEST_DATABASE_URL wins if set; otherwise the name is derived from
    DATABASE_URL and the database is created on first use. This has to run
    before app.db.session is imported, which is why it sits above the other
    app imports."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    original = make_url(settings.DATABASE_URL)
    target = make_url(explicit) if explicit else original.set(database=f"{original.database}_test")

    if target.database != original.database:
        admin = create_engine(original, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target.database}"'))
        admin.dispose()

    settings.DATABASE_URL = target.render_as_string(hide_password=False)


_use_isolated_test_database()

from app.db.base import Base  # noqa: E402
from app.schemas.agent import (  # noqa: E402
    DiagnosisOutput,
    PipelineResult,
    RemediationOutput,
    TestGenerationOutput,
    VerificationResult,
)

# ============================================================================
# 1. GLOBAL ENVIRONMENT & SETTINGS FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """The limiter keeps per-IP counters in process memory; without this the
    TestClient (always the same 'IP') would trip limits across unrelated tests."""
    from app.api import limits

    limits.reset()
    yield
    limits.reset()


@pytest.fixture(autouse=True)
def mock_env_vars():
    """
    Automatically mock essential environment variables for ALL tests
    to prevent real API keys/credentials from leaking or being needed.
    """
    env_vars = {
        "GEMINI_API_KEY": "fake-gemini-key",
        "GITHUB_TOKEN": "fake-github-token",
        "GITHUB_REPO": "owner/test-repo",
        "SMTP_HOST": "smtp.fake.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "alerts@fake.com",
        "SMTP_PASSWORD": "fake-password",
        "ALERT_EMAIL_FROM": "sentinel@fake.com",
        "ALERT_EMAIL_TO": "sre-team@fake.com",
    }
    with patch.dict(os.environ, env_vars):
        yield


# ============================================================================
# 2. SHARED INPUT DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_error_log() -> str:
    """Standardized error log for pipeline and parser tests."""
    return (
        "Traceback (most recent call last):\n"
        '  File "app/services/data.py", line 18, in process_data\n'
        "    for item in data:\n"
        "TypeError: 'NoneType' object is not iterable"
    )


@pytest.fixture
def sample_source_code() -> str:
    """Standardized Python context for pipeline tests."""
    return "def process_data(data):\n    for item in data:\n        print(item)\n"


@pytest.fixture
def sample_issue_body() -> str:
    """Markdown GitHub issue body for issue extractor tests."""
    return """
    ### Bug Report: Unhandled TypeError in `app/services/data.py`

    When running `process_data()`, an unhandled NoneType exception occurs.
    Please review `app/services/data.py` and call `validate_input(data)` first.
    """


# ============================================================================
# 3. PYDANTIC SCHEMA MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_pipeline_result() -> PipelineResult:
    """Provides a valid PipelineResult instance."""
    return PipelineResult(
        diagnosis=DiagnosisOutput(
            summary="Unhandled TypeError when iterating a None payload.",
            root_cause_analysis="TypeError due to unvalidated None payload in process_data()",
            affected_files=["app/services/data.py"],
            risk_score=8,
        ),
        remediation=RemediationOutput(
            patch_explanation="Guard against a None/empty payload before iterating.",
            target_file="app/services/data.py",
            code_fix="def process_data(data):\n    if not data:\n        return\n    for item in data:\n        print(item)",
            git_diff_patch="--- a/app/services/data.py\n+++ b/app/services/data.py\n@@ -1,2 +1,4 @@",
        ),
        test_generation=TestGenerationOutput(
            test_file_name="test_process_data.py",
            test_code="def test_process_data_none():\n    from app.services.data import process_data\n    process_data(None)",
            test_description="Verifies process_data no longer raises on a None payload.",
        ),
    )


@pytest.fixture
def mock_verification_result_passed() -> VerificationResult:
    """Provides a passing VerificationResult object."""
    return VerificationResult(
        passed=True,
        target_test_passed=True,
        stdout="1 passed in 0.02s",
        stderr="",
    )


# ============================================================================
# 4. EXTERNAL CLIENT & MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_genai_client():
    """Mocks the google.genai Client response."""
    with patch("app.services.agent_engine.client") as mock_client:
        mock_response = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        yield mock_client


# ============================================================================
# 5. DATABASE FIXTURES
# ============================================================================
# Uses settings.DATABASE_URL directly (the docker-compose postgres for local
# dev, a dedicated service container in CI). Each test runs inside its own
# transaction that's rolled back afterward, so tests never see each other's
# data and don't need to clean up manually.


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(settings.DATABASE_URL)
    import app.db.models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
