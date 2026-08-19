from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from uuid import UUID

from app.api.dependencies import (
    DeviceServiceDep,
    DeviceInventoryServiceDep,
    SecurityEventServiceDep,
)
from app.schemas.device import DeviceRegisterRequest, DeviceResponse
from app.schemas.heartbeat import HeartbeatRequest, HeartbeatResponse
from app.schemas.device_inventory import DeviceInventoryRequest, DeviceInventoryResponse
from app.schemas.security_event import SecurityEventRequest, SecurityEventResponse
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


@router.get(
    "/{agent_id}/inventory",
    response_model=DeviceInventoryResponse,
    status_code=status.HTTP_200_OK,
)
def get_inventory(
    agent_id: UUID,
    current_user: CurrentUserDep,
    device_inventory_service: DeviceInventoryServiceDep,
) -> DeviceInventoryResponse:
    """Return the current inventory for the authenticated device."""
    inventory = device_inventory_service.get_inventory_by_agent_id(
        user=current_user,
        agent_id=agent_id,
    )
    if inventory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device inventory not found.",
        )
    return inventory


@router.post(
    "/{agent_id}/events",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_security_event(
    agent_id: UUID,
    event_data: SecurityEventRequest,
    current_user: CurrentUserDep,
    security_event_service: SecurityEventServiceDep,
) -> SecurityEventResponse:
    """Create a security event for the authenticated device identified by agent_id.

    This route delegates business logic to ``SecurityEventService`` which enforces
    device lookup and ownership validation.
    """
    event = security_event_service.create_event(
        user=current_user,
        agent_id=agent_id,
        event_data=event_data,
    )
    return event


@router.get(
    "/{agent_id}/events",
    response_model=list[SecurityEventResponse],
    status_code=status.HTTP_200_OK,
)
def get_security_events(
    agent_id: UUID,
    current_user: CurrentUserDep,
    security_event_service: SecurityEventServiceDep,
) -> list[SecurityEventResponse]:
    """Return the list of security events for the authenticated user's device.

    Ownership and existence checks are performed in the service layer.
    """
    return security_event_service.get_events_by_agent_id(user=current_user, agent_id=agent_id)
