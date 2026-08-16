"""Security event schemas for GuardianX API.

Pydantic v2 models describing incoming agent events and the persisted
SecurityEvent response shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.security_event import SecurityEventType, SecurityEventSeverity


SourceField = Annotated[
    str,
    Field(min_length=1, max_length=100, description="Component that generated the event."),
]


class SecurityEventRequest(BaseModel):
    """Payload submitted by a trusted GuardianX agent describing a security event."""

    event_type: SecurityEventType
    severity: SecurityEventSeverity
    source: SourceField
    timestamp: datetime
    payload: dict[str, Any]


class SecurityEventResponse(BaseModel):
    """Persisted security event record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: UUID
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    source: str
    timestamp: datetime
    payload: dict[str, Any]
    created_at: datetime
