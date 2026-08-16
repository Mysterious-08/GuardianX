from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.security_event import SecurityEvent, SecurityEventType, SecurityEventSeverity
from app.schemas.security_event import SecurityEventRequest, SecurityEventResponse


def test_valid_process_event_request_is_accepted() -> None:
    payload = {
        "event_type": SecurityEventType.PROCESS,
        "severity": SecurityEventSeverity.INFO,
        "source": "process_monitor",
        "timestamp": datetime.now(timezone.utc),
        "payload": {
            "process_name": "powershell.exe",
            "pid": 1234,
            "parent_pid": 1000,
            "command_line": "powershell.exe -enc ...",
        },
    }

    model = SecurityEventRequest(**payload)

    assert model.event_type == SecurityEventType.PROCESS
    assert model.payload["pid"] == 1234


def test_empty_source_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityEventRequest(
            event_type=SecurityEventType.PROCESS,
            severity=SecurityEventSeverity.INFO,
            source="",
            timestamp=datetime.now(timezone.utc),
            payload={"k": "v"},
        )


def test_invalid_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityEventRequest(
            event_type="BAD_TYPE",
            severity=SecurityEventSeverity.INFO,
            source="agent",
            timestamp=datetime.now(timezone.utc),
            payload={"k": "v"},
        )


def test_invalid_severity_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityEventRequest(
            event_type=SecurityEventType.FILE,
            severity="UNKNOWN",
            source="agent",
            timestamp=datetime.now(timezone.utc),
            payload={"k": "v"},
        )


def test_missing_payload_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityEventRequest(
            event_type=SecurityEventType.FILE,
            severity=SecurityEventSeverity.LOW,
            source="file_monitor",
            timestamp=datetime.now(timezone.utc),
        )


def test_response_schema_accepts_orm_objects() -> None:
    event = SecurityEvent(
        id=uuid4(),
        device_id=uuid4(),
        event_type=SecurityEventType.NETWORK,
        severity=SecurityEventSeverity.HIGH,
        source="network_monitor",
        timestamp=datetime.now(timezone.utc),
        payload={"remote_ip": "1.2.3.4", "remote_port": 443, "protocol": "TCP"},
        created_at=datetime.now(timezone.utc),
    )

    response = SecurityEventResponse.model_validate(event)

    assert response.event_type == SecurityEventType.NETWORK
    assert response.payload["remote_port"] == 443
    # Additional assertions to ensure attributes are preserved from the ORM object
    assert response.id == event.id
    assert response.device_id == event.device_id
    assert response.created_at == event.created_at
    assert response.source == event.source
    assert response.severity == event.severity


def test_request_schema_accepts_nested_payload() -> None:
    nested_payload = {
        "process": {
            "name": "powershell.exe",
            "pid": 1234,
            "parent": {"pid": 1000, "name": "explorer.exe"},
        },
        "command_line": "powershell.exe -enc ...",
        "metadata": {"user": "test-user", "flags": ["encoded", "suspicious"]},
    }

    model = SecurityEventRequest(
        event_type=SecurityEventType.PROCESS,
        severity=SecurityEventSeverity.MEDIUM,
        source="process_monitor",
        timestamp=datetime.now(timezone.utc),
        payload=nested_payload,
    )

    assert model.payload["process"]["name"] == "powershell.exe"
    assert model.payload["process"]["parent"]["pid"] == 1000
    assert model.payload["metadata"]["flags"] == ["encoded", "suspicious"]
