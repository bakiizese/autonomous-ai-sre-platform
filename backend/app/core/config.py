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

    # Email alerting for critical-risk diagnoses
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_TO: str = ""  # deprecated alias for ADMIN_ALERT_EMAIL
    ALERT_EMAIL_FROM: str = ""  # defaults to SMTP_USER if left blank
    ADMIN_ALERT_EMAIL: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
