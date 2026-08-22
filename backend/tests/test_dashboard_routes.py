from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.security.dependencies import get_current_user


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


def _create_device(db: Session, user: User, *, status: DeviceStatus, last_seen: datetime | None) -> Device:
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


def test_dashboard_overview_returns_authenticated_user_data() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_route")
    _create_device(
        db,
        user,
        status=DeviceStatus.ONLINE,
        last_seen=datetime.now(timezone.utc),
    )
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/dashboard/overview")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "total_devices",
            "online_devices",
            "offline_devices",
            "registered_devices",
            "isolated_devices",
            "quarantined_devices",
            "devices_with_inventory",
            "devices_without_inventory",
            "total_security_events",
            "latest_device_activity",
        }
        assert body["total_devices"] == 1
        assert body["online_devices"] == 1
        assert body["latest_device_activity"] is not None
    finally:
        app.dependency_overrides.clear()


def test_dashboard_overview_is_scoped_to_authenticated_user() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_route_owner")
    other = _create_user(db, "dashboard_route_other")
    _create_device(db, user, status=DeviceStatus.REGISTERED, last_seen=None)
    _create_device(
        db,
        other,
        status=DeviceStatus.ONLINE,
        last_seen=datetime.now(timezone.utc),
    )
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/dashboard/overview")

        assert response.status_code == 200
        body = response.json()
        assert body["total_devices"] == 1
        assert body["registered_devices"] == 1
        assert body["online_devices"] == 0
    finally:
        app.dependency_overrides.clear()


def test_dashboard_overview_returns_zeroed_response_for_user_without_devices() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "dashboard_route_empty")
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/dashboard/overview")

        assert response.status_code == 200
        body = response.json()
        assert body["total_devices"] == 0
        assert body["online_devices"] == 0
        assert body["offline_devices"] == 0
        assert body["registered_devices"] == 0
        assert body["isolated_devices"] == 0
        assert body["quarantined_devices"] == 0
        assert body["devices_with_inventory"] == 0
        assert body["devices_without_inventory"] == 0
        assert body["total_security_events"] == 0
        assert body["latest_device_activity"] is None
    finally:
        app.dependency_overrides.clear()


def test_dashboard_overview_rejects_unauthenticated_access() -> None:
    client = TestClient(app)

    response = client.get("/dashboard/overview")

    assert response.status_code == 401
