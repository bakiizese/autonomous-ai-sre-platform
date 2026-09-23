from datetime import datetime, timedelta, timezone

import httpx

from app.db.models import RateLimitState
from app.db.session import SessionLocal


def _get_or_create(db, provider: str) -> RateLimitState:
    state = db.query(RateLimitState).filter_by(provider=provider).one_or_none()
    if state is None:
        state = RateLimitState(provider=provider)
        db.add(state)
        db.flush()
    return state


def record_github_response(response: httpx.Response) -> None:
    """Reads GitHub's rate-limit headers off every response (success or
    failure) and tracks whether we're currently limited. Called from
    GitHubClient._request() on every call, before raise_for_status()."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    retry_after = response.headers.get("Retry-After")
    is_limited = response.status_code in (403, 429) and (remaining == "0" or retry_after is not None)

    with SessionLocal() as db:
        state = _get_or_create(db, "github")
        if remaining is not None:
            state.remaining_calls = int(remaining)
        state.last_checked_at = datetime.now(timezone.utc)
        state.is_limited = is_limited
        if is_limited:
            if reset is not None:
                state.limited_until = datetime.fromtimestamp(int(reset), tz=timezone.utc)
            elif retry_after is not None:
                state.limited_until = datetime.now(timezone.utc) + timedelta(seconds=int(retry_after))
            state.last_error_message = f"GitHub rate limited (status {response.status_code})"
        db.commit()


def record_gemini_rate_limit(retry_after_seconds: int | None = None, message: str | None = None) -> None:
    with SessionLocal() as db:
        state = _get_or_create(db, "gemini")
        state.is_limited = True
        state.last_checked_at = datetime.now(timezone.utc)
        state.limited_until = (
            datetime.now(timezone.utc) + timedelta(seconds=retry_after_seconds)
            if retry_after_seconds is not None
            else None
        )
        state.last_error_message = message
        db.commit()


def record_gemini_success() -> None:
    with SessionLocal() as db:
        state = _get_or_create(db, "gemini")
        state.is_limited = False
        state.limited_until = None
        state.last_checked_at = datetime.now(timezone.utc)
        db.commit()


def is_gemini_limited() -> bool:
    with SessionLocal() as db:
        state = db.query(RateLimitState).filter_by(provider="gemini").one_or_none()
        if state is None or not state.is_limited:
            return False
        if state.limited_until and state.limited_until <= datetime.now(timezone.utc):
            return False
        return True


def get_status() -> dict:
    with SessionLocal() as db:
        result = {}
        for provider in ("gemini", "github"):
            state = db.query(RateLimitState).filter_by(provider=provider).one_or_none()
            if state is None:
                result[provider] = {"is_limited": False, "limited_until": None, "remaining_calls": None}
            else:
                result[provider] = {
                    "is_limited": state.is_limited,
                    "limited_until": state.limited_until.isoformat() if state.limited_until else None,
                    "remaining_calls": state.remaining_calls,
                }
        return result
