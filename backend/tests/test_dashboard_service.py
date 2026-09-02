from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.device import Device, DeviceStatus
from app.models.device_inventory import DeviceInventory
from app.models.security_event import (
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
)
from app.models.user import User
from app.services.dashboard import DashboardService


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
        hostname=f"{user.username}-{uuid4().hex[:6]}",
        operating_system="Windows",
        status=status,
        last_seen=last_seen,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _create_event(db: Session, device: Device, timestamp: datetime) -> SecurityEvent:
    event = SecurityEvent(
        device_id=device.id,
        event_type=SecurityEventType.PROCESS,
        severity=SecurityEventSeverity.INFO,
        source="dashboard-test",
        timestamp=timestamp,
        payload={"test": True},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_zero_device_user_returns_zeroed_overview() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_empty")

    result = DashboardService(db).get_overview(user=user)

    assert result.total_devices == 0
    assert result.online_devices == 0
    assert result.offline_devices == 0
    assert result.registered_devices == 0
    assert result.isolated_devices == 0
    assert result.quarantined_devices == 0
    assert result.devices_with_inventory == 0
    assert result.devices_without_inventory == 0
    assert result.total_security_events == 0
    assert result.latest_device_activity is None


def test_overview_counts_device_statuses() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_statuses")
    now = datetime.now(timezone.utc)
    _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=now)
    _create_device(db, user, status=DeviceStatus.OFFLINE, last_seen=now - timedelta(minutes=5))
    _create_device(db, user, status=DeviceStatus.REGISTERED)
    _create_device(db, user, status=DeviceStatus.ISOLATED, last_seen=now)
    _create_device(db, user, status=DeviceStatus.QUARANTINED, last_seen=now)

    result = DashboardService(db).get_overview(user=user)

    assert result.total_devices == 5
    assert result.online_devices == 1
    assert result.offline_devices == 1
    assert result.registered_devices == 1
    assert result.isolated_devices == 1
    assert result.quarantined_devices == 1


def test_overview_counts_only_never_seen_registered_devices_as_uninitialized() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_uninitialized")
    now = datetime.now(timezone.utc)
    _create_device(db, user, status=DeviceStatus.REGISTERED)
    _create_device(db, user, status=DeviceStatus.REGISTERED, last_seen=now)

    result = DashboardService(db).get_overview(user=user)

    assert result.registered_devices == 1
    assert result.online_devices == 1


def test_overview_counts_inventory_and_missing_inventory() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_inventory")
    device_with_inventory = _create_device(db, user)
    _create_device(db, user)
    db.add(
        DeviceInventory(
            device_id=device_with_inventory.id,
            hostname="inventory-host",
            operating_system="Windows",
        )
    )
    db.commit()

    result = DashboardService(db).get_overview(user=user)

    assert result.devices_with_inventory == 1
    assert result.devices_without_inventory == 1


def test_overview_counts_security_events_for_authenticated_user() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_events")
    other = _create_user(db, "dashboard_other_events")
    device = _create_device(db, user)
    other_device = _create_device(db, other)
    timestamp = datetime.now(timezone.utc)
    _create_event(db, device, timestamp)
    _create_event(db, device, timestamp + timedelta(seconds=1))
    _create_event(db, other_device, timestamp + timedelta(seconds=2))

    result = DashboardService(db).get_overview(user=user)

    assert result.total_security_events == 2


def test_overview_returns_latest_device_activity() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_activity")
    latest = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=latest - timedelta(minutes=1))
    _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=latest)
    _create_device(db, user)

    result = DashboardService(db).get_overview(user=user)

    assert result.latest_device_activity == latest.replace(tzinfo=None)


def test_overview_excludes_other_users_devices_inventory_and_events() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_scoped")
    other = _create_user(db, "dashboard_unscoped")
    owned = _create_device(db, user, status=DeviceStatus.ONLINE, last_seen=datetime.now(timezone.utc))
    excluded = _create_device(db, other, status=DeviceStatus.OFFLINE)
    db.add(
        DeviceInventory(
            device_id=owned.id,
            hostname="owned-inventory",
            operating_system="Windows",
        )
    )
    db.add(
        DeviceInventory(
            device_id=excluded.id,
            hostname="excluded-inventory",
            operating_system="Windows",
        )
    )
    db.commit()
    _create_event(db, owned, datetime.now(timezone.utc))
    _create_event(db, excluded, datetime.now(timezone.utc))

    result = DashboardService(db).get_overview(user=user)

    assert result.total_devices == 1
    assert result.devices_with_inventory == 1
    assert result.devices_without_inventory == 0
    assert result.total_security_events == 1
