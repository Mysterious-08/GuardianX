from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base
from app.models.backup import BackupStatus, RecoveryJob, RecoveryStatus
from app.models.device import Device, DeviceStatus
from app.models.security_event import SecurityEvent, SecurityEventSeverity, SecurityEventType
from app.models.user import User
from app.services.backup import BackupRecoveryService
from app.services.incident_recovery import IncidentRecoveryService
from app.services.recovery_policy import ExplicitFileIntegrityPolicy


@pytest.fixture
def incident_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    allowed_root = tmp_path / "allowed"
    source = allowed_root / "protected"
    backup_destination = allowed_root / "snapshots"
    recovery_root = allowed_root / "recovery"
    source.mkdir(parents=True)
    backup_destination.mkdir()
    recovery_root.mkdir()
    protected_file = source / "document.txt"
    protected_file.write_text("original data", encoding="utf-8")
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(allowed_root))
    monkeypatch.setattr(settings, "RECOVERY_ROOT", str(recovery_root))

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        owner = User(username="incident-owner", email="incident-owner@example.com", hashed_password="x")
        other_owner = User(username="other-owner", email="other-owner@example.com", hashed_password="x")
        db.add_all([owner, other_owner])
        db.commit()
        db.refresh(owner)
        db.refresh(other_owner)
        device = Device(
            agent_id=uuid4(),
            user_id=owner.id,
            hostname="incident-host",
            operating_system="Windows",
        )
        other_device = Device(
            agent_id=uuid4(),
            user_id=other_owner.id,
            hostname="other-host",
            operating_system="Windows",
        )
        db.add_all([device, other_device])
        db.commit()
        db.refresh(device)
        db.refresh(other_device)
        backups = BackupRecoveryService(db)
        backup = backups.create_backup(
            user=owner,
            source=str(source),
            destination=str(backup_destination),
            device_id=device.id,
        )
        backups.run_backup(backup.id, scheduled=True)
        db.refresh(backup)
        yield db, owner, other_owner, device, other_device, source, protected_file, backup_destination, recovery_root, backup
    engine.dispose()


def _create_event(
    db: Session,
    device: Device,
    source: Path,
    protected_file: Path,
    *,
    event_type: SecurityEventType = SecurityEventType.FILE,
    payload: dict[str, object] | None = None,
) -> SecurityEvent:
    event = SecurityEvent(
        device_id=device.id,
        event_type=event_type,
        severity=SecurityEventSeverity.HIGH,
        source="file-monitor",
        timestamp=datetime.now(timezone.utc),
        payload=payload
        if payload is not None
        else {
            "recovery_eligible": True,
            "integrity_verified": True,
            "source_directory": str(source),
            "file_path": str(protected_file),
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _process_and_restore(db: Session, event: SecurityEvent):
    orchestrator = IncidentRecoveryService(db)
    job = orchestrator.process_event(event.id)
    if job is not None and job.status is RecoveryStatus.QUEUED:
        BackupRecoveryService(db).run_recovery(job.id)
        db.refresh(job)
    return job


def test_eligible_file_event_restores_matching_snapshot_exactly_once(incident_environment) -> None:
    db, owner, _, device, _, source, protected_file, _, recovery_root, backup = incident_environment
    event = _create_event(db, device, source, protected_file)
    orchestrator = IncidentRecoveryService(db)

    queued = orchestrator.process_event(event.id)
    duplicate = orchestrator.process_event(event.id)
    assert queued is not None
    assert queued.id == duplicate.id
    assert queued.backup_id == backup.id
    assert queued.security_event_id == event.id
    assert queued.device_id == device.id
    assert queued.user_id == owner.id

    BackupRecoveryService(db).run_recovery(queued.id)
    db.refresh(queued)
    assert queued.status is RecoveryStatus.COMPLETED
    assert queued.completed_at is not None
    assert Path(queued.recovery_directory) == recovery_root / event.id.hex
    assert (Path(queued.recovery_directory) / protected_file.name).read_text(encoding="utf-8") == "original data"
    assert protected_file.read_text(encoding="utf-8") == "original data"
    assert len(BackupRecoveryService(db).list_recovery_jobs(user=owner)) == 1


def test_network_events_and_generic_anomalies_never_create_recovery_jobs(incident_environment) -> None:
    db, _, _, device, _, source, protected_file, *_ = incident_environment
    network_event = _create_event(
        db,
        device,
        source,
        protected_file,
        event_type=SecurityEventType.NETWORK,
        payload={
            "recovery_eligible": True,
            "integrity_verified": True,
            "source_directory": str(source),
            "file_path": str(protected_file),
            "anomaly_score": 0.99,
        },
    )
    assert IncidentRecoveryService(db).process_event(network_event.id) is None
    assert db.scalar(select(RecoveryJob).where(RecoveryJob.security_event_id == network_event.id)) is None


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (
            {
                "recovery_eligible": False,
                "integrity_verified": True,
                "source_directory": "placeholder",
                "file_path": "placeholder",
            },
            "not explicitly marked as recovery eligible",
        ),
        (
            {
                "recovery_eligible": True,
                "integrity_verified": False,
                "source_directory": "placeholder",
                "file_path": "placeholder",
            },
            "does not contain explicit integrity verification",
        ),
        ({"recovery_eligible": True, "integrity_verified": True}, "missing its protected source directory"),
    ],
)
def test_ineligible_or_unverifiable_file_events_are_skipped(
    incident_environment,
    payload: dict[str, object],
    reason: str,
) -> None:
    db, owner, _, device, _, source, protected_file, *_ = incident_environment
    event = _create_event(db, device, source, protected_file, payload=payload)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert reason in (job.error or "")
    assert job.user_id == owner.id
    assert job.backup_id is None


