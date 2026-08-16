from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.security_event import SecurityEvent
from app.models.device import Device
from app.models.user import User
from app.schemas.security_event import SecurityEventRequest
from app.exceptions.device import DeviceNotFoundError, DeviceOwnershipError


class SecurityEventService:
    """Service responsible for SecurityEvent persistence and queries.

    Framework-agnostic and uses SQLAlchemy session injected via the
    constructor. Methods follow the project's transaction patterns.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_events_by_device_id(self, *, device_id: UUID) -> list[SecurityEvent]:
        """Return a list of SecurityEvent for the device ordered by timestamp desc."""
        statement = select(SecurityEvent).where(SecurityEvent.device_id == device_id).order_by(
            SecurityEvent.timestamp.desc()
        )
        return self.db.scalars(statement).all()

    def create_event(self, *, user: User, agent_id: UUID, event_data: SecurityEventRequest) -> SecurityEvent:
        """Create and persist a SecurityEvent for the device identified by agent_id.

        Enforces device existence and ownership. Uses event_data.timestamp as the
        event occurrence time and preserves the JSON payload.
        """
        # Find device by agent_id
        device_stmt = select(Device).where(Device.agent_id == agent_id)
        device = self.db.scalar(device_stmt)

        if device is None:
            raise DeviceNotFoundError("Device not found.")

        if device.user_id != user.id:
            raise DeviceOwnershipError("Authenticated user does not own the device.")

        event = SecurityEvent(
            device_id=device.id,
            event_type=event_data.event_type,
            severity=event_data.severity,
            source=event_data.source,
            timestamp=event_data.timestamp,
            payload=event_data.payload,
        )

        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except Exception:
            self.db.rollback()
            raise
