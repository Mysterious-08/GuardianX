from __future__ import annotations

from fastapi import APIRouter, status

from app.api.dependencies import DashboardServiceDep
from app.schemas.dashboard import DashboardOverviewResponse
from app.security.dependencies import CurrentUserDep


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
)
def get_dashboard_overview(
    current_user: CurrentUserDep,
    dashboard_service: DashboardServiceDep,
) -> DashboardOverviewResponse:
    """Return the authenticated user's dashboard overview."""
    return dashboard_service.get_overview(user=current_user)