import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    PORT: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()