from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.backup import BackupSnapshot
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.services.backup import BackupRecoveryService

logger = logging.getLogger(__name__)

ConfigurationValidator = Callable[[str, str, UUID], None]
ScheduledBackupRunner = Callable[[str, str, UUID], dict[str, Any]]


class BackupScheduler:
    """Run one configured backup at a time on a lightweight asyncio interval."""

    def __init__(
        self,
        *,
        enabled: bool,
        interval_minutes: int,
        source_directory: str | None,
        destination_directory: str | None,
        device_agent_id: UUID | None,
        validate_configuration: ConfigurationValidator,
        run_backup: ScheduledBackupRunner,
    ) -> None:
        self.enabled = enabled
        self.interval_minutes = interval_minutes
        self.source_directory = source_directory
        self.destination_directory = destination_directory
        self.device_agent_id = device_agent_id
        self.validate_configuration = validate_configuration
        self.run_backup_callback = run_backup
        self.state = "disabled" if not enabled else "starting"
        self.message = "Scheduled backups are disabled by configuration." if not enabled else None
        self.last_run_at: datetime | None = None
        self.last_outcome: str | None = None
        self.last_backup_id: UUID | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._run_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._start_lock:
            if not self.enabled:
                self.state = "disabled"
                self.message = "Scheduled backups are disabled by BACKUP_SCHEDULER_ENABLED."
                return
            if self._task is not None and not self._task.done():
                return

            if (
                not self.source_directory
                or not self.source_directory.strip()
                or not self.destination_directory
                or not self.destination_directory.strip()
            ):
                self.state = "misconfigured"
                self.message = (
                    "Set BACKUP_SOURCE_DIRECTORY and BACKUP_DESTINATION_DIRECTORY before enabling "
                    "scheduled backups."
                )
                logger.error("Scheduled backup scheduler is misconfigured: required paths are missing.")
                return

            if self.device_agent_id is None:
                self.state = "misconfigured"
                self.message = "Set BACKUP_DEVICE_AGENT_ID to a registered, active GuardianX device before enabling scheduled backups."
                logger.error("Scheduled backup scheduler is misconfigured: registered device association is missing.")
                return

            try:
                await asyncio.to_thread(
                    self.validate_configuration,
                    self.source_directory,
                    self.destination_directory,
                    self.device_agent_id,
                )
            except Exception as exc:
                self.state = "misconfigured"
                self.message = str(exc) or "Scheduled backup paths failed validation."
                logger.error("Scheduled backup scheduler is misconfigured: %s", self.message)
                return

            self._stop_event = asyncio.Event()
            self.state = "enabled"
            self.message = None
            self._task = asyncio.create_task(self._run_loop(), name="guardianx-backup-scheduler")
            logger.info(
                "Scheduled backup scheduler started.",
                extra={"interval_minutes": self.interval_minutes},
            )

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        await task
        self._task = None
        self._stop_event = None
        if self.enabled and self.state != "misconfigured":
            self.state = "stopped"
        logger.info("Scheduled backup scheduler stopped.")

    async def _run_loop(self) -> None:
        stop_event = self._stop_event
        if stop_event is None:
            return
        interval_seconds = self.interval_minutes * 60
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except TimeoutError:
                await self.run_once()

    async def run_once(self) -> bool:
        if not self.enabled or self.state != "enabled":
            return False
        if self._run_lock.locked():
            logger.warning("Overlapping scheduled backup run skipped.")
            return False

        async with self._run_lock:
            self.last_run_at = datetime.now(timezone.utc)
            self.last_outcome = "RUNNING"
            self.last_backup_id = None
            self.last_error = None
            source = self.source_directory
            destination = self.destination_directory
            device_agent_id = self.device_agent_id
            if not source or not destination or device_agent_id is None:
                self.last_outcome = "FAILED"
                self.last_error = "Scheduled source, destination, and registered device are required."
                return False
            try:
                result = await asyncio.to_thread(
                    self.run_backup_callback,
                    source,
                    destination,
                    device_agent_id,
                )
                self.last_backup_id = result.get("backup_id")
                self.last_outcome = str(result.get("status", "FAILED"))
                self.last_error = result.get("error")
                if self.last_outcome != "VERIFIED":
                    logger.error(
                        "Scheduled backup run failed.",
                        extra={
                            "backup_id": str(self.last_backup_id) if self.last_backup_id else None,
                            "outcome": self.last_outcome,
                            "error": self.last_error,
                        },
                    )
                    return False
                logger.info(
                    "Scheduled backup run completed.",
                    extra={"backup_id": str(self.last_backup_id)},
                )
                return True
            except Exception as exc:
                self.last_outcome = "FAILED"
                self.last_error = str(exc) or exc.__class__.__name__
                logger.exception("Scheduled backup run failed.")
                return False

    def get_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "interval_minutes": self.interval_minutes,
            "message": self.message,
            "last_run_at": self.last_run_at,
            "last_outcome": self.last_outcome,
            "backup_id": self.last_backup_id,
            "error": self.last_error,
        }


