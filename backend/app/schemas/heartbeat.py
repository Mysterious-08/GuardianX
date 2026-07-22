"""Heartbeat schemas for the GuardianX API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HeartbeatRequest(BaseModel):
    """Payload sent by an agent to indicate it is alive."""

    agent_id: UUID


class HeartbeatResponse(BaseModel):
    """Server response after processing a heartbeat."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    server_time: datetime
    next_heartbeat_in: int
