from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.device import Device


class DeviceInventory(Base):
    """Persistence-only inventory snapshot for a GuardianX endpoint device."""

    __tablename__ = "device_inventories"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
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
    cpu_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    cpu_cores: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    total_memory_mb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    total_disk_mb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    local_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    mac_address: Mapped[str | None] = mapped_column(
        String(17),
        nullable=True,
    )
    cpu_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    ram_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    disk_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    network_interfaces: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    operating_system_info: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
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

    device: Mapped["Device"] = relationship(back_populates="inventory")
