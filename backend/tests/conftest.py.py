import os
import pytest
from unittest.mock import patch, MagicMock

from app.schemas.agent import (
    DiagnosisOutput,
    PipelineResult,
    RemediationOutput,
    TestGenerationOutput,
    VerificationResult,
)

DiagnosisOutput(
    summary="Null pointer exception in data processing pipeline.",
    root_cause_analysis="Null Pointer Exception in process_data when data argument is None.",
    affected_files=["app/services/data.py"],
    root_cause="Null Pointer Exception in process_data",  # include if still present on schema
    risk_score=7,
)

# ============================================================================
# 1. GLOBAL ENVIRONMENT & SETTINGS FIXTURES
# ============================================================================


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
            root_cause="TypeError due to unvalidated None payload in process_data()",
            risk_score=8,
        ),
        remediation=RemediationOutput(
            code_fix="def process_data(data):\n    if not data:\n        return\n    for item in data:\n        print(item)",
            git_diff="--- a/app/services/data.py\n+++ b/app/services/data.py\n@@ -1,2 +1,4 @@",
        ),
        test_generation=TestGenerationOutput(
            pytest_code="def test_process_data_none():\n    from app.services.data import process_data\n    process_data(None)"
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
    with patch("app.sre_pipeline.client") as mock_client:
        mock_response = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        yield mock_client
