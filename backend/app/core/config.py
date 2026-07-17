from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = Field(default="GuardianX")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="change-me-in-production")
    DATABASE_URL: str = Field(default="sqlite:///./guardianx.db")

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
