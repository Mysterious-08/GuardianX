from __future__ import annotations

import pytest
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.layers.l2 import Ether

from app.agent.collectors.network import NetworkTelemetryCollector
from app.agent.collectors.scapy_windows import WindowsScapyPacketSource, packet_to_observation
from app.agent.windows_capture import (
    build_demo_completed_flow_record,
    build_guardianx_v2_ml_detection,
    validate_windows_capture_runtime,
)


def test_converts_ipv4_tcp_packet_and_timestamp() -> None:
    packet = IP(src="192.0.2.1", dst="198.51.100.2") / TCP(sport=49152, dport=443, flags="S")
    packet.time = 1_700_000_000.25

    observation = packet_to_observation(packet)

    assert observation is not None
    assert observation.timestamp == 1_700_000_000.25
    assert observation.source_ip == "192.0.2.1"
    assert observation.source_port == 49152
    assert observation.destination_ip == "198.51.100.2"
    assert observation.destination_port == 443
    assert observation.protocol == "TCP"


def test_converts_ipv4_udp_packet() -> None:
    observation = packet_to_observation(
        IP(src="192.0.2.1", dst="198.51.100.2") / UDP(sport=5353, dport=53)
    )

    assert observation is not None
    assert observation.protocol == "UDP"
    assert observation.tcp_flags == frozenset()


def test_converts_ipv6_tcp_packet() -> None:
    observation = packet_to_observation(
        IPv6(src="2001:db8::1", dst="2001:db8::2") / TCP(sport=12345, dport=443, flags="A")
    )

    assert observation is not None
    assert observation.source_ip == "2001:db8::1"
    assert observation.destination_ip == "2001:db8::2"
    assert observation.protocol == "TCP"


def test_converts_ipv6_udp_packet() -> None:
    observation = packet_to_observation(
        IPv6(src="2001:db8::1", dst="2001:db8::2") / UDP(sport=12345, dport=53)
    )

    assert observation is not None
    assert observation.protocol == "UDP"
    assert observation.source_port == 12345
    assert observation.destination_port == 53


def test_extracts_tcp_syn_flag() -> None:
    observation = packet_to_observation(IP() / TCP(flags="S"))

    assert observation is not None
    assert observation.tcp_flags == frozenset({"SYN"})


def test_extracts_tcp_syn_ack_flags() -> None:
    observation = packet_to_observation(IP() / TCP(flags="SA"))

    assert observation is not None
    assert observation.tcp_flags == frozenset({"SYN", "ACK"})


def test_ignores_unsupported_or_non_ip_packets() -> None:
    assert packet_to_observation(Ether()) is None
    assert packet_to_observation(IP(src="192.0.2.1", dst="198.51.100.2")) is None


def test_uses_full_packet_length_for_byte_count() -> None:
    packet = IP(src="192.0.2.1", dst="198.51.100.2") / UDP(sport=1, dport=2) / b"payload"

    observation = packet_to_observation(packet)

    assert observation is not None
    assert observation.byte_count == len(packet)


def test_capture_forwards_observations_and_honors_configuration() -> None:
    calls: list[dict[str, object]] = []
    collector = NetworkTelemetryCollector()
    forwarded = []
    collector.observe_packet = forwarded.append  # type: ignore[method-assign]

    def fake_sniff(**kwargs: object) -> None:
        calls.append(kwargs)
        handler = kwargs["prn"]
        handler(IP(src="192.0.2.1", dst="198.51.100.2") / UDP(sport=1, dport=2))  # type: ignore[operator]

    source = WindowsScapyPacketSource(
        collector=collector,
        interface="\\\\Device\\NPF_{example}",
        capture_timeout=10,
        capture_count=5,
        packet_filter="ip or ip6",
        sniff_function=fake_sniff,
    )

    source.capture()

    assert len(forwarded) == 1
    assert forwarded[0].protocol == "UDP"
    assert calls == [{
        "iface": "\\\\Device\\NPF_{example}",
        "count": 5,
        "prn": source._handle_packet,
        "store": False,
        "timeout": 10,
        "filter": "ip or ip6",
    }]


def test_demo_flow_builds_v2_vector_and_inference_result() -> None:
    record = build_demo_completed_flow_record()
    vector = record.to_guardianx_v2_feature_vector()
    detection = build_guardianx_v2_ml_detection(record)

    assert vector == [2.0, 1.0, 2.0, 100.0, 500.0, 1.5, 300.0, 0.0]
    assert detection["model"] == "guardianx_isolation_forest_v2"
    assert detection["schema_version"] == "v2"
    assert detection["prediction"] in (0, 1)
    assert isinstance(detection["anomaly_score"], float)


def test_windows_capture_runtime_guard_raises_for_non_windows_or_missing_adapter() -> None:
    with pytest.raises(RuntimeError, match="not Windows"):
        validate_windows_capture_runtime(current_os="posix")

    with pytest.raises(RuntimeError, match="Npcap"):
        validate_windows_capture_runtime(current_os="nt", interface_listing=lambda: [])
