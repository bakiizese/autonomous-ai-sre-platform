from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GEMINI_MODEL_ID: str = "gemini-2.5-flash"

    # GitHub — GITHUB_REPO is deprecated in favor of SANDBOX_REPOS, kept for
    # backward compatibility with existing .env files (aliased in __init__).
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    SANDBOX_REPOS: str = ""

    PORT: int = 8000
    DATABASE_URL: str = "postgresql+psycopg://sre:sre@localhost:5433/sre"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    POLL_INTERVAL_SECONDS: int = 30
    CRITICAL_RISK_THRESHOLD: int = 8
    AGENT_MAX_FIX_RETRIES: int = 1

    # Abuse protection for the public demo. Per visitor (client IP) per 10 minutes;
    # "costly" actions spend Gemini quota or run the sandbox, "light" ones just call GitHub.
    # 0 disables a limit. DAILY_RUN_CAP bounds total pipeline runs per rolling 24h,
    # which also covers strangers opening issues on the public sandbox repo.
    RATE_LIMIT_COSTLY_PER_10MIN: int = 6
    RATE_LIMIT_LIGHT_PER_10MIN: int = 30
    DAILY_RUN_CAP: int = 50

    # Email alerting for critical-risk diagnoses
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_TO: str = ""  # deprecated alias for ADMIN_ALERT_EMAIL
    ALERT_EMAIL_FROM: str = ""  # defaults to SMTP_USER if left blank
    ADMIN_ALERT_EMAIL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Managed Postgres (Render, Neon, Heroku...) hands out plain postgres:// or
        postgresql:// URLs, which SQLAlchemy would resolve to the psycopg2 driver we
        don't install, so pin them to psycopg 3. Also forgive the usual copy-paste
        slips (quotes, a leading `psql`), and fail with a clear message for anything
        else — the raw SQLAlchemy error just says "could not parse URL". The value is
        deliberately never included in the message: it may contain the password."""
        url = value.strip()
        if url.startswith("psql"):
            url = url[4:].strip()
        url = url.strip("'\"").strip()

        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        if url.startswith("postgresql+psycopg://"):
            return url

        raise ValueError(
            "DATABASE_URL is empty or not a Postgres URL. It must be one line starting with "
            "postgresql:// — check for a blank value, a placeholder, or the wrong text pasted."
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.SANDBOX_REPOS and self.GITHUB_REPO:
            self.SANDBOX_REPOS = self.GITHUB_REPO
        if not self.ADMIN_ALERT_EMAIL and self.ALERT_EMAIL_TO:
            self.ADMIN_ALERT_EMAIL = self.ALERT_EMAIL_TO

    @property
    def sandbox_repo_list(self) -> list[str]:
        return [r.strip() for r in self.SANDBOX_REPOS.split(",") if r.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
