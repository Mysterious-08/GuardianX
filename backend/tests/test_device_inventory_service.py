from __future__ import annotations

from uuid import uuid4, UUID

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


def test_create_inventory_creates_record_and_persists() -> None:
    db = _create_in_memory_session()

    # Create a user and device belonging to that user.
    user = User(username="alice", email="alice@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = DeviceInventoryService(db)

    payload = DeviceInventoryRequest(
        hostname="host",
        operating_system="Linux",
        os_version="1.0",
        architecture="x64",
        agent_version="1.0.0",
        cpu_model="Intel",
        cpu_cores=4,
        total_memory_mb=8192,
        total_disk_mb=256000,
        local_ip="10.0.0.1",
        mac_address="00:11:22:33:44:55",
    )

    inventory = service.create_or_update_inventory(user=user, agent_id=agent_id, inventory_data=payload)

    assert inventory.device_id == device.id
    assert inventory.hostname == "host"

    # Ensure the record is present in the database.
    stmt = select(DeviceInventory).where(DeviceInventory.device_id == device.id)
    persisted = db.scalar(stmt)
    assert persisted is not None
    assert persisted.id == inventory.id


def test_update_inventory_updates_existing_record_and_preserves_id() -> None:
    db = _create_in_memory_session()

    user = User(username="bob", email="bob@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="old-host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    # Create initial inventory
    initial = DeviceInventory(
        device_id=device.id,
        hostname="old-host",
        operating_system="Linux",
    )
    db.add(initial)
    db.commit()
    db.refresh(initial)

    service = DeviceInventoryService(db)

    updated_payload = DeviceInventoryRequest(
        hostname="new-host",
        operating_system="Linux",
        os_version="2.0",
        architecture="arm64",
        agent_version="2.0.0",
        cpu_model="AMD",
        cpu_cores=8,
        total_memory_mb=16384,
        total_disk_mb=512000,
        local_ip="10.0.0.2",
        mac_address="AA:BB:CC:DD:EE:FF",
    )

    result = service.create_or_update_inventory(user=user, agent_id=agent_id, inventory_data=updated_payload)

    assert result.id == initial.id
    assert result.device_id == initial.device_id
    assert result.hostname == "new-host"
    assert result.os_version == "2.0"

    # Ensure only one inventory record exists for the device.
    stmt = select(DeviceInventory).where(DeviceInventory.device_id == device.id)
    persisted = db.scalar(stmt)
    assert persisted is not None


def test_create_or_update_inventory_raises_for_unknown_device() -> None:
    db = _create_in_memory_session()

    user = User(username="carol", email="carol@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    service = DeviceInventoryService(db)

    with pytest.raises(DeviceNotFoundError):
        service.create_or_update_inventory(user=user, agent_id=uuid4(), inventory_data=DeviceInventoryRequest(hostname="h", operating_system="OS"))


def test_create_or_update_inventory_raises_on_ownership_violation() -> None:
    db = _create_in_memory_session()

    owner = User(username="owner", email="owner@example.com", hashed_password="x")
    attacker = User(username="attacker", email="attacker@example.com", hashed_password="x")
    db.add_all([owner, attacker])
    db.commit()
    db.refresh(owner)
    db.refresh(attacker)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=owner.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = DeviceInventoryService(db)

    with pytest.raises(DeviceOwnershipError):
        service.create_or_update_inventory(user=attacker, agent_id=agent_id, inventory_data=DeviceInventoryRequest(hostname="h", operating_system="OS"))


def test_get_inventory_by_device_id_returns_inventory_or_none() -> None:
    db = _create_in_memory_session()

    user = User(username="dave", email="dave@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    agent_id = uuid4()
    device = Device(agent_id=agent_id, user_id=user.id, hostname="host", operating_system="Linux")
    db.add(device)
    db.commit()
    db.refresh(device)

    service = DeviceInventoryService(db)

    # No inventory yet
    assert service.get_inventory_by_device_id(device_id=device.id) is None

    inv = DeviceInventory(device_id=device.id, hostname="h", operating_system="Linux")
    db.add(inv)
    db.commit()
    db.refresh(inv)

    fetched = service.get_inventory_by_device_id(device_id=device.id)
    assert fetched is not None
    assert fetched.id == inv.id
