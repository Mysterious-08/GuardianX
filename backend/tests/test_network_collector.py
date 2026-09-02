from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.agent.collectors.network import (
    BidirectionalFlowAggregator,
    NetworkTelemetryCollector,
    PacketObservation,
)
from app.models.security_event import SecurityEventSeverity, SecurityEventType


def packet(
    timestamp: float,
    source_port: int,
    destination_port: int,
    byte_count: int,
    *,
    source_ip: str = "10.0.0.1",
    destination_ip: str = "10.0.0.2",
    protocol: str = "UDP",
    tcp_flags: frozenset[str] = frozenset(),
) -> PacketObservation:
    return PacketObservation(
        timestamp=timestamp,
        source_ip=source_ip,
        source_port=source_port,
        destination_ip=destination_ip,
        destination_port=destination_port,
        protocol=protocol,
        byte_count=byte_count,
        tcp_flags=tcp_flags,
    )


def test_forward_and_reverse_packets_are_aggregated_with_rates() -> None:
    aggregator = BidirectionalFlowAggregator()

    aggregator.observe(packet(10.0, 4000, 443, 100))
    aggregator.observe(packet(12.0, 443, 4000, 200, source_ip="10.0.0.2", destination_ip="10.0.0.1"))
    completed = aggregator.observe(packet(14.0, 4000, 443, 300))
    completed.extend(aggregator.flush())

    record = completed[0]
    assert record.flow_duration == 4.0
    assert record.forward_packet_count == 2
    assert record.backward_packet_count == 1
    assert record.forward_byte_count == 400
    assert record.backward_byte_count == 200
    assert record.packet_rate == 0.75
    assert record.byte_rate == 150.0
    assert record.forward_backward_packet_ratio == 2.0


def test_tcp_syn_sets_forward_direction_and_fin_completes_flow() -> None:
    aggregator = BidirectionalFlowAggregator()

    aggregator.observe(packet(1.0, 443, 5000, 60, source_ip="10.0.0.2", destination_ip="10.0.0.1", protocol="tcp", tcp_flags=frozenset({"SYN"})))
    aggregator.observe(packet(2.0, 5000, 443, 60, protocol="TCP", tcp_flags=frozenset({"SYN", "ACK"})))
    completed = aggregator.observe(packet(3.0, 5000, 443, 40, protocol="TCP", tcp_flags=frozenset({"FIN"})))

    assert len(completed) == 1
    assert completed[0].forward_source_ip == "10.0.0.2"
    assert completed[0].forward_source_port == 443
    assert completed[0].forward_packet_count == 1
    assert completed[0].backward_packet_count == 2
    assert aggregator.active_flow_count == 0


def test_tcp_rst_completes_flow() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, 50, protocol="TCP"))

    completed = aggregator.observe(packet(2.0, 4000, 443, 20, protocol="TCP", tcp_flags=frozenset({"RST"})))

    assert len(completed) == 1
    assert completed[0].quality_status == "valid"


def test_idle_and_max_lifetime_expire_flows() -> None:
    aggregator = BidirectionalFlowAggregator(idle_timeout_seconds=5, max_flow_lifetime_seconds=20)
    aggregator.observe(packet(10.0, 4000, 443, 10))
    aggregator.observe(packet(11.0, 4000, 443, 10))
    assert aggregator.expire(14.0) == []
    assert aggregator.expire(16.0)[0].quality_status == "valid"

    lifetime_aggregator = BidirectionalFlowAggregator(idle_timeout_seconds=100, max_flow_lifetime_seconds=20)
    lifetime_aggregator.observe(packet(20.0, 4001, 443, 10))
    lifetime_aggregator.observe(packet(21.0, 4001, 443, 10))
    assert lifetime_aggregator.expire(39.0) == []
    assert lifetime_aggregator.expire(40.0)[0].quality_status == "valid"


def test_zero_backward_packets_use_unknown_ratio() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, 10))

    record = aggregator.flush()[0]

    assert record.forward_backward_packet_ratio is None


def test_completed_flow_builds_guardianx_v2_feature_vector() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, 10))
    aggregator.observe(packet(2.0, 443, 4000, 20, source_ip="10.0.0.2", destination_ip="10.0.0.1"))

    record = aggregator.flush()[0]
    vector = record.to_guardianx_v2_feature_vector()

    assert vector == [1.0, 1.0, 1.0, 10.0, 20.0, 2.0, 30.0, 0.0]


def test_one_way_flow_sets_is_one_way_flow_to_one() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, 10))
    aggregator.observe(packet(3.0, 4000, 443, 30))

    record = aggregator.flush()[0]

    assert record.to_guardianx_v2_feature_vector()[-1] == 1.0


def test_invalid_duration_does_not_produce_infinity_or_nan() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(5.0, 4000, 443, 10))
    aggregator.observe(packet(5.0, 4000, 443, 10))

    record = aggregator.flush()[0]

    assert record.flow_duration == 0.0
    assert record.packet_rate is None
    assert record.byte_rate is None
    assert record.model_ready is False
    assert "flow_duration" in record.missing_fields


def test_negative_bytes_are_preserved_as_invalid_telemetry() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, -10))
    aggregator.observe(packet(2.0, 4000, 443, 10))

    record = aggregator.flush()[0]

    assert record.forward_byte_count == 0
    assert record.quality_status == "invalid_telemetry"
    assert record.model_ready is False
    assert "byte_count" in record.missing_fields


def test_independent_flows_remain_separate() -> None:
    aggregator = BidirectionalFlowAggregator()
    aggregator.observe(packet(1.0, 4000, 443, 10))
    aggregator.observe(packet(1.0, 4001, 443, 20))

    completed = aggregator.flush()

    assert len(completed) == 2
    assert {record.source_port for record in completed} == {4000, 4001}


def test_shutdown_flushes_active_flows_and_publishes_records() -> None:
    published = []
    collector = NetworkTelemetryCollector(
        aggregator=BidirectionalFlowAggregator(),
        on_completed=published.append,
    )
    collector.observe_packet(packet(1.0, 4000, 443, 10))

    completed = collector.shutdown()

    assert len(completed) == 1
    assert published == completed


def test_completed_flow_converts_to_network_security_event_request() -> None:
    aggregator = BidirectionalFlowAggregator(collector_scope="test-machine")
    aggregator.observe(packet(1.0, 4000, 443, 10))
    record = aggregator.observe(packet(3.0, 443, 4000, 20, source_ip="10.0.0.2", destination_ip="10.0.0.1"))
    record = record[0] if record else aggregator.flush()[0]
    observed_at = datetime(2026, 8, 24, tzinfo=timezone.utc)

    request = record.to_security_event_request(observed_at=observed_at)

    assert request.event_type is SecurityEventType.NETWORK
    assert request.severity is SecurityEventSeverity.INFO
    assert request.source == "guardianx.network_collector"
    assert request.timestamp == observed_at
    assert request.payload["schema_version"] == "draft-network-flow-v0"
    assert request.payload["collector_scope"] == "test-machine"
    assert request.payload["flow_duration"] == 2.0
    assert request.payload["forward_packet_count"] == 1
    assert request.payload["backward_packet_count"] == 1


def test_invalid_timeout_configuration_is_rejected() -> None:
    with pytest.raises(ValueError):
        BidirectionalFlowAggregator(idle_timeout_seconds=0)