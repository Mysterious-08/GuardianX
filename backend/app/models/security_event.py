from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SecurityEventType(PyEnum):
    PROCESS = "PROCESS"
    FILE = "FILE"
    REGISTRY = "REGISTRY"
    NETWORK = "NETWORK"
    SYSTEM = "SYSTEM"


class SecurityEventSeverity(PyEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


if TYPE_CHECKING:
    from app.models.device import Device


class SecurityEvent(Base):
    """Persistence-only security event record for GuardianX endpoints.

    This table stores normalized, schema-flexible events produced by endpoint
    components (process monitors, file monitors, network monitors, etc.). The
    `payload` JSON column carries event-specific attributes so no specialized
    columns are required for v1.
    """

    __tablename__ = "security_events"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[SecurityEventType] = mapped_column(
        SQLAlchemyEnum(SecurityEventType, name="securityeventtype", native_enum=False),
        nullable=False,
        index=True,
    )
    severity: Mapped[SecurityEventSeverity] = mapped_column(
        SQLAlchemyEnum(SecurityEventSeverity, name="securityeventseverity", native_enum=False),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    device: Mapped["Device"] = relationship(back_populates="security_events")