def test_missing_or_mismatched_snapshot_never_restores(incident_environment) -> None:
    db, _, _, device, other_device, source, protected_file, backup_destination, _, backup = incident_environment
    backup.device_id = other_device.id
    db.commit()
    event = _create_event(db, device, source, protected_file)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert "No VERIFIED snapshot matches" in (job.error or "")
    assert protected_file.read_text(encoding="utf-8") == "original data"
    assert backup.status is BackupStatus.VERIFIED
    assert backup_destination.exists()


def test_different_source_snapshot_is_not_selected(incident_environment, tmp_path: Path) -> None:
    db, _, _, device, _, _source, protected_file, _, _, backup = incident_environment
    other_source = tmp_path / "allowed" / "other-source"
    other_source.mkdir()
    other_file = other_source / "other.txt"
    other_file.write_text("other source", encoding="utf-8")
    event = _create_event(db, device, other_source, other_file)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert "No VERIFIED snapshot matches" in (job.error or "")
    assert backup.status is BackupStatus.VERIFIED
    assert protected_file.read_text(encoding="utf-8") == "original data"


def test_snapshot_owned_by_different_user_is_not_selected(incident_environment) -> None:
    db, _, other_owner, device, other_device, source, protected_file, _, _, backup = incident_environment
    backup.user_id = other_owner.id
    backup.device_id = other_device.id
    db.commit()
    event = _create_event(db, device, source, protected_file)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert job.backup_id is None
    assert "No VERIFIED snapshot matches" in (job.error or "")


def test_corrupted_snapshot_fails_restore_without_changing_original(incident_environment) -> None:
    db, _, _, device, _, source, protected_file, _, _, backup = incident_environment
    (Path(backup.snapshot_directory) / "files" / protected_file.name).write_text("tampered", encoding="utf-8")
    event = _create_event(db, device, source, protected_file)

    job = _process_and_restore(db, event)

    assert job is not None
    assert job.status is RecoveryStatus.FAILED
    assert "integrity" in (job.error or "").lower()
    assert protected_file.read_text(encoding="utf-8") == "original data"


def test_two_incidents_for_same_source_do_not_overlap(incident_environment) -> None:
    db, owner, _, device, _, source, protected_file, _, recovery_root, _ = incident_environment
    first = _create_event(db, device, source, protected_file)
    second = _create_event(db, device, source, protected_file)
    service = IncidentRecoveryService(db)

    first_job = service.process_event(first.id)
    second_job = service.process_event(second.id)

    assert first_job is not None
    assert first_job.status is RecoveryStatus.QUEUED
    assert second_job is not None
    assert second_job.status is RecoveryStatus.SKIPPED
    assert "already active" in (second_job.error or "")
    assert len(BackupRecoveryService(db).list_recovery_jobs(user=owner)) == 2
    assert list(recovery_root.iterdir()) == []


def test_missing_recovery_root_is_reported_as_skipped(incident_environment, monkeypatch: pytest.MonkeyPatch) -> None:
    db, _, _, device, _, source, protected_file, *_ = incident_environment
    monkeypatch.setattr(settings, "RECOVERY_ROOT", "")
    event = _create_event(db, device, source, protected_file)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert "RECOVERY_ROOT" in (job.error or "")


def test_uninstalled_device_is_skipped(incident_environment) -> None:
    db, owner, _, device, _, source, protected_file, *_ = incident_environment
    device.status = DeviceStatus.UNINSTALLED
    db.commit()
    event = _create_event(db, device, source, protected_file)

    job = IncidentRecoveryService(db).process_event(event.id)

    assert job is not None
    assert job.status is RecoveryStatus.SKIPPED
    assert "device or its active owner is unavailable" in (job.error or "")
    assert job.user_id == owner.id


def test_recovery_history_is_scoped_to_owner(incident_environment) -> None:
    db, owner, other_owner, device, _, source, protected_file, *_ = incident_environment
    event = _create_event(db, device, source, protected_file)
    job = IncidentRecoveryService(db).process_event(event.id)
    assert job is not None

    backups = BackupRecoveryService(db)
    assert backups.list_recovery_jobs(user=owner) == [job]
    assert backups.list_recovery_jobs(user=other_owner) == []
    with pytest.raises(LookupError, match="Recovery job not found"):
        backups.get_recovery_job(user=other_owner, job_id=job.id)


def test_event_ingestion_queues_and_executes_auto_recovery_after_persist(
    incident_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_security_event_service
    from app.api.routes import device as device_routes
    from app.models.security_event import SecurityEvent
    from app.security.dependencies import get_current_user
    from app.services.security_event import SecurityEventService

    db, owner, _, device, _, source, protected_file, _, recovery_root, backup = incident_environment
    app = FastAPI()
    app.include_router(device_routes.router)
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_security_event_service] = lambda: SecurityEventService(db)
    monkeypatch.setattr(
        device_routes,
        "SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )

    with TestClient(app) as client:
        response = client.post(
            f"/devices/{device.agent_id}/events",
            json={
                "event_type": "FILE",
                "severity": "HIGH",
                "source": "file-monitor",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": {
                    "recovery_eligible": True,
                    "integrity_verified": True,
                    "source_directory": str(source),
                    "file_path": str(protected_file),
                },
            },
        )

    assert response.status_code == 201
    event_id = response.json()["id"]
    event = db.get(SecurityEvent, UUID(event_id))
    assert event is not None
    job = db.scalar(select(RecoveryJob).where(RecoveryJob.security_event_id == event.id))
    assert job is not None
    assert job.status is RecoveryStatus.COMPLETED
    assert job.backup_id == backup.id
    assert job.recovery_directory == str(recovery_root / event.id.hex)
    assert (Path(job.recovery_directory) / protected_file.name).read_text(encoding="utf-8") == "original data"
