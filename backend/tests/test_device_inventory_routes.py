from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.device import Device
from app.models.device_inventory import DeviceInventory
from app.models.user import User
from app.security.dependencies import get_current_user


def _create_in_memory_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    return session_factory()


def _override_db(db: Session):
    def _get_db():
        try:
            yield db
        finally:
            pass

    return _get_db


def _override_user(user: User):
    def _get_user(token: str | None = None) -> User:
        return user

    return _get_user


def _configure_overrides(db: Session, user: User) -> None:
    app.dependency_overrides[get_db] = _override_db(db)
    app.dependency_overrides[get_current_user] = _override_user(user)


def _create_user(db: Session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_device(db: Session, user: User) -> Device:
    device = Device(
        agent_id=uuid4(),
        user_id=user.id,
        hostname="host",
        operating_system="Linux",
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _inventory_payload(**overrides) -> dict:
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
    return payload


def test_create_inventory_endpoint_success() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_owner")
    device = _create_device(db, user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json=_inventory_payload(),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] is not None
        assert body["device_id"] == str(device.id)
        assert body["hostname"] == "endpoint-01"
        assert body["operating_system"] == "Windows"
        assert body["cpu_cores"] == 8
        assert body["total_memory_mb"] == 16384
        assert body["total_disk_mb"] == 512000
        assert body["local_ip"] == "192.168.1.10"
        assert body["mac_address"] == "00:11:22:33:44:55"
        assert body["cpu_info"]["cores"]["logical"] == 20
        assert body["ram_info"]["modules"][0]["speed_mhz"] == 3200
        assert body["disk_info"]["volumes"][0]["free_gb"] == 218
        assert body["network_interfaces"][0]["name"] == "Ethernet"
        assert body["operating_system_info"]["build"] == "22631"

        persisted = db.scalar(
            select(DeviceInventory).where(DeviceInventory.device_id == device.id)
        )
        assert persisted is not None
        assert str(persisted.id) == body["id"]
    finally:
        app.dependency_overrides.clear()


def test_create_inventory_endpoint_is_idempotent() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_update")
    device = _create_device(db, user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        first_response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json=_inventory_payload(),
        )
        assert first_response.status_code == 200

        second_response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json=_inventory_payload(
                hostname="endpoint-02",
                cpu_cores=16,
                total_memory_mb=32768,
                cpu_info={"manufacturer": "AMD", "model": "Ryzen 9"},
                ram_info={"total_mb": 32768},
                disk_info={"volumes": [{"drive": "D:", "size_gb": 1024}]},
                network_interfaces=[{"name": "Wi-Fi", "addresses": ["10.0.0.5"]}],
                operating_system_info={"name": "Windows 11 Enterprise", "build": "26100"},
            ),
        )

        assert second_response.status_code == 200
        first_body = first_response.json()
        second_body = second_response.json()
        assert second_body["id"] == first_body["id"]
        assert second_body["device_id"] == str(device.id)
        assert second_body["hostname"] == "endpoint-02"
        assert second_body["cpu_cores"] == 16
        assert second_body["total_memory_mb"] == 32768
        assert second_body["cpu_info"]["model"] == "Ryzen 9"
        assert second_body["ram_info"]["total_mb"] == 32768
        assert second_body["disk_info"]["volumes"][0]["drive"] == "D:"
        assert second_body["network_interfaces"][0]["name"] == "Wi-Fi"
        assert second_body["operating_system_info"]["build"] == "26100"
        assert db.scalar(select(func.count()).select_from(DeviceInventory)) == 1
    finally:
        app.dependency_overrides.clear()


def test_get_inventory_endpoint_success() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_get")
    device = _create_device(db, user)
    inventory = DeviceInventory(
        device_id=device.id,
        hostname="endpoint-get",
        operating_system="Windows",
        cpu_info={"model": "Intel"},
        ram_info={"total_mb": 8192},
        disk_info={"volumes": [{"drive": "C:"}]},
        network_interfaces=[{"name": "Ethernet"}],
        operating_system_info={"build": "22631"},
    )
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get(f"/devices/{device.agent_id}/inventory")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(inventory.id)
        assert body["device_id"] == str(device.id)
        assert body["hostname"] == "endpoint-get"
        assert body["cpu_info"]["model"] == "Intel"
        assert body["ram_info"]["total_mb"] == 8192
        assert body["disk_info"]["volumes"][0]["drive"] == "C:"
        assert body["network_interfaces"][0]["name"] == "Ethernet"
        assert body["operating_system_info"]["build"] == "22631"
    finally:
        app.dependency_overrides.clear()


def test_get_inventory_endpoint_returns_404_when_inventory_missing() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_missing")
    device = _create_device(db, user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get(f"/devices/{device.agent_id}/inventory")

        assert response.status_code == 404
        assert response.json()["detail"] == "Device inventory not found."
    finally:
        app.dependency_overrides.clear()


def test_create_inventory_endpoint_unknown_agent_returns_404() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_unknown_post")
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.post(
            f"/devices/{uuid4()}/inventory",
            json=_inventory_payload(),
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_inventory_endpoint_unknown_agent_returns_404() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_unknown_get")
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.get(f"/devices/{uuid4()}/inventory")

        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_create_inventory_endpoint_ownership_violation_returns_403() -> None:
    db = _create_in_memory_session()
    owner = _create_user(db, "route_inventory_device_owner")
    other = _create_user(db, "route_inventory_other_post")
    device = _create_device(db, owner)
    _configure_overrides(db, other)
    client = TestClient(app)

    try:
        response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json=_inventory_payload(),
        )

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_get_inventory_endpoint_ownership_violation_returns_403() -> None:
    db = _create_in_memory_session()
    owner = _create_user(db, "route_inventory_get_owner")
    other = _create_user(db, "route_inventory_other_get")
    device = _create_device(db, owner)
    _configure_overrides(db, other)
    client = TestClient(app)

    try:
        response = client.get(f"/devices/{device.agent_id}/inventory")

        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_create_inventory_endpoint_invalid_missing_fields_returns_422() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_invalid_missing")
    device = _create_device(db, user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json={},
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_create_inventory_endpoint_invalid_positive_integer_returns_422() -> None:
    db = _create_in_memory_session()
    user = _create_user(db, "route_inventory_invalid_integer")
    device = _create_device(db, user)
    _configure_overrides(db, user)
    client = TestClient(app)

    try:
        response = client.post(
            f"/devices/{device.agent_id}/inventory",
            json=_inventory_payload(cpu_cores=0),
        )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
