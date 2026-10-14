from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_backup_recovery_service
from app.core.config import Settings, settings
from app.database.base import Base
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.security.dependencies import get_current_user
from app.api.routes.backups import router as backups_router
from app.services.backup import BackupRecoveryService
from app.services.backup_scheduler import (
    BackupScheduler,
    get_latest_persisted_scheduled_run,
    run_scheduled_backup,
    validate_scheduled_backup_configuration,
)


@pytest.fixture
def scheduled_backup_environment(tmp_path: Path):
    root = tmp_path / "allowed"
    source = root / "source"
    destination = root / "destination"
    source.mkdir(parents=True)
    destination.mkdir()
    (source / "scheduled.txt").write_text("scheduled backup data", encoding="utf-8")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        user = User(username="scheduler-user", email="scheduler@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        device = Device(
            agent_id=uuid4(),
            user_id=user.id,
            hostname="scheduler-host",
            operating_system="Windows",
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        yield db, user, device, root, source, destination
    engine.dispose()


def _scheduler(
    *,
    enabled: bool = True,
    source: str | None = "source",
    destination: str | None = "destination",
    device_agent_id: UUID | None = UUID(int=1),
    validate=None,
    execute=None,
) -> BackupScheduler:
    return BackupScheduler(
        enabled=enabled,
        interval_minutes=60,
        source_directory=source,
        destination_directory=destination,
        device_agent_id=device_agent_id,
        validate_configuration=validate or (lambda _source, _destination, _owner: None),
        run_backup=execute or (lambda _source, _destination, _owner: {"status": "VERIFIED"}),
    )


def test_scheduler_settings_are_disabled_and_validated_by_default() -> None:
    assert Settings.model_fields["BACKUP_SCHEDULER_ENABLED"].default is False
    assert Settings.model_fields["BACKUP_INTERVAL_MINUTES"].default == 60
    assert Settings.model_fields["BACKUP_SOURCE_DIRECTORY"].default is None
    assert Settings.model_fields["BACKUP_DESTINATION_DIRECTORY"].default is None
    assert Settings.model_fields["BACKUP_DEVICE_AGENT_ID"].default is None
    assert Settings(_env_file=None, BACKUP_INTERVAL_MINUTES=1).BACKUP_INTERVAL_MINUTES == 1
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKUP_INTERVAL_MINUTES=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, BACKUP_INTERVAL_MINUTES=10081)


def test_disabled_scheduler_does_not_validate_or_run_filesystem_work() -> None:
    calls: list[str] = []
    scheduler = _scheduler(
        enabled=False,
        validate=lambda *_: calls.append("validate"),
        execute=lambda *_: calls.append("execute") or {"status": "VERIFIED"},
    )

    async def run() -> None:
        await scheduler.start()
        assert await scheduler.run_once() is False
        await scheduler.stop()

    asyncio.run(run())

    assert scheduler.get_status()["state"] == "disabled"
    assert calls == []


def test_enabled_scheduler_reports_configured_interval_and_last_run() -> None:
    scheduler = _scheduler(execute=lambda *_: {"status": "VERIFIED"})

    async def run() -> dict[str, Any]:
        await scheduler.start()
        try:
            assert await scheduler.run_once()
            return scheduler.get_status()
        finally:
            await scheduler.stop()

    status = asyncio.run(run())

    assert status["enabled"] is True
    assert status["interval_minutes"] == 60
    assert status["last_run_at"] is not None
    assert status["last_outcome"] == "VERIFIED"


@pytest.mark.parametrize(
    ("source", "destination"),
    [(None, "destination"), ("source", None), (" ", "destination"), ("source", " ")],
)
def test_missing_scheduled_path_prevents_validation_and_backup(
    source: str | None,
    destination: str | None,
) -> None:
    calls: list[str] = []
    scheduler = _scheduler(
        source=source,
        destination=destination,
        validate=lambda *_: calls.append("validate"),
        execute=lambda *_: calls.append("execute") or {"status": "VERIFIED"},
    )

    async def run() -> None:
        await scheduler.start()
        assert await scheduler.run_once() is False

    asyncio.run(run())

    assert scheduler.get_status()["state"] == "misconfigured"
    assert calls == []


