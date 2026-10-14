from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLAlchemyEnum, ForeignKey, Index, JSON, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BackupStatus(PyEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CORRUPT = "CORRUPT"


class RecoveryStatus(PyEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class BackupSnapshot(Base):
    __tablename__ = "backup_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_directory: Mapped[str] = mapped_column(Text, nullable=False)
    destination_directory: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_directory: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[BackupStatus] = mapped_column(
        SQLAlchemyEnum(BackupStatus, name="backupstatus", native_enum=False),
        nullable=False,
        default=BackupStatus.QUEUED,
        server_default=BackupStatus.QUEUED.value,
        index=True,
    )
    manifest: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecoveryJob(Base):
    __tablename__ = "recovery_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, nullable=False)
    backup_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("backup_snapshots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    security_event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security_events.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_directory: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_directory: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RecoveryStatus] = mapped_column(
        SQLAlchemyEnum(RecoveryStatus, name="recoverystatus", native_enum=False),
        nullable=False,
        default=RecoveryStatus.QUEUED,
        server_default=RecoveryStatus.QUEUED.value,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "uq_recovery_jobs_active_source",
    RecoveryJob.source_directory,
    unique=True,
    sqlite_where=text("source_directory IS NOT NULL AND status IN ('QUEUED', 'RUNNING')"),
    postgresql_where=text("source_directory IS NOT NULL AND status IN ('QUEUED', 'RUNNING')"),
)
