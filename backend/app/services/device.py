from __future__ import annotations

from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.schemas.device import DeviceRegisterRequest
from app.exceptions.device import DeviceOwnershipError
from app.exceptions.device import DeviceNotFoundError
from app.schemas.heartbeat import HeartbeatRequest, HeartbeatResponse

# Heartbeat interval returned to agents (seconds).
HEARTBEAT_INTERVAL_SECONDS = 30


class DeviceService:
    """Service responsible for GuardianX device lifecycle operations.

    Encapsulates device-related business logic and database interactions
    while remaining independent of FastAPI.
    """

    def __init__(self, db: Session) -> None:
        """Initialize the service with a SQLAlchemy session via dependency injection."""
        self.db = db

    def get_device_by_agent_id(self, *, agent_id: UUID) -> Device | None:
        """Retrieve a device by `agent_id`, returning ``None`` when absent."""
        statement = select(Device).where(Device.agent_id == agent_id)
        return self.db.scalar(statement)

    def register_or_update_device(
        self,
        *,
        user: User,
        device_data: DeviceRegisterRequest,
    ) -> Device:
        """Register a new device (first-time path) and return the persisted model.

        This implementation only handles the initial registration branch where a new
        Device is created and persisted. Update and ownership paths are handled
        in this method: existing devices are validated for ownership and their
        mutable metadata is updated.
        """
        existing_device = self.get_device_by_agent_id(agent_id=device_data.agent_id)

        if existing_device is None:
            # First-time registration: create and persist a new Device.
            device = Device(
                agent_id=device_data.agent_id,
                user_id=user.id,
                device_name=device_data.device_name,
                hostname=device_data.hostname,
                operating_system=device_data.operating_system,
                os_version=device_data.os_version,
                architecture=device_data.architecture,
                agent_version=device_data.agent_version,
            )

            try:
                self.db.add(device)
                self.db.commit()
                self.db.refresh(device)
                return device
            except Exception:
                self.db.rollback()
                raise

        # Existing device found: ensure ownership matches the authenticated user.
        if existing_device.user_id != user.id:
            raise DeviceOwnershipError("Device ownership mismatch.")

        # Update mutable metadata only.
        existing_device.device_name = device_data.device_name
        existing_device.hostname = device_data.hostname
        existing_device.operating_system = device_data.operating_system
        existing_device.os_version = device_data.os_version
        existing_device.architecture = device_data.architecture
        existing_device.agent_version = device_data.agent_version

        try:
            self.db.commit()
            self.db.refresh(existing_device)
            return existing_device
        except Exception:
            self.db.rollback()
            raise

    def send_heartbeat(self, *, user: User, heartbeat: HeartbeatRequest) -> HeartbeatResponse:
        """Process an agent heartbeat and return a heartbeat response."""
        existing_device = self.get_device_by_agent_id(agent_id=heartbeat.agent_id)

        if existing_device is None:
            raise DeviceNotFoundError("Device not found.")

        if existing_device.user_id != user.id:
            raise DeviceOwnershipError("Authenticated user does not own the device.")

        now = datetime.now(timezone.utc)
        existing_device.last_seen = now

        if existing_device.status in (DeviceStatus.REGISTERED, DeviceStatus.OFFLINE):
            existing_device.status = DeviceStatus.ONLINE

        try:
            self.db.commit()
            self.db.refresh(existing_device)

            return HeartbeatResponse(
                status="OK",
                server_time=now,
                next_heartbeat_in=HEARTBEAT_INTERVAL_SECONDS,
            )
        except Exception:
            self.db.rollback()
            raise
