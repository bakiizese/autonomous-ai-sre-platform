import pytest

from app.core.config import Settings


def _settings(**overrides):
    return Settings(_env_file=None, GEMINI_API_KEY="x", **overrides)


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ],
)
def test_database_url_is_pinned_to_psycopg3(given, expected):
    assert _settings(DATABASE_URL=given).DATABASE_URL == expected


def test_legacy_names_still_alias_to_new_ones():
    s = _settings(GITHUB_REPO="o/r", ALERT_EMAIL_TO="a@example.com")
    assert s.sandbox_repo_list == ["o/r"]
    assert s.ADMIN_ALERT_EMAIL == "a@example.com"
