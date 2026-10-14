from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.backup import BackupStatus, RecoveryStatus


class CreateBackupRequest(BaseModel):
    source_directory: str = Field(min_length=1, max_length=4096)
    destination_directory: str = Field(min_length=1, max_length=4096)


class StartRecoveryRequest(BaseModel):
    recovery_directory: str | None = Field(default=None, min_length=1, max_length=4096)


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_directory: str
    destination_directory: str
    snapshot_directory: str
    device_id: UUID | None
    status: BackupStatus
    manifest: dict[str, Any] | None = Field(exclude=True)
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @computed_field
    @property
    def file_count(self) -> int:
        manifest = self.manifest
        files = manifest.get("files", []) if isinstance(manifest, dict) else []
        return len(files) if isinstance(files, list) else 0

    @computed_field
    @property
    def trigger(self) -> Literal["manual", "scheduled"]:
        return (
            "scheduled"
            if self.device_id is not None
            or isinstance(self.manifest, dict) and self.manifest.get("trigger") == "scheduled"
            else "manual"
        )


class RecoveryJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    backup_id: UUID | None
    security_event_id: UUID | None
    device_id: UUID | None
    source_directory: str | None
    recovery_directory: str | None
    status: RecoveryStatus
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class BackupSchedulerStatusResponse(BaseModel):
    enabled: bool
    state: Literal["disabled", "starting", "enabled", "misconfigured", "stopped"]
    interval_minutes: int
    message: str | None
    last_run_at: datetime | None
    last_outcome: str | None
    backup_id: UUID | None
    error: str | None
