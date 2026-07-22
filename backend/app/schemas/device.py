"""Device schemas for the GuardianX API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.device import DeviceStatus


HostnameField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        description="Host name assigned to the endpoint device.",
    ),
]

DeviceNameField = Annotated[
    str,
    Field(
        max_length=255,
        description="Optional user-facing device name.",
    ),
]

OperatingSystemField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="Operating system name reported by the endpoint.",
    ),
]

VersionField = Annotated[
    str,
    Field(
        max_length=50,
        description="Optional version string for OS, architecture, or agent.",
    ),
]


class DeviceRegisterRequest(BaseModel):
    """Payload used to register a new GuardianX device."""

    agent_id: UUID
    device_name: DeviceNameField | None = None
    hostname: HostnameField
    operating_system: OperatingSystemField
    os_version: VersionField | None = None
    architecture: VersionField | None = None
    agent_version: VersionField | None = None


class DeviceUpdate(BaseModel):
    """Payload used to update mutable GuardianX device fields."""

    device_name: DeviceNameField | None = None
    hostname: HostnameField | None = None
    operating_system: OperatingSystemField | None = None
    os_version: VersionField | None = None
    architecture: VersionField | None = None
    agent_version: VersionField | None = None


class DeviceResponse(BaseModel):
    """API representation of a GuardianX device record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    device_name: str | None = None
    hostname: str
    operating_system: str
    os_version: str | None = None
    architecture: str | None = None
    agent_version: str | None = None
    status: DeviceStatus
    created_at: datetime
    updated_at: datetime


class DeviceSummary(BaseModel):
    """Concise API summary for a GuardianX device."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_name: str | None = None
    hostname: str
    status: DeviceStatus
    last_seen: datetime | None = None


class DeviceListResponse(BaseModel):
    """List response for GuardianX devices."""

    model_config = ConfigDict(from_attributes=True)

    devices: list[DeviceSummary]
    total: int


class DeviceDetailResponse(DeviceResponse):
    """Detailed API response for a single GuardianX device."""
