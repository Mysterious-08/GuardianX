from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.database.session import DBSessionDep
from app.services.device import DeviceService


def get_device_service(db: DBSessionDep) -> DeviceService:
    """Provide a device service instance for route handlers."""
    return DeviceService(db=db)


DeviceServiceDep = Annotated[
    DeviceService,
    Depends(get_device_service),
]
