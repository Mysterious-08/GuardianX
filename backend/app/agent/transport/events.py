from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

import httpx

from app.agent.collectors.network import CompletedFlowRecord
from app.ml.inference import GuardianXInference

logger = logging.getLogger(__name__)

ML_MODEL_NAME = "guardianx_isolation_forest_v2"
ML_SCHEMA_VERSION = "v2"
ML_ARTIFACT_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml"
    / "models"
    / "guardianx_isolation_forest_v2.joblib"
)


class EventTransportError(RuntimeError):
    """Raised when a GuardianX security event cannot be published."""


class SecurityEventTransport:
    """Publish completed telemetry events to the GuardianX API."""

    def __init__(
        self,
        *,
        base_url: str,
        agent_id: UUID,
        access_token: str,
        timeout: float = 10.0,
        inference: GuardianXInference | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("base_url cannot be empty.")
        if not access_token.strip():
            raise ValueError("access_token cannot be empty.")
        if timeout <= 0:
            raise ValueError("timeout must be positive.")

        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.access_token = access_token
        self.timeout = timeout
        self.inference = inference or GuardianXInference(ML_ARTIFACT_PATH)

    @property
    def events_url(self) -> str:
        return f"{self.base_url}/devices/{self.agent_id}/events"

    def _ml_detection(self, record: CompletedFlowRecord) -> dict[str, object]:
        if not record.model_ready:
            raise ValueError("Flow telemetry is not ready for GuardianX v2 inference.")

        vector = record.to_guardianx_v2_feature_vector()
        result = self.inference.predict(vector)
        return {
            "model": ML_MODEL_NAME,
            "schema_version": ML_SCHEMA_VERSION,
            "prediction": result.prediction,
            "anomaly_score": result.anomaly_score,
        }

    def publish(self, record: CompletedFlowRecord) -> None:
        """Publish one completed flow as a GuardianX security event."""
        event = record.to_security_event_request()

        try:
            event.payload["ml_detection"] = self._ml_detection(record)
        except (TypeError, ValueError, RuntimeError) as exc:
            logger.warning("GuardianX v2 inference skipped for %s: %s", record, exc)

        try:
            response = httpx.post(
                self.events_url,
                json=event.model_dump(mode="json"),
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EventTransportError(
                f"Failed to publish security event: {exc}"
            ) from exc