def test_invalid_scheduled_paths_leave_scheduler_misconfigured_without_running() -> None:
    calls: list[str] = []

    def reject_paths(_source: str, _destination: str, _owner: UUID) -> None:
        calls.append("validate")
        raise ValueError("The path is outside the configured BACKUP_ALLOWED_ROOTS.")

    scheduler = _scheduler(
        validate=reject_paths,
        execute=lambda *_: calls.append("execute") or {"status": "VERIFIED"},
    )

    async def run() -> bool:
        await scheduler.start()
        result = await scheduler.run_once()
        await scheduler.stop()
        return result

    assert asyncio.run(run()) is False
    assert scheduler.get_status()["state"] == "misconfigured"
    assert scheduler.get_status()["message"] == "The path is outside the configured BACKUP_ALLOWED_ROOTS."
    assert calls == ["validate"]


def test_missing_scheduler_device_prevents_startup_and_backup() -> None:
    calls: list[str] = []
    scheduler = _scheduler(
        device_agent_id=None,
        validate=lambda *_: calls.append("validate"),
        execute=lambda *_: calls.append("execute") or {"status": "VERIFIED"},
    )

    async def run() -> None:
        await scheduler.start()
        assert await scheduler.run_once() is False
        await scheduler.stop()

    asyncio.run(run())
    assert scheduler.get_status()["state"] == "misconfigured"
    assert "BACKUP_DEVICE_AGENT_ID" in scheduler.get_status()["message"]
    assert calls == []


