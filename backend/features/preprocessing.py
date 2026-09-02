"""Deterministic preprocessing for GuardianX v2 model features."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.preprocessing import StandardScaler

from features.schema import V2_SCHEMA


CONTINUOUS_FEATURES = (
    "flow_duration",
    "forward_packet_count",
    "backward_packet_count",
    "forward_byte_count",
    "backward_byte_count",
    "packet_rate",
    "byte_rate",
)

BINARY_FEATURES = (
    "is_one_way_flow",
)

EXPECTED_FEATURES = CONTINUOUS_FEATURES + BINARY_FEATURES


@dataclass
class V2Preprocessor:
    """Fit-on-training, transform-only-after-fit preprocessing."""

    scaler: StandardScaler | None = None

    def fit(self, vectors: Sequence[Sequence[float]]) -> "V2Preprocessor":
        matrix = _validate_matrix(vectors)

        continuous = np.log1p(matrix[:, :7])

        self.scaler = StandardScaler()
        self.scaler.fit(continuous)

        return self

    def transform(self, vectors: Sequence[Sequence[float]]) -> np.ndarray:
        if self.scaler is None:
            raise RuntimeError("Preprocessor must be fitted before transform().")

        matrix = _validate_matrix(vectors)

        continuous = np.log1p(matrix[:, :7])
        scaled = self.scaler.transform(continuous)

        binary = matrix[:, 7:8]

        return np.hstack((scaled, binary))

    def fit_transform(self, vectors: Sequence[Sequence[float]]) -> np.ndarray:
        return self.fit(vectors).transform(vectors)


def _validate_matrix(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=float)

    if matrix.ndim != 2:
        raise ValueError("Feature vectors must form a 2D matrix.")

    if matrix.shape[1] != len(EXPECTED_FEATURES):
        raise ValueError(
            f"Expected {len(EXPECTED_FEATURES)} v2 features, "
            f"got {matrix.shape[1]}."
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError("Feature matrix must contain only finite values.")

    if np.any(matrix[:, :7] < 0):
        raise ValueError("Continuous v2 features must not be negative.")

    binary = matrix[:, 7]

    if not np.all(np.isin(binary, (0.0, 1.0))):
        raise ValueError("is_one_way_flow must contain only 0 or 1.")

    return matrix