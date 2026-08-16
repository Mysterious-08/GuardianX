from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.device_inventory import DeviceInventory
    from app.models.user import User
    from app.models.security_event import SecurityEvent


class DeviceStatus(PyEnum):
    """Lifecycle state for a GuardianX endpoint device."""

    REGISTERED = "REGISTERED"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ISOLATED = "ISOLATED"
    QUARANTINED = "QUARANTINED"
    UNINSTALLED = "UNINSTALLED"


class Device(Base):
    """Persistence-only device record for GuardianX."""

    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    operating_system: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    os_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    architecture: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    agent_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    status: Mapped[DeviceStatus] = mapped_column(
        SQLAlchemyEnum(DeviceStatus, native_enum=False),
        nullable=False,
        default=DeviceStatus.REGISTERED,
        server_default="REGISTERED",
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship(
        back_populates="devices",
    )
    inventory: Mapped["DeviceInventory | None"] = relationship(
        back_populates="device",
        uselist=False,
        cascade="all, delete-orphan",
    )
    security_events: Mapped[list["SecurityEvent"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )
