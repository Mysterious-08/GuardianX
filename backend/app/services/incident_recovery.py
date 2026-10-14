from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.backup import BackupSnapshot, BackupStatus, RecoveryJob, RecoveryStatus
from app.models.device import Device, DeviceStatus
from app.models.security_event import SecurityEvent, SecurityEventType
from app.models.user import User
from app.services.backup import BackupRecoveryService
from app.services.recovery_policy import ExplicitFileIntegrityPolicy, RecoveryOrchestrator

logger = logging.getLogger(__name__)


class IncidentRecoveryService:
    """Create idempotent recovery jobs for explicitly eligible file events."""

    def __init__(
        self,
        db: Session,
        *,
        orchestrator: RecoveryOrchestrator | None = None,
    ) -> None:
        self.db = db
        self.orchestrator = orchestrator or RecoveryOrchestrator(ExplicitFileIntegrityPolicy())
        self.backups = BackupRecoveryService(db)

    def process_event(self, event_id: UUID) -> RecoveryJob | None:
        event = self.db.scalar(select(SecurityEvent).where(SecurityEvent.id == event_id))
        if event is None:
            raise LookupError("Security event not found.")
        if event.event_type is not SecurityEventType.FILE:
            return None

        existing = self._get_event_job(event.id)
        if existing is not None:
            return existing

        device = self.db.scalar(select(Device).where(Device.id == event.device_id))
        user = self.db.get(User, device.user_id) if device is not None else None
        if (
            device is None
            or device.status is DeviceStatus.UNINSTALLED
            or user is None
            or not user.is_active
        ):
            return self._record_skipped(
                event=event,
                user_id=device.user_id if device is not None and user is not None else None,
                device_id=device.id if device is not None else None,
                source_directory=self._payload_source(event),
                reason="The event device or its active owner is unavailable.",
            )

        reason = self.orchestrator.ineligibility_reason(event)
        if reason is not None:
            return self._record_skipped(
                event=event,
                user_id=user.id,
                device_id=device.id,
                source_directory=self._payload_source(event),
                reason=reason,
            )

        source_directory = self._payload_source(event)
        if source_directory is None:
            return self._record_skipped(
                event=event,
                user_id=user.id,
                device_id=device.id,
                source_directory=None,
                reason="The event is missing its protected source directory.",
            )

        backup = self._find_compatible_backup(
            user_id=user.id,
            device_id=device.id,
            source_directory=source_directory,
        )
        if backup is None:
            return self._record_skipped(
                event=event,
                user_id=user.id,
                device_id=device.id,
                source_directory=source_directory,
                reason="No VERIFIED snapshot matches this device, owner, and protected source.",
            )

        try:
            recovery_path = self._recovery_path(event.id)
            job = self.backups.start_recovery(
                user=user,
                backup_id=backup.id,
                recovery_directory=recovery_path,
                security_event_id=event.id,
            )
            self.db.refresh(job)
            return job
        except (ValueError, RuntimeError) as exc:
            self.db.rollback()
            return self._record_skipped(
                event=event,
                user_id=user.id,
                device_id=device.id,
                source_directory=source_directory,
                reason=str(exc) or exc.__class__.__name__,
                backup_id=backup.id,
            )
        except IntegrityError:
            self.db.rollback()
            existing = self._get_event_job(event.id)
            if existing is not None:
                return existing
            return self._record_skipped(
                event=event,
                user_id=user.id,
                device_id=device.id,
                source_directory=source_directory,
                reason="Another recovery job is already active for this protected source.",
                backup_id=backup.id,
            )

    def _get_event_job(self, event_id: UUID) -> RecoveryJob | None:
        return self.db.scalar(
            select(RecoveryJob).where(RecoveryJob.security_event_id == event_id)
        )

    @staticmethod
    def _payload_source(event: SecurityEvent) -> str | None:
        source_directory = event.payload.get("source_directory")
        if not isinstance(source_directory, str) or not source_directory.strip():
            return None
        return str(Path(source_directory).expanduser().resolve(strict=False))

    def _find_compatible_backup(
        self,
        *,
        user_id: UUID,
        device_id: UUID,
        source_directory: str,
    ) -> BackupSnapshot | None:
        statement = (
            select(BackupSnapshot)
            .where(
                BackupSnapshot.user_id == user_id,
                BackupSnapshot.device_id == device_id,
                BackupSnapshot.source_directory == source_directory,
                BackupSnapshot.status == BackupStatus.VERIFIED,
            )
            .order_by(BackupSnapshot.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    @staticmethod
    def _recovery_path(event_id: UUID) -> str:
        if settings.recovery_root is None:
            raise ValueError("Automatic recovery requires RECOVERY_ROOT to be configured.")
        recovery_root = Path(settings.recovery_root).expanduser().resolve(strict=False)
        return str(recovery_root / event_id.hex)

    def _record_skipped(
        self,
        *,
        event: SecurityEvent,
        user_id: UUID | None,
        device_id: UUID | None,
        source_directory: str | None,
        reason: str,
        backup_id: UUID | None = None,
    ) -> RecoveryJob | None:
        if user_id is None:
            logger.warning(
                "Automatic recovery skipped because event owner could not be resolved.",
                extra={"security_event_id": str(event.id), "reason": reason},
            )
            return None
        job = RecoveryJob(
            backup_id=backup_id,
            security_event_id=event.id,
            device_id=device_id,
            user_id=user_id,
            source_directory=source_directory,
            recovery_directory=None,
            status=RecoveryStatus.SKIPPED,
            error=reason,
            completed_at=datetime.now(timezone.utc),
        )
        try:
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job
        except IntegrityError:
            self.db.rollback()
            existing = self._get_event_job(event.id)
            if existing is not None:
                return existing
            logger.exception("Could not persist skipped automatic recovery for event %s.", event.id)
            raise
