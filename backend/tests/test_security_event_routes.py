from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.security.dependencies import get_current_user
from app.models.user import User
from app.models.device import Device


def _create_in_memory_session():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _override_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass

    return _get_db


def _override_user(user):
    def _get_user(token: str | None = None):
        return user

    return _get_user


def test_create_event_endpoint_success() -> None:
    db = _create_in_memory_session()

    user = User(username="routealice", email="routealice@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)

    client = TestClient(app)

    try:
        payload = {
            "event_type": "PROCESS",
            "severity": "INFO",
            "source": "procmon",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"process_name": "test.exe"},
        }

        resp = client.post(f"/devices/{agent_id}/events", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body, dict)
        assert body.get("id") is not None
        assert body.get("device_id") == str(device.id)
        assert body.get("event_type") == "PROCESS"
        assert body.get("severity") == "INFO"
        assert body.get("source") == "procmon"
        assert body.get("timestamp") is not None
        assert body.get("payload", {}).get("process_name") == "test.exe"
    finally:
        app.dependency_overrides.clear()


def test_get_events_endpoint_success() -> None:
    db = _create_in_memory_session()

    user = User(username="routebob", email="routebob@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)

    client = TestClient(app)

    try:
        older_ts = datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc).isoformat()
        newer_ts = datetime(2026, 8, 16, 11, 0, tzinfo=timezone.utc).isoformat()

        payload1 = {
            "event_type": "PROCESS",
            "severity": "LOW",
            "source": "procmon",
            "timestamp": older_ts,
            "payload": {"i": 1},
        }

        payload2 = {
            "event_type": "PROCESS",
            "severity": "LOW",
            "source": "procmon",
            "timestamp": newer_ts,
            "payload": {"i": 2},
        }

        r1 = client.post(f"/devices/{agent_id}/events", json=payload1)
        assert r1.status_code == 201
        r2 = client.post(f"/devices/{agent_id}/events", json=payload2)
        assert r2.status_code == 201

        get_resp = client.get(f"/devices/{agent_id}/events")
        assert get_resp.status_code == 200
        events = get_resp.json()
        assert isinstance(events, list)
        assert len(events) >= 2

        # newest first
        ts0 = datetime.fromisoformat(events[0]["timestamp"])
        ts1 = datetime.fromisoformat(events[1]["timestamp"])
        assert ts0 >= ts1
    finally:
        app.dependency_overrides.clear()


def test_create_event_unknown_agent_returns_404() -> None:
    db = _create_in_memory_session()
    user = User(username="routecarol", email="routecarol@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)

    client = TestClient(app)

    try:
        payload = {
            "event_type": "PROCESS",
            "severity": "INFO",
            "source": "procmon",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"process_name": "test.exe"},
        }

        resp = client.post(f"/devices/{uuid4()}/events", json=payload)
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_events_unknown_agent_returns_404() -> None:
    db = _create_in_memory_session()
    user = User(username="routedave", email="routedave@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)

    client = TestClient(app)

    try:
        resp = client.get(f"/devices/{uuid4()}/events")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_event_ownership_violation_returns_403() -> None:
    db = _create_in_memory_session()

    owner = User(username="owner", email="owner@example.com", hashed_password="x")
    other = User(username="other", email="other@example.com", hashed_password="x")
    db.add_all([owner, other])
    db.commit()
    db.refresh(owner)
    db.refresh(other)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=owner.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(other)

    client = TestClient(app)

    try:
        payload = {
            "event_type": "PROCESS",
            "severity": "INFO",
            "source": "procmon",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {"process_name": "test.exe"},
        }

        resp = client.post(f"/devices/{agent_id}/events", json=payload)
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_get_events_ownership_violation_returns_403() -> None:
    db = _create_in_memory_session()

    owner = User(username="owner2", email="owner2@example.com", hashed_password="x")
    other = User(username="other2", email="other2@example.com", hashed_password="x")
    db.add_all([owner, other])
    db.commit()
    db.refresh(owner)
    db.refresh(other)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=owner.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(other)

    client = TestClient(app)

    try:
        resp = client.get(f"/devices/{agent_id}/events")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_invalid_payload_returns_422() -> None:
    db = _create_in_memory_session()
    user = User(username="routeeve", email="routeeve@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)

    client = TestClient(app)

    try:
        # Missing required fields
        resp = client.post(f"/devices/{agent_id}/events", json={"foo": "bar"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
