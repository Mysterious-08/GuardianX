from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.user import User
from app.models.device import Device
import pytest

from app.models.security_event import SecurityEvent, SecurityEventType, SecurityEventSeverity
from app.schemas.security_event import SecurityEventRequest
from app.services.security_event import SecurityEventService
from app.exceptions.device import DeviceNotFoundError, DeviceOwnershipError


def _create_in_memory_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_create_event_creates_record_and_persists() -> None:
    db = _create_in_memory_session()

    user = User(username="alice", email="alice@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = SecurityEventService(db)

    ts = datetime.now(timezone.utc)
    payload = {"process_name": "powershell.exe", "pid": 1234}

    req = SecurityEventRequest(
        event_type="PROCESS",
        severity="INFO",
        source="process_monitor",
        timestamp=ts,
        payload=payload,
    )

    result = service.create_event(user=user, agent_id=agent_id, event_data=req)

    assert result.device_id == device.id
    assert result.event_type.name == "PROCESS"
    assert result.severity.name == "INFO"
    assert result.source == "process_monitor"
    assert result.timestamp.replace(tzinfo=timezone.utc) == ts
    assert result.payload["pid"] == 1234
    assert result.id is not None

    # Ensure persistence
    stmt = select(SecurityEvent).where(SecurityEvent.device_id == device.id)
    persisted = db.scalar(stmt)
    assert persisted is not None


def test_create_event_preserves_event_timestamp() -> None:
    db = _create_in_memory_session()

    user = User(username="bob", email="bob@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = SecurityEventService(db)

    submitted_ts = datetime(2026, 8, 16, 10, 30, tzinfo=timezone.utc)

    req = SecurityEventRequest(
        event_type="PROCESS",
        severity="LOW",
        source="process_monitor",
        timestamp=submitted_ts,
        payload={"k": "v"},
    )

    result = service.create_event(user=user, agent_id=agent_id, event_data=req)
    assert result.timestamp.replace(tzinfo=timezone.utc) == submitted_ts


def test_create_event_raises_for_unknown_device() -> None:
    db = _create_in_memory_session()

    user = User(username="carol", email="carol@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    service = SecurityEventService(db)

    with pytest.raises(DeviceNotFoundError):
        service.create_event(user=user, agent_id=uuid4(), event_data=SecurityEventRequest(event_type="PROCESS", severity="INFO", source="agent", timestamp=datetime.now(timezone.utc), payload={"k": "v"}))


def test_create_event_raises_on_ownership_violation() -> None:
    db = _create_in_memory_session()

    owner = User(username="owner", email="owner@example.com", hashed_password="x")
    attacker = User(username="attacker", email="attacker@example.com", hashed_password="x")
    db.add_all([owner, attacker])
    db.commit()
    db.refresh(owner)
    db.refresh(attacker)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=owner.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = SecurityEventService(db)

    with pytest.raises(DeviceOwnershipError):
        service.create_event(user=attacker, agent_id=agent_id, event_data=SecurityEventRequest(event_type="PROCESS", severity="INFO", source="agent", timestamp=datetime.now(timezone.utc), payload={"k": "v"}))


def test_get_events_by_device_id_returns_events_newest_first() -> None:
    db = _create_in_memory_session()

    user = User(username="dave", email="dave@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    # Create multiple events with different timestamps
    older = SecurityEvent(device_id=device.id, event_type=SecurityEventType.PROCESS, severity=SecurityEventSeverity.LOW, source="s", timestamp=datetime(2026, 8, 16, 9, 0, tzinfo=timezone.utc), payload={"i": 1})
    newer = SecurityEvent(device_id=device.id, event_type=SecurityEventType.PROCESS, severity=SecurityEventSeverity.LOW, source="s", timestamp=datetime(2026, 8, 16, 11, 0, tzinfo=timezone.utc), payload={"i": 2})
    db.add_all([older, newer])
    db.commit()

    service = SecurityEventService(db)

    results = service.get_events_by_device_id(device_id=device.id)
    assert len(results) == 2
    assert results[0].timestamp > results[1].timestamp


def test_get_events_by_device_id_returns_empty_list_when_no_events() -> None:
    db = _create_in_memory_session()

    user = User(username="erin", email="erin@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = SecurityEventService(db)
    results = service.get_events_by_device_id(device_id=device.id)
    assert results == []


def test_service_preserves_nested_payloads() -> None:
    db = _create_in_memory_session()

    user = User(username="frank", email="frank@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = SecurityEventService(db)

    nested = {
        "process": {"name": "powershell.exe", "pid": 1234, "parent": {"pid": 1000, "name": "explorer.exe"}},
        "metadata": {"flags": ["encoded", "suspicious"]},
    }

    req = SecurityEventRequest(event_type="PROCESS", severity="MEDIUM", source="process_monitor", timestamp=datetime.now(timezone.utc), payload=nested)

    result = service.create_event(user=user, agent_id=agent_id, event_data=req)

    assert result.payload["process"]["name"] == "powershell.exe"
    assert result.payload["process"]["parent"]["pid"] == 1000
    assert result.payload["metadata"]["flags"] == ["encoded", "suspicious"]


def test_get_events_by_agent_id_returns_events_for_owner() -> None:
    db = _create_in_memory_session()

    user = User(username="gina", email="gina@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    event = SecurityEvent(device_id=device.id, event_type=SecurityEventType.PROCESS, severity=SecurityEventSeverity.LOW, source="s", timestamp=datetime.now(timezone.utc), payload={})
    db.add(event)
    db.commit()

    service = SecurityEventService(db)
    results = service.get_events_by_agent_id(user=user, agent_id=agent_id)
    assert len(results) == 1


def test_get_events_by_agent_id_raises_for_unknown_agent() -> None:
    db = _create_in_memory_session()

    user = User(username="hank", email="hank@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    service = SecurityEventService(db)

    with pytest.raises(DeviceNotFoundError):
        service.get_events_by_agent_id(user=user, agent_id=uuid4())


def test_get_events_by_agent_id_raises_on_ownership_violation() -> None:
    db = _create_in_memory_session()

    owner = User(username="owner2", email="owner2@example.com", hashed_password="x")
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

    service = SecurityEventService(db)

    with pytest.raises(DeviceOwnershipError):
        service.get_events_by_agent_id(user=other, agent_id=agent_id)
