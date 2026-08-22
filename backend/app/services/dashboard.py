from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceStatus
from app.models.user import User
from app.models.security_event import SecurityEvent
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.device import DeviceService


class DashboardService:
    """Service responsible for authenticated dashboard aggregations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.device_service = DeviceService(db=db)

    def get_overview(self, *, user: User) -> DashboardOverviewResponse:
        """Return dashboard totals scoped to devices owned by ``user``."""
        devices = self.device_service.get_devices_by_user(user=user)
        device_ids = [device.id for device in devices]
        statuses = [device.status for device in devices]

        if device_ids:
            total_security_events = self.db.scalar(
                select(func.count(SecurityEvent.id)).where(
                    SecurityEvent.device_id.in_(device_ids)
                )
            ) or 0
        else:
            total_security_events = 0

        latest_device_activity = max(
            (device.last_seen for device in devices if device.last_seen is not None),
            default=None,
        )
        devices_with_inventory = sum(device.inventory is not None for device in devices)

        return DashboardOverviewResponse(
            total_devices=len(devices),
            online_devices=statuses.count(DeviceStatus.ONLINE),
            offline_devices=statuses.count(DeviceStatus.OFFLINE),
            registered_devices=statuses.count(DeviceStatus.REGISTERED),
            isolated_devices=statuses.count(DeviceStatus.ISOLATED),
            quarantined_devices=statuses.count(DeviceStatus.QUARANTINED),
            devices_with_inventory=devices_with_inventory,
            devices_without_inventory=len(devices) - devices_with_inventory,
            total_security_events=total_security_events,
            latest_device_activity=latest_device_activity,
        )
