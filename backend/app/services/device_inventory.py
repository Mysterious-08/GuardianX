from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.device_inventory import DeviceInventory
from app.models.user import User
from app.schemas.device_inventory import DeviceInventoryRequest
from app.exceptions.device import DeviceNotFoundError, DeviceOwnershipError


class DeviceInventoryService:
    """Service responsible for creating and updating a device's current inventory.

    This class is framework-agnostic and operates solely against SQLAlchemy models
    and business exceptions so it can be used from API routes or background
    workers without pulling in FastAPI-specific dependencies.
    """

    def __init__(self, db: Session) -> None:
        """Initialize with a SQLAlchemy ``Session`` provided via dependency injection."""
        self.db = db

    def get_inventory_by_device_id(self, *, device_id: UUID) -> DeviceInventory | None:
        """Return the current ``DeviceInventory`` for a given ``device_id``.

        Returns ``None`` when no inventory exists for the device.
        """
        statement = select(DeviceInventory).where(DeviceInventory.device_id == device_id)
        return self.db.scalar(statement)

    def get_inventory_by_agent_id(
        self,
        *,
        user: User,
        agent_id: UUID,
    ) -> DeviceInventory | None:
        """Return a device's inventory after validating existence and ownership."""
        device_stmt = select(Device).where(Device.agent_id == agent_id)
        device = self.db.scalar(device_stmt)

        if device is None:
            raise DeviceNotFoundError("Device not found.")

        if device.user_id != user.id:
            raise DeviceOwnershipError("Authenticated user does not own the device.")

        return self.get_inventory_by_device_id(device_id=device.id)

    def create_or_update_inventory(
        self,
        *,
        user: User,
        agent_id: UUID,
        inventory_data: DeviceInventoryRequest,
    ) -> DeviceInventory:
        """Create or update the current inventory for the device identified by ``agent_id``.

        The method enforces ownership and will raise ``DeviceNotFoundError`` when no
        Device exists for the provided ``agent_id``. If the authenticated ``user``
        does not own the device, ``DeviceOwnershipError`` is raised.

        On create: a new ``DeviceInventory`` is created and associated with the
        device. On update: only fields represented by ``DeviceInventoryRequest`` are
        updated. Transactions are committed on success and rolled back on errors.
        """

        # Locate the device by agent_id.
        device_stmt = select(Device).where(Device.agent_id == agent_id)
        device = self.db.scalar(device_stmt)

        if device is None:
            raise DeviceNotFoundError("Device not found.")

        if device.user_id != user.id:
            raise DeviceOwnershipError("Authenticated user does not own the device.")

        # Look for an existing inventory record for the device using the helper.
        existing_inventory = self.get_inventory_by_device_id(device_id=device.id)

        if existing_inventory is None:
            inventory = DeviceInventory(
                device_id=device.id,
                hostname=inventory_data.hostname,
                operating_system=inventory_data.operating_system,
                os_version=inventory_data.os_version,
                architecture=inventory_data.architecture,
                agent_version=inventory_data.agent_version,
                cpu_model=inventory_data.cpu_model,
                cpu_cores=inventory_data.cpu_cores,
                total_memory_mb=inventory_data.total_memory_mb,
                total_disk_mb=inventory_data.total_disk_mb,
                local_ip=inventory_data.local_ip,
                mac_address=inventory_data.mac_address,
                cpu_info=inventory_data.cpu_info,
                ram_info=inventory_data.ram_info,
                disk_info=inventory_data.disk_info,
                network_interfaces=inventory_data.network_interfaces,
                operating_system_info=inventory_data.operating_system_info,
            )

            try:
                self.db.add(inventory)
                self.db.commit()
                self.db.refresh(inventory)
                return inventory
            except Exception:
                self.db.rollback()
                raise

        # Update allowed fields only; do not touch id/device_id/created_at/updated_at.
        existing_inventory.hostname = inventory_data.hostname
        existing_inventory.operating_system = inventory_data.operating_system
        existing_inventory.os_version = inventory_data.os_version
        existing_inventory.architecture = inventory_data.architecture
        existing_inventory.agent_version = inventory_data.agent_version
        existing_inventory.cpu_model = inventory_data.cpu_model
        existing_inventory.cpu_cores = inventory_data.cpu_cores
        existing_inventory.total_memory_mb = inventory_data.total_memory_mb
        existing_inventory.total_disk_mb = inventory_data.total_disk_mb
        existing_inventory.local_ip = inventory_data.local_ip
        existing_inventory.mac_address = inventory_data.mac_address
        existing_inventory.cpu_info = inventory_data.cpu_info
        existing_inventory.ram_info = inventory_data.ram_info
        existing_inventory.disk_info = inventory_data.disk_info
        existing_inventory.network_interfaces = inventory_data.network_interfaces
        existing_inventory.operating_system_info = inventory_data.operating_system_info

        try:
            self.db.commit()
            self.db.refresh(existing_inventory)
            return existing_inventory
        except Exception:
            self.db.rollback()
            raise
