from pathlib import Path
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = Field(default="GuardianX")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ISSUER: str = Field(default="GuardianX")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    CORS_ORIGINS: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:4173,http://127.0.0.1:4173"
        )
    )
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://guardianx:guardianx@localhost:5432/guardianx")
    BACKUP_ALLOWED_ROOTS: str = Field(default="")
    RECOVERY_ROOT: str = Field(default="")
    BACKUP_SCHEDULER_ENABLED: bool = Field(default=False)
    BACKUP_INTERVAL_MINUTES: int = Field(default=60, ge=1, le=10080)
    BACKUP_SOURCE_DIRECTORY: str | None = Field(default=None, min_length=1)
    BACKUP_DESTINATION_DIRECTORY: str | None = Field(default=None, min_length=1)
    BACKUP_DEVICE_AGENT_ID: UUID | None = Field(default=None)
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured browser origins without empty values or whitespace."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def backup_allowed_root_list(self) -> list[str]:
        """Return explicitly configured filesystem roots available to backup operations."""
        return [root.strip() for root in self.BACKUP_ALLOWED_ROOTS.split(";") if root.strip()]

    @property
    def recovery_root(self) -> str | None:
        """Return the explicitly configured recovery directory, if any."""
        return self.RECOVERY_ROOT.strip() or None

    @property
    def scheduled_backup_source(self) -> str | None:
        value = self.BACKUP_SOURCE_DIRECTORY.strip() if self.BACKUP_SOURCE_DIRECTORY else ""
        return value or None

    @property
    def scheduled_backup_destination(self) -> str | None:
        value = self.BACKUP_DESTINATION_DIRECTORY.strip() if self.BACKUP_DESTINATION_DIRECTORY else ""
        return value or None


settings = Settings()