def test_configured_scheduler_uses_existing_backup_and_verification_service(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, user, device, root, source, destination = scheduled_backup_environment
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(settings, "BACKUP_DEVICE_AGENT_ID", device.agent_id)
    monkeypatch.setattr(
        "app.services.backup_scheduler.SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )
    scheduler = _scheduler(
        source=str(source),
        destination=str(destination),
        device_agent_id=device.agent_id,
        validate=validate_scheduled_backup_configuration,
        execute=run_scheduled_backup,
    )

    async def run() -> bool:
        await scheduler.start()
        try:
            return await scheduler.run_once()
        finally:
            await scheduler.stop()

    assert asyncio.run(run()) is True
    status = scheduler.get_status()
    assert status["last_outcome"] == "VERIFIED"
    assert isinstance(status["backup_id"], UUID)
    result = get_latest_persisted_scheduled_run(str(source), str(destination), device.agent_id)
    assert result is not None
    assert result["backup_id"] == status["backup_id"]
    assert result["last_outcome"] == "VERIFIED"
    listed = BackupRecoveryService(db).list_backups(user=user)
    assert [backup.id for backup in listed] == [status["backup_id"]]
    assert listed[0].manifest["trigger"] == "scheduled"
    assert listed[0].device_id == device.id


def test_scheduled_snapshot_is_only_listed_for_configured_owner(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, owner, device, root, source, destination = scheduled_backup_environment
    other_user = User(username="another-user", email="another@example.com", hashed_password="x")
    db.add(other_user)
    db.commit()
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(settings, "BACKUP_DEVICE_AGENT_ID", device.agent_id)
    monkeypatch.setattr(
        "app.services.backup_scheduler.SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )

    result = run_scheduled_backup(str(source), str(destination), device.agent_id)
    service = BackupRecoveryService(db)
    assert result["status"] == "VERIFIED"
    assert [backup.id for backup in service.list_backups(user=owner)] == [result["backup_id"]]
    assert service.list_backups(user=other_user) == []

    app = FastAPI()
    app.include_router(backups_router)
    app.dependency_overrides[get_backup_recovery_service] = lambda: service
    authenticated_user = {"user": other_user}
    app.dependency_overrides[get_current_user] = lambda: authenticated_user["user"]
    with TestClient(app) as client:
        assert client.get("/backups").json() == []
        assert client.post(f"/backups/{result['backup_id']}/verify").status_code == 404
        assert client.post(f"/backups/{result['backup_id']}/restore", json={}).status_code == 404
        authenticated_user["user"] = owner
        listed = client.get("/backups").json()
        assert len(listed) == 1
        assert listed[0]["id"] == str(result["backup_id"])
        assert listed[0]["trigger"] == "scheduled"
    assert service.list_backups(user=owner)[0].device_id == device.id


def test_failed_scheduled_backup_is_listed_as_failed_not_verified(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, user, device, root, source, destination = scheduled_backup_environment
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(
        "app.services.backup_scheduler.SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )

    def fail_copy(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        raise OSError("simulated scheduled copy failure")

    monkeypatch.setattr(BackupRecoveryService, "_copy_source_tree", fail_copy)
    result = run_scheduled_backup(str(source), str(destination), device.agent_id)
    listed = BackupRecoveryService(db).list_backups(user=user)

    assert result["status"] == "FAILED"
    assert len(listed) == 1
    assert listed[0].status.value == "FAILED"
    assert "simulated scheduled copy failure" in (listed[0].error or "")
    assert listed[0].device_id == device.id
    from app.schemas.backup import BackupResponse

    assert BackupResponse.model_validate(listed[0]).trigger == "scheduled"
    persisted = get_latest_persisted_scheduled_run(str(source), str(destination), device.agent_id)
    assert persisted is not None
    assert persisted["last_outcome"] == "FAILED"


def test_failed_scheduled_run_is_reported_and_next_run_succeeds() -> None:
    outcomes: list[dict[str, Any] | Exception] = [
        {"backup_id": None, "status": "FAILED", "error": "test failure"},
        {"backup_id": UUID(int=1), "status": "VERIFIED", "error": None},
    ]

    def execute(_source: str, _destination: str, _owner: UUID) -> dict[str, Any]:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    scheduler = _scheduler(execute=execute)

    async def run() -> tuple[bool, bool]:
        await scheduler.start()
        try:
            first = await scheduler.run_once()
            assert scheduler.get_status()["last_outcome"] == "FAILED"
            assert scheduler.get_status()["error"] == "test failure"
            second = await scheduler.run_once()
            return first, second
        finally:
            await scheduler.stop()

    assert asyncio.run(run()) == (False, True)
    assert scheduler.get_status()["last_outcome"] == "VERIFIED"
    assert scheduler.get_status()["backup_id"] == UUID(int=1)


def test_concurrent_scheduler_runs_do_not_overlap() -> None:
    active_runs = 0
    maximum_active_runs = 0
    call_count = 0
    guard = threading.Lock()

    def execute(_source: str, _destination: str, _owner: UUID) -> dict[str, Any]:
        nonlocal active_runs, maximum_active_runs, call_count
        with guard:
            active_runs += 1
            call_count += 1
            maximum_active_runs = max(maximum_active_runs, active_runs)
        time.sleep(0.1)
        with guard:
            active_runs -= 1
        return {"status": "VERIFIED"}

    scheduler = _scheduler(execute=execute)

    async def run() -> tuple[bool, bool]:
        await scheduler.start()
        try:
            return await asyncio.gather(scheduler.run_once(), scheduler.run_once())
        finally:
            await scheduler.stop()

    assert sum(asyncio.run(run())) == 1
    assert call_count == 1
    assert maximum_active_runs == 1


def test_scheduler_starts_and_stops_without_waiting_for_interval() -> None:
    validation_count = 0

    def validate(_source: str, _destination: str, _owner: UUID) -> None:
        nonlocal validation_count
        validation_count += 1

    scheduler = _scheduler(validate=validate)
    scheduler.interval_minutes = 60

    async def run() -> tuple[str, bool]:
        await asyncio.gather(scheduler.start(), scheduler.start())
        assert validation_count == 1
        task = scheduler._task
        await scheduler.stop()
        return scheduler.get_status()["state"], bool(task and task.done())

    assert asyncio.run(run()) == ("stopped", True)


def test_scheduler_path_validation_rejects_disallowed_and_overlapping_paths(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _db, _user, _device, root, source, destination = scheduled_backup_environment
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))

    with pytest.raises(ValueError, match="outside"):
        validate_scheduled_backup_configuration(
            str(source),
            str(root.parent / "not-allowed"),
            UUID(int=1),
        )
    with pytest.raises(ValueError, match="overlap"):
        validate_scheduled_backup_configuration(
            str(source),
            str(source / "backups"),
            UUID(int=1),
        )


def test_scheduler_validation_requires_registered_active_device(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, _user, device, root, source, destination = scheduled_backup_environment
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(
        "app.services.backup_scheduler.SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )

    validate_scheduled_backup_configuration(str(source), str(destination), device.agent_id)
    with pytest.raises(ValueError, match="registered device with an active owner"):
        validate_scheduled_backup_configuration(str(source), str(destination), UUID(int=0))

    device.status = DeviceStatus.UNINSTALLED
    db.commit()
    with pytest.raises(ValueError, match="registered device with an active owner"):
        validate_scheduled_backup_configuration(str(source), str(destination), device.agent_id)


def test_configured_device_resolves_the_correct_owner_with_multiple_users(
    scheduled_backup_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, first_user, _first_device, root, source, destination = scheduled_backup_environment
    second_user = User(username="second-scheduler", email="second-scheduler@example.com", hashed_password="x")
    db.add(second_user)
    db.flush()
    second_device = Device(
        agent_id=uuid4(),
        user_id=second_user.id,
        hostname="second-scheduler-host",
        operating_system="Windows",
    )
    db.add(second_device)
    db.commit()
    db.refresh(second_device)
    monkeypatch.setattr(settings, "BACKUP_ALLOWED_ROOTS", str(root))
    monkeypatch.setattr(
        "app.services.backup_scheduler.SessionLocal",
        lambda: Session(bind=db.get_bind(), expire_on_commit=False),
    )

    validate_scheduled_backup_configuration(str(source), str(destination), second_device.agent_id)
    result = run_scheduled_backup(str(source), str(destination), second_device.agent_id)
    first_user_backups = BackupRecoveryService(db).list_backups(user=first_user)
    second_user_backups = BackupRecoveryService(db).list_backups(user=second_user)

    assert first_user_backups == []
    assert len(second_user_backups) == 1
    assert second_user_backups[0].id == result["backup_id"]
    assert second_user_backups[0].device_id == second_device.id


def test_scheduler_status_endpoint_is_authenticated_and_reports_state() -> None:
    scheduler = _scheduler(enabled=False)
    app = FastAPI()
    app.include_router(backups_router)
    app.state.backup_scheduler = scheduler

    with TestClient(app) as client:
        unauthenticated = client.get("/backups/scheduler/status")
        assert unauthenticated.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: User(
            username="scheduler-status",
            email="scheduler-status@example.com",
            hashed_password="x",
        )
        authenticated = client.get("/backups/scheduler/status")

    assert authenticated.status_code == 200
    assert authenticated.json()["state"] == "disabled"
    assert authenticated.json()["enabled"] is False


def test_fastapi_lifespan_starts_and_stops_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main as main_module

    class FakeScheduler:
        started = False
        stopped = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.stopped = True

    scheduler = FakeScheduler()
    application = FastAPI()
    monkeypatch.setattr(main_module, "check_database_connection", lambda: None)
    monkeypatch.setattr(main_module, "build_backup_scheduler", lambda: scheduler)

    async def run() -> None:
        async with main_module.lifespan(application):
            assert scheduler.started
            assert application.state.backup_scheduler is scheduler
        assert scheduler.stopped
        assert application.state.backup_scheduler is None

    asyncio.run(run())
