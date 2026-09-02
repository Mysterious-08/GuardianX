from __future__ import annotations

"""Draft Windows-neutral network flow aggregation primitives.

Live packet capture is intentionally outside this milestone. A future Windows
packet source can feed ``PacketObservation`` values into ``NetworkTelemetryCollector``.
The timeout defaults are conservative provisional values and remain configurable
until the draft telemetry contract is reviewed.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable

from app.models.security_event import SecurityEventType, SecurityEventSeverity
from app.schemas.security_event import SecurityEventRequest


logger = logging.getLogger(__name__)

DEFAULT_IDLE_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_FLOW_LIFETIME_SECONDS = 3600.0
NETWORK_COLLECTOR_SOURCE = "guardianx.network_collector"
NETWORK_FLOW_SCHEMA_VERSION = "draft-network-flow-v0"


@dataclass(frozen=True, order=True)
class FlowEndpoint:
    ip: str
    port: int


@dataclass(frozen=True)
class PacketObservation:
    """Packet metadata required by the flow aggregator; payload bytes are excluded."""

    timestamp: float
    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    protocol: str
    byte_count: int
    tcp_flags: frozenset[str] = frozenset()

    @property
    def source(self) -> FlowEndpoint:
        return FlowEndpoint(self.source_ip, self.source_port)

    @property
    def destination(self) -> FlowEndpoint:
        return FlowEndpoint(self.destination_ip, self.destination_port)

    @property
    def normalized_protocol(self) -> str:
        return self.protocol.upper()

    @property
    def normalized_tcp_flags(self) -> frozenset[str]:
        return frozenset(flag.upper() for flag in self.tcp_flags)


@dataclass(frozen=True)
class CompletedFlowRecord:
    collector_scope: str
    protocol: str
    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    forward_source_ip: str
    forward_source_port: int
    forward_destination_ip: str
    forward_destination_port: int
    flow_start_timestamp: float
    flow_end_timestamp: float
    flow_duration: float
    forward_packet_count: int
    backward_packet_count: int
    forward_byte_count: int
    backward_byte_count: int
    packet_rate: float | None
    byte_rate: float | None
    forward_backward_packet_ratio: float | None
    quality_status: str
    missing_fields: tuple[str, ...] = ()
    model_ready: bool = True

    def to_security_event_request(
        self,
        *,
        observed_at: datetime | None = None,
    ) -> SecurityEventRequest:
        observed_time = observed_at or datetime.now(timezone.utc)
        payload = {
            "schema_version": NETWORK_FLOW_SCHEMA_VERSION,
            "collection_source": NETWORK_COLLECTOR_SOURCE,
            "collector_scope": self.collector_scope,
            "observed_at": observed_time.isoformat(),
            "quality_status": self.quality_status,
            "missing_fields": list(self.missing_fields),
            "model_ready": self.model_ready,
            "protocol": self.protocol,
            "source_ip": self.source_ip,
            "source_port": self.source_port,
            "destination_ip": self.destination_ip,
            "destination_port": self.destination_port,
            "forward_source_ip": self.forward_source_ip,
            "forward_source_port": self.forward_source_port,
            "forward_destination_ip": self.forward_destination_ip,
            "forward_destination_port": self.forward_destination_port,
            "flow_start_timestamp": self.flow_start_timestamp,
            "flow_end_timestamp": self.flow_end_timestamp,
            "flow_duration": self.flow_duration,
            "forward_packet_count": self.forward_packet_count,
            "backward_packet_count": self.backward_packet_count,
            "forward_byte_count": self.forward_byte_count,
            "backward_byte_count": self.backward_byte_count,
            "packet_rate": self.packet_rate,
            "byte_rate": self.byte_rate,
            "forward_backward_packet_ratio": self.forward_backward_packet_ratio,
        }
        return SecurityEventRequest(
            event_type=SecurityEventType.NETWORK,
            severity=SecurityEventSeverity.INFO,
            source=NETWORK_COLLECTOR_SOURCE,
            timestamp=observed_time,
            payload=payload,
        )

    def to_guardianx_v2_feature_vector(self) -> list[float]:
        """Return the exact GuardianX v2 feature vector for a completed flow."""
        required = (
            self.flow_duration,
            self.forward_packet_count,
            self.backward_packet_count,
            self.forward_byte_count,
            self.backward_byte_count,
            self.packet_rate,
            self.byte_rate,
        )
        if any(value is None for value in required):
            raise ValueError("CompletedFlowRecord is missing required GuardianX v2 telemetry.")

        if self.flow_duration <= 0:
            raise ValueError("CompletedFlowRecord flow_duration must be positive for GuardianX v2 inference.")

        is_one_way_flow = 1 if self.backward_packet_count == 0 else 0
        vector = [
            float(self.flow_duration),
            float(self.forward_packet_count),
            float(self.backward_packet_count),
            float(self.forward_byte_count),
            float(self.backward_byte_count),
            float(self.packet_rate),
            float(self.byte_rate),
            float(is_one_way_flow),
        ]

        if any(value < 0 for value in vector[:7]):
            raise ValueError("CompletedFlowRecord contains negative GuardianX v2 feature values.")

        if not all(math.isfinite(value) for value in vector):
            raise ValueError("CompletedFlowRecord contains non-finite GuardianX v2 feature values.")

        return vector


@dataclass
class _FlowState:
    key: tuple[FlowEndpoint, FlowEndpoint, str]
    forward_source: FlowEndpoint
    forward_destination: FlowEndpoint
    start_timestamp: float
    last_timestamp: float
    forward_packet_count: int = 0
    backward_packet_count: int = 0
    forward_byte_count: int = 0
    backward_byte_count: int = 0
    invalid_fields: set[str] = field(default_factory=set)

    def add(self, observation: PacketObservation) -> None:
        if observation.source == self.forward_source and observation.destination == self.forward_destination:
            self.forward_packet_count += 1
            self.forward_byte_count += observation.byte_count
        else:
            self.backward_packet_count += 1
            self.backward_byte_count += observation.byte_count
        self.last_timestamp = observation.timestamp
        if observation.byte_count < 0:
            self.invalid_fields.add("byte_count")


class BidirectionalFlowAggregator:
    """Aggregate packet metadata into completed bidirectional flow records."""

    def __init__(
        self,
        *,
        collector_scope: str = "local",
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        max_flow_lifetime_seconds: float = DEFAULT_MAX_FLOW_LIFETIME_SECONDS,
    ) -> None:
        if idle_timeout_seconds <= 0 or max_flow_lifetime_seconds <= 0:
            raise ValueError("Flow timeouts must be positive.")
        self.collector_scope = collector_scope
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_flow_lifetime_seconds = max_flow_lifetime_seconds
        self._flows: dict[tuple[FlowEndpoint, FlowEndpoint, str], _FlowState] = {}
        logger.info(
            "Network telemetry collector started idle_timeout=%s max_lifetime=%s",
            idle_timeout_seconds,
            max_flow_lifetime_seconds,
        )

    @property
    def active_flow_count(self) -> int:
        return len(self._flows)

    def observe(self, observation: PacketObservation) -> list[CompletedFlowRecord]:
        key = self._flow_key(observation)
        state = self._flows.get(key)
        if state is None:
            forward_source, forward_destination = self._initial_direction(observation)
            state = _FlowState(
                key=key,
                forward_source=forward_source,
                forward_destination=forward_destination,
                start_timestamp=observation.timestamp,
                last_timestamp=observation.timestamp,
            )
            self._flows[key] = state
            logger.debug("Created network flow protocol=%s", observation.normalized_protocol)
        state.add(observation)
        if observation.normalized_protocol == "TCP" and state_has_close_flag(observation):
            return [self._complete(key, "tcp_closed")]
        return []

    def expire(self, now: float) -> list[CompletedFlowRecord]:
        completed: list[CompletedFlowRecord] = []
        for key, state in list(self._flows.items()):
            if now - state.last_timestamp >= self.idle_timeout_seconds:
                completed.append(self._complete(key, "idle_timeout"))
            elif now - state.start_timestamp >= self.max_flow_lifetime_seconds:
                completed.append(self._complete(key, "max_lifetime"))
        return completed

    def flush(self) -> list[CompletedFlowRecord]:
        completed = [self._complete(key, "shutdown") for key in list(self._flows)]
        logger.info("Flushed %d active network flows", len(completed))
        return completed

    def _flow_key(self, observation: PacketObservation) -> tuple[FlowEndpoint, FlowEndpoint, str]:
        endpoints = tuple(sorted((observation.source, observation.destination)))
        return endpoints[0], endpoints[1], observation.normalized_protocol

    def _initial_direction(self, observation: PacketObservation) -> tuple[FlowEndpoint, FlowEndpoint]:
        flags = observation.normalized_tcp_flags
        if observation.normalized_protocol == "TCP" and "SYN" in flags and "ACK" not in flags:
            return observation.source, observation.destination
        return observation.source, observation.destination

    def _complete(self, key: tuple[FlowEndpoint, FlowEndpoint, str], reason: str) -> CompletedFlowRecord:
        state = self._flows.pop(key)
        duration = state.last_timestamp - state.start_timestamp
        total_packets = state.forward_packet_count + state.backward_packet_count
        total_bytes = state.forward_byte_count + state.backward_byte_count
        invalid_fields = set(state.invalid_fields)
        if duration <= 0:
            invalid_fields.add("flow_duration")
        if state.backward_packet_count == 0:
            ratio = None
        else:
            ratio = state.forward_packet_count / state.backward_packet_count
        if duration > 0 and not invalid_fields:
            packet_rate = total_packets / duration
            byte_rate = total_bytes / duration
        else:
            packet_rate = None
            byte_rate = None
        quality_status = "valid" if not invalid_fields else "invalid_telemetry"
        record = CompletedFlowRecord(
            collector_scope=self.collector_scope,
            protocol=key[2],
            source_ip=key[0].ip,
            source_port=key[0].port,
            destination_ip=key[1].ip,
            destination_port=key[1].port,
            forward_source_ip=state.forward_source.ip,
            forward_source_port=state.forward_source.port,
            forward_destination_ip=state.forward_destination.ip,
            forward_destination_port=state.forward_destination.port,
            flow_start_timestamp=state.start_timestamp,
            flow_end_timestamp=state.last_timestamp,
            flow_duration=duration,
            forward_packet_count=state.forward_packet_count,
            backward_packet_count=state.backward_packet_count,
            forward_byte_count=state.forward_byte_count,
            backward_byte_count=state.backward_byte_count,
            packet_rate=packet_rate,
            byte_rate=byte_rate,
            forward_backward_packet_ratio=ratio,
            quality_status=quality_status,
            missing_fields=tuple(sorted(invalid_fields)),
            model_ready=duration > 0 and not invalid_fields,
        )
        logger.info("Completed network flow reason=%s quality=%s", reason, quality_status)
        return record


def state_has_close_flag(observation: PacketObservation) -> bool:
    return bool({"FIN", "RST"} & observation.normalized_tcp_flags)


class NetworkTelemetryCollector:
    """Collector facade for a future packet source; it does not capture packets itself."""

    def __init__(
        self,
        *,
        aggregator: BidirectionalFlowAggregator | None = None,
        on_completed: Callable[[CompletedFlowRecord], None] | None = None,
    ) -> None:
        self.aggregator = aggregator or BidirectionalFlowAggregator()
        self.on_completed = on_completed

    def observe_packet(self, observation: PacketObservation) -> list[CompletedFlowRecord]:
        completed = self.aggregator.observe(observation)
        self._publish(completed)
        return completed

    def expire(self, now: float) -> list[CompletedFlowRecord]:
        completed = self.aggregator.expire(now)
        self._publish(completed)
        return completed

    def shutdown(self) -> list[CompletedFlowRecord]:
        completed = self.aggregator.flush()
        self._publish(completed)
        logger.info("Network telemetry collector shut down")
        return completed

    def _publish(self, records: Iterable[CompletedFlowRecord]) -> None:
        if self.on_completed is not None:
            for record in records:
                self.on_completed(record)