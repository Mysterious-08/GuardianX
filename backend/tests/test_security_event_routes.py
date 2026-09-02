from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.security.dependencies import get_current_user
from app.models.user import User
from app.models.device import Device
from app.models.security_event import SecurityEvent, SecurityEventSeverity, SecurityEventType
from app.agent.collectors.network import CompletedFlowRecord
from app.agent.transport.events import SecurityEventTransport
from app.ml.inference import GuardianXInference


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


def _configure_overrides(db, user) -> None:
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)


def _create_event(db, device: Device, timestamp: datetime, *, source: str = "test") -> SecurityEvent:
    event = SecurityEvent(
        device_id=device.id,
        event_type=SecurityEventType.PROCESS,
        severity=SecurityEventSeverity.INFO,
        source=source,
        timestamp=timestamp,
        payload={"source": source},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_network_flow_transport_post_contains_guardianx_v2_ml_detection_and_persists_event() -> None:
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

    _configure_overrides(db, user)
    client = TestClient(app)

    record = CompletedFlowRecord(
        collector_scope="integration-test",
        protocol="TCP",
        source_ip="10.0.0.1",
        source_port=4000,
        destination_ip="10.0.0.2",
        destination_port=443,
        forward_source_ip="10.0.0.1",
        forward_source_port=4000,
        forward_destination_ip="10.0.0.2",
        forward_destination_port=443,
        flow_start_timestamp=1.0,
        flow_end_timestamp=3.0,
        flow_duration=2.0,
        forward_packet_count=1,
        backward_packet_count=0,
        forward_byte_count=10,
        backward_byte_count=0,
        packet_rate=0.5,
        byte_rate=5.0,
        forward_backward_packet_ratio=None,
        quality_status="valid",
        missing_fields=(),
        model_ready=True,
    )

    inference = GuardianXInference(
        "D:/VScode/Projects/GuardianX/backend/ml/models/guardianx_isolation_forest_v2.joblib"
    )
    expected = inference.predict(record.to_guardianx_v2_feature_vector())
    expected_ml = {
        "model": "guardianx_isolation_forest_v2",
        "schema_version": "v2",
        "prediction": expected.prediction,
        "anomaly_score": expected.anomaly_score,
    }

    def fake_post(url: str, *, json: object, headers: dict[str, str], timeout: float):
        assert url == f"http://testserver/devices/{agent_id}/events"
        response = client.post(
            f"/devices/{agent_id}/events",
            json=json,
            headers=headers,
        )
        return httpx.Response(
            status_code=response.status_code,
            json=response.json(),
            request=httpx.Request("POST", url),
        )

    try:
        with patch("app.agent.transport.events.httpx.post", side_effect=fake_post):
            transport = SecurityEventTransport(
                base_url="http://testserver",
                agent_id=agent_id,
                access_token="token",
                inference=inference,
            )
            transport.publish(record)

        response = client.get(f"/devices/{agent_id}/events")
        assert response.status_code == 200
        payload = response.json()[0]["payload"]
        assert payload["flow_duration"] == 2.0
        assert payload["forward_packet_count"] == 1
        assert payload["backward_packet_count"] == 0
        assert payload["ml_detection"] == expected_ml

        persisted = db.scalar(
            select(SecurityEvent).where(SecurityEvent.device_id == device.id)
        )
        assert persisted is not None
        assert persisted.payload["ml_detection"] == expected_ml
    finally:
        app.dependency_overrides.clear()


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


def test_get_all_security_events_returns_owned_events_newest_first() -> None:
    db = _create_in_memory_session()
    owner = User(username="all_events_owner", email="all_events_owner@example.com", hashed_password="x")
    other = User(username="all_events_other", email="all_events_other@example.com", hashed_password="x")
    db.add_all([owner, other])
    db.commit()
    db.refresh(owner)
    db.refresh(other)
    owned_device = Device(agent_id=uuid4(), user_id=owner.id, hostname="owned", operating_system="Windows")
    other_device = Device(agent_id=uuid4(), user_id=other.id, hostname="other", operating_system="Windows")
    db.add_all([owned_device, other_device])
    db.commit()
    db.refresh(owned_device)
    db.refresh(other_device)
    newer = _create_event(db, owned_device, datetime(2026, 8, 16, 11, 0, tzinfo=timezone.utc), source="newer")
    _create_event(db, owned_device, datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc), source="older")
    _create_event(db, other_device, datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc), source="excluded")
    _configure_overrides(db, owner)
    client = TestClient(app)

    try:
        response = client.get("/security-events")

        assert response.status_code == 200
        events = response.json()
        assert [event["source"] for event in events] == ["newer", "older"]
        assert events[0]["id"] == str(newer.id)
        assert events[0]["device_id"] == str(owned_device.id)
    finally:
        app.dependency_overrides.clear()


def test_get_all_security_events_returns_empty_list_when_no_events_exist() -> None:
    db = _create_in_memory_session()
    user = User(username="empty_events", email="empty_events@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get("/security-events")

        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_get_all_security_events_requires_authentication() -> None:
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/security-events")

    assert response.status_code == 401
