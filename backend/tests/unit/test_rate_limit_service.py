from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import RateLimitState
from app.services import rate_limit_service


@pytest.fixture(autouse=True)
def clean_rate_limit_state():
    """rate_limit_service manages its own commits (it has to — it's called
    from a singleton GitHubClient with no per-request session), so it can't
    use the db_session transaction-rollback fixture. Clear the table around
    each test instead so state never leaks between tests or test runs."""
    with rate_limit_service.SessionLocal() as session:
        session.query(RateLimitState).delete()
        session.commit()
    yield
    with rate_limit_service.SessionLocal() as session:
        session.query(RateLimitState).delete()
        session.commit()


def test_gemini_starts_unlimited():
    assert rate_limit_service.is_gemini_limited() is False
    status = rate_limit_service.get_status()
    assert status["gemini"]["is_limited"] is False
    assert status["gemini"]["remaining_calls"] is None


def test_record_gemini_rate_limit_marks_limited():
    rate_limit_service.record_gemini_rate_limit(retry_after_seconds=60, message="429 from Gemini")

    assert rate_limit_service.is_gemini_limited() is True
    status = rate_limit_service.get_status()
    assert status["gemini"]["is_limited"] is True
    assert status["gemini"]["limited_until"] is not None


def test_record_gemini_success_clears_limit():
    rate_limit_service.record_gemini_rate_limit(retry_after_seconds=60)
    assert rate_limit_service.is_gemini_limited() is True

    rate_limit_service.record_gemini_success()

    assert rate_limit_service.is_gemini_limited() is False


def test_is_gemini_limited_expires_after_limited_until():
    with rate_limit_service.SessionLocal() as session:
        session.add(
            RateLimitState(
                provider="gemini",
                is_limited=True,
                limited_until=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
        )
        session.commit()

    assert rate_limit_service.is_gemini_limited() is False
