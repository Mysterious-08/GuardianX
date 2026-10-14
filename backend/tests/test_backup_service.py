from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.api.dependencies import get_backup_recovery_service
from app.api.routes import backups as backup_routes
from app.core.config import settings
from app.models.backup import BackupSnapshot, BackupStatus, RecoveryStatus
from app.models.security_event import SecurityEvent, SecurityEventSeverity, SecurityEventType
from app.models.user import User
from app.schemas.backup import BackupResponse
import app.services.backup as backup_module
from app.services.backup import BackupRecoveryService
from app.services.recovery_policy import ExplicitFileIntegrityPolicy, RecoveryOrchestrator
from app.security.dependencies import get_current_user


@pytest.fixture
def backup_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "allowed"
    source = root / "protected"
    destination = root / "snapshots"
    recovery_root = root / "recovery-output"
    source.mkdir(parents=True)
    destination.mkdir()
    (source / "notes.txt").write_text("original contents", encoding="utf-8")
    (source / ".env").write_text("SECRET=must not be copied", encoding="utf-8")
    (source / "api-token.txt").write_text("token=must not be copied", encoding="utf-8")
    (source / "appsettings.json").write_text('{"api_key":"must not be copied"}', encoding="utf-8")
    monkeypatch.setattr(settings, "RECOVERY_ROOT", str(recovery_root))

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        user = User(username="backup-user", email="backup@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        yield db, user, root, source, destination, recovery_root
    engine.dispose()


def _create_verified_backup(db: Session, user: User, root: Path, source: Path, destination: Path) -> tuple[BackupRecoveryService, BackupSnapshot]:
    service = BackupRecoveryService(db, allowed_roots=[root])
    backup = service.create_backup(user=user, source=str(source), destination=str(destination))
    service.run_backup(backup.id)
    db.refresh(backup)
    return service, backup


def test_backup_creation_writes_manifest_and_verifies_hashes(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment

    service, backup = _create_verified_backup(db, user, root, source, destination)

    assert backup.status is BackupStatus.VERIFIED
    manifest = backup.manifest
    assert manifest is not None
    assert [entry["path"] for entry in manifest["files"]] == ["notes.txt"]
    assert len(manifest["files"][0]["sha256"]) == 64
    snapshot = Path(backup.snapshot_directory)
    assert (snapshot / "manifest.json").is_file()
    assert (snapshot / "files" / "notes.txt").read_text(encoding="utf-8") == "original contents"
    assert not (snapshot / "files" / ".env").exists()
    assert not (snapshot / "files" / "api-token.txt").exists()
    assert not (snapshot / "files" / "appsettings.json").exists()
    assert backup.error is None
    response = BackupResponse.model_validate(backup)
    assert response.file_count == 1
    assert response.trigger == "manual"
    assert response.device_id is None
    assert "manifest" not in response.model_dump()


def test_verification_marks_modified_snapshot_corrupt(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)

    (Path(backup.snapshot_directory) / "files" / "notes.txt").write_text("tampered", encoding="utf-8")
    service.verify_backup(user=user, backup_id=backup.id)
    service.run_verification(backup.id)
    db.refresh(backup)

    assert backup.status is BackupStatus.CORRUPT
    assert "integrity verification" in (backup.error or "")
    with pytest.raises(RuntimeError, match="VERIFIED"):
        service.start_recovery(user=user, backup_id=backup.id)


def test_restore_recovers_original_after_source_is_modified(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)
    (source / "notes.txt").write_text("changed source", encoding="utf-8")

    job = service.start_recovery(user=user, backup_id=backup.id)
    service.run_recovery(job.id)
    db.refresh(job)

    assert job.status is RecoveryStatus.COMPLETED
    assert Path(job.recovery_directory) == recovery_root / backup.id.hex
    assert (Path(job.recovery_directory) / "notes.txt").read_text(encoding="utf-8") == "original contents"
    assert (source / "notes.txt").read_text(encoding="utf-8") == "changed source"
    assert Path(job.recovery_directory) != source


def test_invalid_paths_and_overlapping_destination_are_rejected(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service = BackupRecoveryService(db, allowed_roots=[root])

    with pytest.raises(ValueError, match="absolute"):
        service.create_backup(user=user, source=str(root / ".." / "outside"), destination=str(destination))
    with pytest.raises(ValueError, match="outside"):
        service.create_backup(user=user, source=str(source), destination=str(root.parent))
    with pytest.raises(ValueError, match="overlap"):
        service.create_backup(user=user, source=str(source), destination=str(source / "nested-backups"))


def test_backup_fails_instead_of_following_symlink_outside_source(
    backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    outside = root / "outside.txt"
    outside.write_text("must not be copied", encoding="utf-8")
    link = source / "external-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        link.write_text("simulated reparse point", encoding="utf-8")
        original_check = backup_module._has_reparse_point
        monkeypatch.setattr(
            backup_module,
            "_has_reparse_point",
            lambda path: path == link or original_check(path),
        )
    service = BackupRecoveryService(db, allowed_roots=[root])
    backup = service.create_backup(user=user, source=str(source), destination=str(destination))

    service.run_backup(backup.id)
    db.refresh(backup)

    assert backup.status is BackupStatus.FAILED
    assert "symbolic links" in (backup.error or "").lower()
    assert not (Path(backup.snapshot_directory) / "files" / "external-link.txt").exists()


def test_failed_recovery_does_not_overwrite_existing_files(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)
    job = service.start_recovery(user=user, backup_id=backup.id)
    recovery_directory = Path(job.recovery_directory)
    recovery_directory.mkdir(parents=True)
    marker = recovery_directory / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    service.run_recovery(job.id)
    db.refresh(job)

    assert job.status is RecoveryStatus.FAILED
    assert "already exists" in (job.error or "")
    assert marker.read_text(encoding="utf-8") == "do not overwrite"


def test_unverified_backup_cannot_be_restored(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service = BackupRecoveryService(db, allowed_roots=[root])
    backup = service.create_backup(user=user, source=str(source), destination=str(destination))

    with pytest.raises(RuntimeError, match="VERIFIED"):
        service.start_recovery(user=user, backup_id=backup.id        )


def test_recovery_root_overlapping_backup_destination_is_rejected(backup_environment, monkeypatch: pytest.MonkeyPatch) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)
    monkeypatch.setattr(settings, "RECOVERY_ROOT", str(destination))

    with pytest.raises(ValueError, match="must be separate"):
        service.start_recovery(user=user, backup_id=backup.id)


def test_recovery_policy_requires_explicit_verified_file_evidence(tmp_path: Path) -> None:
    policy = RecoveryOrchestrator(ExplicitFileIntegrityPolicy())
    source = tmp_path / "protected"
    file_path = source / "sample.txt"
    file_evidence = {
        "recovery_eligible": True,
        "integrity_verified": True,
        "source_directory": str(source),
        "file_path": str(file_path),
    }
    network_event = SecurityEvent(
        event_type=SecurityEventType.NETWORK,
        severity=SecurityEventSeverity.CRITICAL,
        source="network-monitor",
        timestamp=None,
        payload=file_evidence,
    )
    unverified_file_event = SecurityEvent(
        event_type=SecurityEventType.FILE,
        severity=SecurityEventSeverity.CRITICAL,
        source="file-monitor",
        timestamp=None,
        payload={**file_evidence, "integrity_verified": False},
    )
    verified_file_event = SecurityEvent(
        event_type=SecurityEventType.FILE,
        severity=SecurityEventSeverity.HIGH,
        source="file-monitor",
        timestamp=None,
        payload=file_evidence,
    )

    assert policy.is_recovery_eligible(network_event) is False
    assert policy.is_recovery_eligible(unverified_file_event) is False
    assert policy.is_recovery_eligible(verified_file_event) is True


def test_backup_api_creates_verifies_restores_and_reports_job_status(
    backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(
        backup_routes,
        "SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )
    service = BackupRecoveryService(db)
    app = FastAPI()
    app.include_router(backup_routes.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_backup_recovery_service] = lambda: service

    with TestClient(app) as client:
        created = client.post(
            "/backups",
            json={"source_directory": str(source), "destination_directory": str(destination)},
        )
        assert created.status_code == 202
        backup_id = created.json()["id"]

        listed = client.get("/backups")
        assert listed.status_code == 200
        assert listed.json()[0]["status"] == "VERIFIED"
        assert listed.json()[0]["file_count"] == 1
        assert listed.json()[0]["trigger"] == "manual"

        verified = client.post(f"/backups/{backup_id}/verify")
        assert verified.status_code == 202
        assert client.get("/backups").json()[0]["status"] == "VERIFIED"

        recovery = client.post(f"/backups/{backup_id}/restore", json={})
        assert recovery.status_code == 202
        job_id = recovery.json()["id"]
        job_status = client.get(f"/recovery-jobs/{job_id}")
        assert job_status.status_code == 200
        assert job_status.json()["status"] == "COMPLETED"
        assert Path(job_status.json()["recovery_directory"]) == recovery_root / backup_id.replace("-", "")


def test_default_recovery_root_is_inferred_from_single_separate_allowed_root(
    backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    monkeypatch.setattr(settings, "RECOVERY_ROOT", "")
    service, backup = _create_verified_backup(db, user, root, source, destination)
    service = BackupRecoveryService(db, allowed_roots=[root, recovery_root])

    job = service.start_recovery(user=user, backup_id=backup.id)

    assert Path(job.recovery_directory) == recovery_root / backup.id.hex


def test_disallowed_recovery_root_is_rejected(backup_environment, monkeypatch: pytest.MonkeyPatch) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)
    outside_root = root.parent / "outside-recovery"
    monkeypatch.setattr(settings, "RECOVERY_ROOT", str(outside_root))

    with pytest.raises(ValueError, match="outside the configured BACKUP_ALLOWED_ROOTS"):
        service.start_recovery(user=user, backup_id=backup.id)


def test_recovery_override_must_remain_under_configured_root(backup_environment) -> None:
    db, user, root, source, destination, recovery_root = backup_environment
    service, backup = _create_verified_backup(db, user, root, source, destination)

    with pytest.raises(ValueError, match="inside the configured RECOVERY_ROOT"):
        service.start_recovery(
            user=user,
            backup_id=backup.id,
            recovery_directory=str(destination / "restore-elsewhere"),
        )
