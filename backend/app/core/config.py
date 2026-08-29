import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    PORT: int = 8000

    # Email alerting for critical-risk diagnoses
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_TO: str = ""  # where critical alerts are sent
    ALERT_EMAIL_FROM: str = ""  # defaults to SMTP_USER if left blank

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