def validate_scheduled_backup_configuration(
    source: str,
    destination: str,
    device_agent_id: UUID,
) -> None:
    with SessionLocal() as db:
        BackupRecoveryService(db).validate_source_and_destination(source, destination)
        if _get_scheduled_device(db, device_agent_id) is None:
            raise ValueError("BACKUP_DEVICE_AGENT_ID must identify a registered device with an active owner.")


def run_scheduled_backup(source: str, destination: str, device_agent_id: UUID) -> dict[str, Any]:
    with SessionLocal() as db:
        device = _get_scheduled_device(db, device_agent_id)
        if device is None:
            raise RuntimeError("BACKUP_DEVICE_AGENT_ID must identify a registered device with an active owner.")

        user = db.get(User, device.user_id)
        if user is None:
            raise RuntimeError("The scheduled backup device owner no longer exists.")
        service = BackupRecoveryService(db)
        backup = service.create_backup(
            user=user,
            source=source,
            destination=destination,
            device_id=device.id,
        )
        service.run_backup(backup.id, scheduled=True)
        db.refresh(backup)
        return {
            "backup_id": backup.id,
            "status": backup.status.value,
            "error": backup.error,
        }


def _get_scheduled_device(db: Session, device_agent_id: UUID) -> Device | None:
    return db.scalar(
        select(Device)
        .join(User, Device.user_id == User.id)
        .where(
            Device.agent_id == device_agent_id,
            Device.status != DeviceStatus.UNINSTALLED,
            User.is_active.is_(True),
        )
    )


def get_scheduled_device_owner(device_agent_id: UUID) -> UUID | None:
    with SessionLocal() as db:
        device = _get_scheduled_device(db, device_agent_id)
        return device.user_id if device is not None else None


def build_backup_scheduler() -> BackupScheduler:
    return BackupScheduler(
        enabled=settings.BACKUP_SCHEDULER_ENABLED,
        interval_minutes=settings.BACKUP_INTERVAL_MINUTES,
        source_directory=settings.scheduled_backup_source,
        destination_directory=settings.scheduled_backup_destination,
        device_agent_id=settings.BACKUP_DEVICE_AGENT_ID,
        validate_configuration=validate_scheduled_backup_configuration,
        run_backup=run_scheduled_backup,
    )


def get_latest_persisted_scheduled_run(
    source_directory: str,
    destination_directory: str,
    device_agent_id: UUID,
) -> dict[str, Any] | None:
    source = str(Path(source_directory).expanduser().resolve())
    destination = str(Path(destination_directory).expanduser().resolve())
    with SessionLocal() as db:
        device = _get_scheduled_device(db, device_agent_id)
        if device is None:
            return None
        statement = (
            select(BackupSnapshot)
            .where(
                BackupSnapshot.source_directory == source,
                BackupSnapshot.destination_directory == destination,
                BackupSnapshot.device_id == device.id,
                BackupSnapshot.user_id == device.user_id,
            )
            .order_by(BackupSnapshot.created_at.desc())
            .limit(1)
        )
        backup = db.scalar(statement)
        if backup is None:
            return None
        return {
            "last_run_at": backup.completed_at or backup.created_at,
            "last_outcome": backup.status.value,
            "backup_id": backup.id,
            "error": backup.error,
        }
