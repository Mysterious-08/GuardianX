from pathlib import Path

from app.ml.inference import GuardianXInference


ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "ml"
    / "models"
    / "guardianx_isolation_forest_v2.joblib"
)


vector = [
    3e-06,
    2,
    0,
    12,
    0,
    666666.67,
    4000000,
    1,
]


inference = GuardianXInference(ARTIFACT)
result = inference.predict(vector)

print("Inference smoke test: PASS")
print("Prediction:", result.prediction)
print("Anomaly score:", result.anomaly_score)