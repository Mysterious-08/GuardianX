from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.exceptions.device import DeviceNotFoundError, DeviceOwnershipError
from app.main import app
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.schemas.heartbeat import HeartbeatRequest
from app.security.dependencies import get_current_user
from app.services.device import DeviceService, OFFLINE_THRESHOLD


def _create_in_memory_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _create_user(db: Session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_device(
    db: Session,
    user: User,
    *,
    status: DeviceStatus = DeviceStatus.REGISTERED,
    last_seen: datetime | None = None,
) -> Device:
    device = Device(
        agent_id=uuid4(),
        user_id=user.id,
        hostname=f"{user.username}-host",
        operating_system="Windows",
        status=status,
        last_seen=last_seen,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _override_db(db: Session):
    def _get_db():
        try:
            yield db
        finally:
            pass

    return _get_db


def _override_user(user: User):
    def _get_user(token: str | None = None) -> User:
        return user

    return _get_user


def _configure_overrides(db: Session, user: User) -> None:
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)


def test_heartbeat_updates_last_seen_and_registered_becomes_online() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "heartbeat_registered")
    device = _create_device(db, user)
    service = DeviceService(db)
    before = datetime.now(timezone.utc)

    response = service.send_heartbeat(
        user=user,
        heartbeat=HeartbeatRequest(agent_id=device.agent_id),
    )

    db.refresh(device)
    assert response.status == "OK"
    assert device.last_seen is not None
    assert device.last_seen.replace(tzinfo=timezone.utc) >= before
    assert device.status is DeviceStatus.ONLINE


def test_offline_device_becomes_online_after_heartbeat() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "heartbeat_offline")
    device = _create_device(db, user, status=DeviceStatus.OFFLINE, last_seen=datetime.now(timezone.utc) - timedelta(minutes=5))

    DeviceService(db).send_heartbeat(
        user=user,
        heartbeat=HeartbeatRequest(agent_id=device.agent_id),
    )

    db.refresh(device)
    assert device.status is DeviceStatus.ONLINE


def test_recent_heartbeat_keeps_device_online() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "recent")
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    device = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=now - timedelta(seconds=89))

    result = DeviceService(db).evaluate_device_status(device=device, now=now)

    assert result.status is DeviceStatus.ONLINE
    db.refresh(device)
    assert device.status is DeviceStatus.ONLINE


def test_stale_device_becomes_offline_and_persists_status() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "stale")
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    last_seen = now - OFFLINE_THRESHOLD - timedelta(seconds=1)
    device = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=last_seen)

    devices = DeviceService(db).get_devices_by_user(user=user, now=now)

    assert devices[0].status is DeviceStatus.OFFLINE
    db.expire_all()
    persisted = db.scalar(select(Device).where(Device.id == device.id))
    assert persisted is not None
    assert persisted.status is DeviceStatus.OFFLINE
    assert persisted.last_seen.replace(tzinfo=timezone.utc) == last_seen


def test_device_without_last_seen_remains_registered() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "never_seen")
    device = _create_device(db, user, status=DeviceStatus.REGISTERED, last_seen=None)

    result = DeviceService(db).evaluate_device_status(
        device=device,
        now=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert result.status is DeviceStatus.REGISTERED
    assert result.last_seen is None


def test_protected_device_states_are_not_changed_by_availability_evaluation() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "protected")
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)

    for status in (DeviceStatus.ISOLATED, DeviceStatus.QUARANTINED, DeviceStatus.UNINSTALLED):
        device = _create_device(
            db,
            user,
            status=status,
            last_seen=now - OFFLINE_THRESHOLD - timedelta(minutes=1),
        )
        DeviceService(db).evaluate_device_status(device=device, now=now)
        assert device.status is status


def test_device_ownership_validation_remains_correct() -> None:
    db = _create_in_memory_session()
    owner = _create_user(db, "status_owner")
    other = _create_user(db, "status_other")
    device = _create_device(db, owner)

    with pytest.raises(DeviceOwnershipError, match="does not own"):
        DeviceService(db).send_heartbeat(
            user=other,
            heartbeat=HeartbeatRequest(agent_id=device.agent_id),
        )


def test_unknown_device_behavior_remains_correct() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "unknown")

    with pytest.raises(DeviceNotFoundError, match="Device not found"):
        DeviceService(db).send_heartbeat(
            user=user,
            heartbeat=HeartbeatRequest(agent_id=uuid4()),
        )


def test_multiple_devices_are_evaluated_independently() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "multiple")
    now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    recent = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=now - timedelta(seconds=30))
    stale = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=now - timedelta(seconds=120))
    never_seen = _create_device(db, user, status=DeviceStatus.REGISTERED, last_seen=None)

    devices = DeviceService(db).get_devices_by_user(user=user, now=now)
    statuses = {device.id: device.status for device in devices}

    assert statuses[recent.id] is DeviceStatus.ONLINE
    assert statuses[stale.id] is DeviceStatus.OFFLINE
    assert statuses[never_seen.id] is DeviceStatus.REGISTERED


def test_device_list_endpoint_returns_status_and_last_seen() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "list_status")
    now = datetime.now(timezone.utc)
    device = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=now)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/devices")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["devices"][0]["id"] == str(device.id)
        assert body["devices"][0]["status"] == "ONLINE"
        assert body["devices"][0]["last_seen"] is not None
    finally:
        app.dependency_overrides.clear()


def test_device_list_endpoint_returns_only_owned_devices() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "list_owner")
    other = _create_user(db, "list_other")
    owned = _create_device(db, user, status=DeviceStatus.REGISTERED)
    _create_device(db, other, status=DeviceStatus.ONLINE, last_seen=datetime.now(timezone.utc))
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/devices")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["devices"][0]["id"] == str(owned.id)
    finally:
        app.dependency_overrides.clear()


def test_existing_heartbeat_response_contract_remains_intact() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "contract")
    device = _create_device(db, user)

    response = DeviceService(db).send_heartbeat(
        user=user,
        heartbeat=HeartbeatRequest(agent_id=device.agent_id),
    )

    assert response.status == "OK"
    assert response.next_heartbeat_in == 30
    assert response.server_time.tzinfo is not None
