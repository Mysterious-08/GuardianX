from __future__ import annotations

from fastapi import APIRouter, status
from uuid import UUID

from app.api.dependencies import DeviceServiceDep, DeviceInventoryServiceDep
from app.schemas.device import DeviceRegisterRequest, DeviceResponse
from app.schemas.heartbeat import HeartbeatRequest, HeartbeatResponse
from app.schemas.device_inventory import DeviceInventoryRequest, DeviceInventoryResponse
from app.security.dependencies import CurrentUserDep


router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
)
def register_device(
    device_data: DeviceRegisterRequest,
    current_user: CurrentUserDep,
    device_service: DeviceServiceDep,
) -> DeviceResponse:
    """Register or update a GuardianX device using the device service."""
    device = device_service.register_or_update_device(
        user=current_user,
        device_data=device_data,
    )
    return device


@router.post(
    "/heartbeat",
    response_model=HeartbeatResponse,
    status_code=status.HTTP_200_OK,
)
def heartbeat(
    heartbeat: HeartbeatRequest,
    current_user: CurrentUserDep,
    device_service: DeviceServiceDep,
) -> HeartbeatResponse:
    """Process an agent heartbeat and return the server response."""
    return device_service.send_heartbeat(user=current_user, heartbeat=heartbeat)


@router.post(
    "/{agent_id}/inventory",
    response_model=DeviceInventoryResponse,
    status_code=status.HTTP_200_OK,
)
def upsert_inventory(
    agent_id: UUID,
    inventory_data: DeviceInventoryRequest,
    current_user: CurrentUserDep,
    device_inventory_service: DeviceInventoryServiceDep,
) -> DeviceInventoryResponse:
    """Create or update the current inventory snapshot for the authenticated device.

    This endpoint is intentionally idempotent: it returns the device's current
    inventory whether the call results in a create or an update.
    """
    inventory = device_inventory_service.create_or_update_inventory(
        user=current_user,
        agent_id=agent_id,
        inventory_data=inventory_data,
    )
    return inventory
