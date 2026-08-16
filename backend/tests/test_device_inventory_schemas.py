from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.device_inventory import DeviceInventory
from app.schemas.device_inventory import DeviceInventoryRequest, DeviceInventoryResponse


def test_request_schema_accepts_valid_inventory_data() -> None:
    payload = {
        "hostname": "endpoint-01",
        "operating_system": "Windows",
        "os_version": "11",
        "architecture": "x64",
        "agent_version": "1.2.3",
        "cpu_model": "Intel Core i7",
        "cpu_cores": 8,
        "total_memory_mb": 16384,
        "total_disk_mb": 512000,
        "local_ip": "192.168.1.10",
        "mac_address": "00:11:22:33:44:55",
    }

    model = DeviceInventoryRequest(**payload)

    assert model.hostname == "endpoint-01"
    assert model.operating_system == "Windows"
    assert model.cpu_cores == 8
    assert model.total_memory_mb == 16384


def test_request_schema_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="", operating_system="Windows")

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", cpu_cores=0)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", cpu_cores=-1)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", total_memory_mb=0)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", total_memory_mb=-1)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", total_disk_mb=0)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", total_disk_mb=-1)

    with pytest.raises(ValidationError):
        DeviceInventoryRequest(hostname="endpoint", operating_system="Windows", local_ip="x" * 46)


def test_response_schema_supports_orm_objects() -> None:
    inventory = DeviceInventory(
        id=uuid4(),
        device_id=uuid4(),
        hostname="endpoint-01",
        operating_system="Windows",
        os_version="11",
        architecture="x64",
        agent_version="1.2.3",
        cpu_model="Intel Core i7",
        cpu_cores=8,
        total_memory_mb=16384,
        total_disk_mb=512000,
        local_ip="192.168.1.10",
        mac_address="00:11:22:33:44:55",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = DeviceInventoryResponse.model_validate(inventory)

    assert response.hostname == "endpoint-01"
    assert response.device_id == inventory.device_id
    assert isinstance(response.created_at, datetime)
    assert isinstance(response.id, UUID)
