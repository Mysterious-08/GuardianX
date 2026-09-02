from __future__ import annotations

"""Windows capture demo and live-path helpers for GuardianX.

This module intentionally keeps the existing packet-source, aggregation, inference,
transport, and API boundaries intact while exposing a safe deterministic demo
mode and a Windows/Npcap live-capture entry point.
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Callable
from uuid import UUID

from app.agent.collectors.network import (
    BidirectionalFlowAggregator,
    CompletedFlowRecord,
    NetworkTelemetryCollector,
    PacketObservation,
)
from app.agent.collectors.scapy_windows import WindowsScapyPacketSource
from app.agent.transport.events import SecurityEventTransport
from app.ml.inference import GuardianXInference

logger = logging.getLogger(__name__)

MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "ml"
    / "models"
    / "guardianx_isolation_forest_v2.joblib"
)


def validate_windows_capture_runtime(
    *,
    current_os: str | None = None,
    interface_listing: Callable[[], list[object]] | None = None,
) -> None:
    """Validate the environment needed for a real Windows/Npcap capture."""
    platform_name = current_os or os.name
    if platform_name != "nt":
        raise RuntimeError(
            "Windows live capture requires a Windows host with Npcap/WinPcap support. "
            "This environment is not Windows."
        )

    if interface_listing is not None and not interface_listing():
        raise RuntimeError(
            "Windows live capture requires an available Npcap/WinPcap adapter. "
            "Install Npcap and ensure a packet-capture interface exists."
        )


def build_demo_completed_flow_record(collector_scope: str = "windows-demo") -> CompletedFlowRecord:
    """Construct a deterministic, completed flow for local smoke testing."""
    aggregator = BidirectionalFlowAggregator(collector_scope=collector_scope)
    observations = (
        PacketObservation(
            timestamp=1.0,
            source_ip="10.0.0.1",
            source_port=4000,
            destination_ip="10.0.0.2",
            destination_port=443,
            protocol="TCP",
            byte_count=100,
            tcp_flags=frozenset({"SYN"}),
        ),
        PacketObservation(
            timestamp=2.0,
            source_ip="10.0.0.2",
            source_port=443,
            destination_ip="10.0.0.1",
            destination_port=4000,
            protocol="TCP",
            byte_count=200,
            tcp_flags=frozenset({"SYN", "ACK"}),
        ),
        PacketObservation(
            timestamp=3.0,
            source_ip="10.0.0.2",
            source_port=443,
            destination_ip="10.0.0.1",
            destination_port=4000,
            protocol="TCP",
            byte_count=300,
            tcp_flags=frozenset({"FIN"}),
        ),
    )

    completed: list[CompletedFlowRecord] = []
    for observation in observations:
        completed = aggregator.observe(observation)
        if completed:
            break

    if not completed:
        completed = aggregator.flush()
    if not completed:
        raise RuntimeError("Demo flow did not complete as expected.")
    return completed[0]


def build_guardianx_v2_ml_detection(
    record: CompletedFlowRecord,
    *,
    inference: GuardianXInference | None = None,
) -> dict[str, object]:
    """Run the verified GuardianX v2 inference against the current flow record."""
    model_inference = inference or GuardianXInference(MODEL_PATH)
    vector = record.to_guardianx_v2_feature_vector()
    result = model_inference.predict(vector)
    return {
        "model": "guardianx_isolation_forest_v2",
        "schema_version": "v2",
        "prediction": result.prediction,
        "anomaly_score": result.anomaly_score,
    }


def run_demo(
    *,
    base_url: str | None = None,
    agent_id: UUID | str | None = None,
    access_token: str | None = None,
    inference: GuardianXInference | None = None,
) -> CompletedFlowRecord:
    """Exercise the existing collector → ML → transport path without live packet capture."""
    record = build_demo_completed_flow_record()
    vector = record.to_guardianx_v2_feature_vector()
    result = (inference or GuardianXInference(MODEL_PATH)).predict(vector)
    detection = {
        "model": "guardianx_isolation_forest_v2",
        "schema_version": "v2",
        "prediction": result.prediction,
        "anomaly_score": result.anomaly_score,
    }

    print("[demo] flow completed")
    print(f"[demo] v2 feature vector: {vector}")
    print(f"[demo] prediction: {result.prediction}")
    print(f"[demo] anomaly_score: {result.anomaly_score}")

    if base_url and agent_id and access_token:
        event = record.to_security_event_request()
        event.payload["ml_detection"] = detection
        transport = SecurityEventTransport(
            base_url=base_url,
            agent_id=UUID(str(agent_id)),
            access_token=access_token,
            inference=inference or GuardianXInference(MODEL_PATH),
        )
        print("[demo] sending event to GuardianX API")
        transport.publish(record)
        print("[demo] event transmission status: sent")
    else:
        print("[demo] API submission skipped: no base_url/agent_id/access_token provided")

    return record


def run_live_capture(
    *,
    interface: str | None = None,
    capture_timeout: float = 30.0,
    capture_count: int = 0,
    packet_filter: str = "ip or ip6",
    base_url: str | None = None,
    agent_id: UUID | str | None = None,
    access_token: str | None = None,
    inference: GuardianXInference | None = None,
) -> None:
    """Run the real Windows/Npcap capture pipeline against the existing collector stack."""
    validate_windows_capture_runtime()

    if base_url and not (agent_id and access_token):
        raise ValueError("base_url requires agent_id and access_token when posting to the API.")

    model_inference = inference or GuardianXInference(MODEL_PATH)
    transport = None
    if base_url and agent_id and access_token:
        transport = SecurityEventTransport(
            base_url=base_url,
            agent_id=UUID(str(agent_id)),
            access_token=access_token,
            inference=model_inference,
        )

    def on_completed(record: CompletedFlowRecord) -> None:
        detection = build_guardianx_v2_ml_detection(record, inference=model_inference)
        vector = record.to_guardianx_v2_feature_vector()
        print("[live] flow completed")
        print(f"[live] v2 feature vector: {vector}")
        print(f"[live] prediction: {detection['prediction']}")
        print(f"[live] anomaly_score: {detection['anomaly_score']}")

        if transport is not None:
            print("[live] creating event payload")
            try:
                transport.publish(record)
                print("[live] event transmission status: sent")
            except Exception as exc:  # pragma: no cover - live-path warning path
                print(f"[live] event transmission status: failed ({exc})")
                raise

    collector = NetworkTelemetryCollector(
        aggregator=BidirectionalFlowAggregator(collector_scope="windows-live"),
        on_completed=on_completed,
    )
    source = WindowsScapyPacketSource(
        collector=collector,
        interface=interface,
        capture_timeout=capture_timeout,
        capture_count=capture_count,
        packet_filter=packet_filter,
    )

    try:
        source.capture()
    except PermissionError as exc:
        raise RuntimeError(
            "Windows live capture requires Administrator privileges and Npcap/WinPcap support. "
            "Run PowerShell as Administrator and ensure Npcap is installed."
        ) from exc
    except OSError as exc:  # pragma: no cover - OS-specific live path
        raise RuntimeError(
            "Windows live capture failed. Ensure Npcap is installed and the selected interface is valid."
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GuardianX Windows capture demo and live path")
    parser.add_argument("--demo", action="store_true", help="Run a deterministic collector-to-ML demo without live capture.")
    parser.add_argument("--live", action="store_true", help="Run the Windows/Npcap live packet capture path.")
    parser.add_argument("--interface", default=None, help="Scapy interface name for live capture.")
    parser.add_argument("--capture-timeout", type=float, default=30.0, help="Seconds to capture during live mode.")
    parser.add_argument("--capture-count", type=int, default=0, help="Packet count limit; 0 means unlimited for the live capture.")
    parser.add_argument("--packet-filter", default="ip or ip6", help="Scapy packet filter for live capture.")
    parser.add_argument("--api-base-url", default=None, help="GuardianX API base URL, e.g. http://localhost:8000")
    parser.add_argument("--agent-id", default=None, help="Device agent UUID used for live API submissions.")
    parser.add_argument("--access-token", default=None, help="Bearer token for the live API submission path.")
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    if args.live and args.demo:
        parser.error("Choose either --live or --demo, not both.")

    if args.live:
        run_live_capture(
            interface=args.interface,
            capture_timeout=args.capture_timeout,
            capture_count=args.capture_count,
            packet_filter=args.packet_filter,
            base_url=args.api_base_url,
            agent_id=args.agent_id,
            access_token=args.access_token,
        )
        return 0

    if args.demo:
        run_demo(
            base_url=args.api_base_url,
            agent_id=args.agent_id,
            access_token=args.access_token,
        )
        return 0

    run_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


WindowsPacketCapture = WindowsScapyPacketSource

__all__ = [
    "WindowsPacketCapture",
    "WindowsScapyPacketSource",
    "build_demo_completed_flow_record",
    "build_guardianx_v2_ml_detection",
    "run_demo",
    "run_live_capture",
    "validate_windows_capture_runtime",
]
