from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.database.session import DBSessionDep
from app.services.device import DeviceService
from app.services.device_inventory import DeviceInventoryService
from app.services.dashboard import DashboardService
from app.services.security_event import SecurityEventService


def get_device_service(db: DBSessionDep) -> DeviceService:
    """Provide a device service instance for route handlers."""
    return DeviceService(db=db)


DeviceServiceDep = Annotated[
    DeviceService,
    Depends(get_device_service),
]


def get_device_inventory_service(db: DBSessionDep) -> DeviceInventoryService:
    """Provide a device inventory service instance for route handlers."""
    return DeviceInventoryService(db=db)


DeviceInventoryServiceDep = Annotated[
    DeviceInventoryService,
    Depends(get_device_inventory_service),
]


def get_dashboard_service(db: DBSessionDep) -> DashboardService:
    """Provide a dashboard service instance for route handlers."""
    return DashboardService(db=db)


DashboardServiceDep = Annotated[
    DashboardService,
    Depends(get_dashboard_service),
]


def get_security_event_service(db: DBSessionDep) -> SecurityEventService:
    """Provide a security event service instance for route handlers."""
    return SecurityEventService(db=db)


SecurityEventServiceDep = Annotated[
    SecurityEventService,
    Depends(get_security_event_service),
]
