from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.user import User
from app.models.device import Device
from app.models.device_inventory import DeviceInventory
from app.services.device_inventory import DeviceInventoryService
from app.schemas.device_inventory import DeviceInventoryRequest
from app.exceptions.device import DeviceNotFoundError, DeviceOwnershipError


def _create_in_memory_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _create_user(db, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_device(db, user: User, *, agent_id: UUID | None = None) -> Device:
    device = Device(
        agent_id=agent_id or uuid4(),
        user_id=user.id,
        hostname="host",
        operating_system="Linux",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _inventory_request(**overrides) -> DeviceInventoryRequest:
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
        "cpu_info": {
            "manufacturer": "Intel",
            "model": "Core i7-12700",
            "cores": {"physical": 12, "logical": 20},
        },
        "ram_info": {
            "total_mb": 16384,
            "modules": [{"capacity_mb": 8192, "speed_mhz": 3200}],
        },
        "disk_info": {
            "volumes": [{"drive": "C:", "size_gb": 512, "free_gb": 218}],
        },
        "network_interfaces": [
            {
                "name": "Ethernet",
                "mac_address": "00:11:22:33:44:55",
                "addresses": ["192.168.1.10"],
            }
        ],
        "operating_system_info": {
            "name": "Windows 11 Pro",
            "build": "22631",
            "edition": "Professional",
        },
    }
    payload.update(overrides)
    return DeviceInventoryRequest(**payload)


def test_create_inventory_creates_record_and_persists() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "alice")
    device = _create_device(db, user)

    service = DeviceInventoryService(db)
    request = _inventory_request()
    inventory = service.create_or_update_inventory(user=user, agent_id=device.agent_id, inventory_data=request)

    assert inventory is not None
    assert inventory.device_id == device.id
    assert inventory.hostname == request.hostname
    assert inventory.operating_system == request.operating_system
    assert inventory.cpu_cores == request.cpu_cores
    assert inventory.total_memory_mb == request.total_memory_mb
    assert inventory.total_disk_mb == request.total_disk_mb
    assert inventory.local_ip == request.local_ip
    assert inventory.mac_address == request.mac_address
    assert inventory.cpu_info == request.cpu_info
    assert inventory.ram_info == request.ram_info
    assert inventory.disk_info == request.disk_info
    assert inventory.network_interfaces == request.network_interfaces
    assert inventory.operating_system_info == request.operating_system_info
    assert inventory.id is not None

    stmt = select(DeviceInventory).where(DeviceInventory.device_id == device.id)
    persisted = db.scalar(stmt)
    assert persisted is not None
    assert persisted.id == inventory.id


def test_create_inventory_preserves_all_inventory_fields() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "nested")
    device = _create_device(db, user)
    request = _inventory_request()

    inventory = DeviceInventoryService(db).create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=request,
    )

    db.refresh(inventory)
    assert inventory.cpu_info == request.cpu_info
    assert inventory.ram_info == request.ram_info
    assert inventory.disk_info == request.disk_info
    assert inventory.network_interfaces == request.network_interfaces
    assert inventory.operating_system_info == request.operating_system_info


def test_create_inventory_raises_for_unknown_device() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "carol")

    with pytest.raises(DeviceNotFoundError):
        DeviceInventoryService(db).create_or_update_inventory(
            user=user,
            agent_id=uuid4(),
            inventory_data=_inventory_request(),
        )


def test_create_inventory_raises_on_ownership_violation() -> None:
    db = _create_in_memory_session()
    owner = _create_user(db, "owner")
    other = _create_user(db, "other")
    device = _create_device(db, owner)

    with pytest.raises(DeviceOwnershipError):
        DeviceInventoryService(db).create_or_update_inventory(
            user=other,
            agent_id=device.agent_id,
            inventory_data=_inventory_request(),
        )


def test_update_inventory_updates_existing_record() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "update")
    device = _create_device(db, user)
    service = DeviceInventoryService(db)

    initial = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=_inventory_request(),
    )
    updated_request = _inventory_request(
        hostname="endpoint-02",
        cpu_cores=16,
        total_memory_mb=32768,
        total_disk_mb=1024000,
        cpu_info={"manufacturer": "AMD", "model": "Ryzen 9"},
        ram_info={"total_mb": 32768, "modules": [{"capacity_mb": 16384}]},
        disk_info={"volumes": [{"drive": "D:", "size_gb": 1024}]},
        network_interfaces=[{"name": "Wi-Fi", "addresses": ["10.0.0.5"]}],
        operating_system_info={"name": "Windows 11 Enterprise", "build": "26100"},
    )

    result = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=updated_request,
    )

    assert result.id == initial.id
    assert result.device_id == device.id
    assert result.hostname == "endpoint-02"
    assert result.cpu_cores == 16
    assert result.total_memory_mb == 32768
    assert result.total_disk_mb == 1024000
    assert result.cpu_info == updated_request.cpu_info
    assert result.ram_info == updated_request.ram_info
    assert result.disk_info == updated_request.disk_info
    assert result.network_interfaces == updated_request.network_interfaces
    assert result.operating_system_info == updated_request.operating_system_info
    assert db.scalar(select(DeviceInventory).where(DeviceInventory.device_id == device.id)) is not None
    assert len(db.scalars(select(DeviceInventory)).all()) == 1


def test_update_inventory_preserves_device_association() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "association")
    device = _create_device(db, user)
    service = DeviceInventoryService(db)

    initial = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=_inventory_request(),
    )
    updated = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=_inventory_request(hostname="updated-host"),
    )

    assert updated.id == initial.id
    assert updated.device_id == device.id


def test_get_inventory_by_device_id_returns_inventory() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "device_lookup")
    device = _create_device(db, user)
    service = DeviceInventoryService(db)
    created = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=_inventory_request(),
    )

    result = service.get_inventory_by_device_id(device_id=device.id)

    assert result is not None
    assert result.id == created.id


def test_get_inventory_by_device_id_returns_none_when_missing() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "device_missing")
    device = _create_device(db, user)

    result = DeviceInventoryService(db).get_inventory_by_device_id(device_id=device.id)

    assert result is None


def test_get_inventory_by_agent_id_returns_inventory() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "agent_lookup")
    device = _create_device(db, user)
    service = DeviceInventoryService(db)
    created = service.create_or_update_inventory(
        user=user,
        agent_id=device.agent_id,
        inventory_data=_inventory_request(),
    )

    result = service.get_inventory_by_agent_id(user=user, agent_id=device.agent_id)

    assert result is not None
    assert result.id == created.id


def test_get_inventory_by_agent_id_returns_none_when_inventory_missing() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "agent_missing")
    device = _create_device(db, user)

    result = DeviceInventoryService(db).get_inventory_by_agent_id(
        user=user,
        agent_id=device.agent_id,
    )

    assert result is None


def test_get_inventory_by_agent_id_raises_for_unknown_device() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "unknown_agent")

    with pytest.raises(DeviceNotFoundError):
        DeviceInventoryService(db).get_inventory_by_agent_id(user=user, agent_id=uuid4())


def test_get_inventory_by_agent_id_raises_on_ownership_violation() -> None:
    db = _create_in_memory_session()
    owner = _create_user(db, "inventory_owner")
    other = _create_user(db, "inventory_other")
    device = _create_device(db, owner)

    with pytest.raises(DeviceOwnershipError):
        DeviceInventoryService(db).get_inventory_by_agent_id(
            user=other,
            agent_id=device.agent_id,
        )
