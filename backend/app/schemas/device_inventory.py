"""Device inventory schemas for the GuardianX API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

HostnameField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        description="Host name reported by the endpoint device.",
    ),
]

OperatingSystemField = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        description="Operating system reported by the endpoint device.",
    ),
]

VersionField = Annotated[
    str | None,
    Field(
        default=None,
        max_length=50,
        description="Optional version string for the operating system, architecture, or agent.",
    ),
]

CpuModelField = Annotated[
    str | None,
    Field(
        default=None,
        max_length=255,
        description="Optional CPU model reported by the endpoint device.",
    ),
]

PositiveIntegerField = Annotated[
    int | None,
    Field(
        default=None,
        gt=0,
        description="Optional positive integer value reported by the endpoint device.",
    ),
]

LocalIpField = Annotated[
    str | None,
    Field(
        default=None,
        max_length=45,
        description="Optional local IP address reported by the endpoint device.",
    ),
]

MacAddressField = Annotated[
    str | None,
    Field(
        default=None,
        max_length=17,
        description="Optional MAC address reported by the endpoint device.",
    ),
]


class DeviceInventoryRequest(BaseModel):
    """Payload submitted by a trusted GuardianX agent with inventory details."""

    hostname: HostnameField
    operating_system: OperatingSystemField
    os_version: VersionField = None
    architecture: VersionField = None
    agent_version: VersionField = None
    cpu_model: CpuModelField = None
    cpu_cores: PositiveIntegerField = None
    total_memory_mb: PositiveIntegerField = None
    total_disk_mb: PositiveIntegerField = None
    local_ip: LocalIpField = None
    mac_address: MacAddressField = None


class DeviceInventoryResponse(BaseModel):
    """Persisted device inventory record returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: UUID
    hostname: str
    operating_system: str
    os_version: str | None = None
    architecture: str | None = None
    agent_version: str | None = None
    cpu_model: str | None = None
    cpu_cores: int | None = None
    total_memory_mb: int | None = None
    total_disk_mb: int | None = None
    local_ip: str | None = None
    mac_address: str | None = None
    created_at: datetime
    updated_at: datetime
