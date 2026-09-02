from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np


FEATURE_COUNT = 8

EXPECTED_FEATURES = (
    "flow_duration",
    "forward_packet_count",
    "backward_packet_count",
    "forward_byte_count",
    "backward_byte_count",
    "packet_rate",
    "byte_rate",
    "is_one_way_flow",
)


@dataclass(frozen=True)
class MLInferenceResult:
    prediction: int
    anomaly_score: float


class GuardianXInference:
    """Runtime inference wrapper for the GuardianX v2 model artifact."""

    def __init__(self, artifact_path: str | Path) -> None:
        self.artifact_path = Path(artifact_path)

        if not self.artifact_path.exists():
            raise FileNotFoundError(
                f"GuardianX ML artifact not found: {self.artifact_path}"
            )

        artifact = joblib.load(self.artifact_path)
        self._validate_artifact(artifact)

        self.preprocessor = artifact["preprocessor"]
        self.model = artifact["model"]

    def predict(
        self,
        vector: Sequence[float],
    ) -> MLInferenceResult:
        """Run inference on one canonical v2 feature vector."""

        matrix = np.asarray(vector, dtype=float)

        if matrix.ndim != 1:
            raise ValueError("Inference input must be a 1D feature vector.")

        if matrix.shape[0] != FEATURE_COUNT:
            raise ValueError(
                f"Expected {FEATURE_COUNT} v2 features, "
                f"got {matrix.shape[0]}."
            )

        if not np.all(np.isfinite(matrix)):
            raise ValueError("Inference input must contain only finite values.")

        if np.any(matrix[:7] < 0):
            raise ValueError("Continuous v2 features must not be negative.")

        if matrix[7] not in (0.0, 1.0):
            raise ValueError("is_one_way_flow must be 0 or 1.")

        transformed = self.preprocessor.transform(matrix.reshape(1, -1))

        prediction = int(self.model.predict(transformed)[0])
        anomaly_score = float(self.model.decision_function(transformed)[0])

        return MLInferenceResult(
            prediction=prediction,
            anomaly_score=anomaly_score,
        )

    @staticmethod
    def _validate_artifact(artifact: object) -> None:
        if not isinstance(artifact, dict):
            raise ValueError("GuardianX ML artifact must contain a dictionary.")

        required_keys = {
            "schema_name",
            "schema_version",
            "feature_names",
            "preprocessor",
            "model",
        }

        missing = required_keys - artifact.keys()

        if missing:
            raise ValueError(
                f"GuardianX ML artifact is missing keys: {sorted(missing)}"
            )

        if artifact["schema_name"] != "guardianx_behavioral_features":
            raise ValueError("Unsupported GuardianX ML schema name.")

        if artifact["schema_version"] != "v2":
            raise ValueError("Unsupported GuardianX ML schema version.")

        if tuple(artifact["feature_names"]) != EXPECTED_FEATURES:
            raise ValueError(
                "GuardianX ML artifact feature order does not match v2."
            )