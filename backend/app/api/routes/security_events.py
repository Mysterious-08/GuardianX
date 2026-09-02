from __future__ import annotations

from fastapi import APIRouter, status

from app.api.dependencies import SecurityEventServiceDep
from app.schemas.security_event import SecurityEventResponse
from app.security.dependencies import CurrentUserDep


router = APIRouter(prefix="/security-events", tags=["Security Events"])


@router.get(
    "",
    response_model=list[SecurityEventResponse],
    status_code=status.HTTP_200_OK,
)
def get_security_events(
    current_user: CurrentUserDep,
    security_event_service: SecurityEventServiceDep,
) -> list[SecurityEventResponse]:
    """Return the authenticated user's security events newest first."""
    return security_event_service.get_events_by_user(user=current_user)