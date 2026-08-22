"""Dashboard response schemas for GuardianX."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardOverviewResponse(BaseModel):
    """Aggregated dashboard overview for the authenticated user."""

    total_devices: int
    online_devices: int
    offline_devices: int
    registered_devices: int
    isolated_devices: int
    quarantined_devices: int
    devices_with_inventory: int
    devices_without_inventory: int
    total_security_events: int
    latest_device_activity: datetime | None
