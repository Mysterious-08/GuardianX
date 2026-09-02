from __future__ import annotations

"""Windows Scapy packet source for the network telemetry collector.

Scapy is deliberately contained in this module. The flow aggregation
primitives in :mod:`app.agent.collectors.network` remain packet-source
independent and can be used without Scapy installed.
"""

import logging
from collections.abc import Callable

from scapy.config import conf
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.inet6 import IPv6
from scapy.packet import Packet
from scapy.sendrecv import sniff

from .network import NetworkTelemetryCollector, PacketObservation


logger = logging.getLogger(__name__)

_TCP_FLAG_NAMES = {
    "F": "FIN", "S": "SYN", "R": "RST", "P": "PSH",
    "A": "ACK", "U": "URG", "E": "ECE", "C": "CWR",
}


def packet_to_observation(packet: Packet) -> PacketObservation | None:
    """Convert a supported Scapy packet to metadata-only flow input.

    Non-IP packets and IP packets without TCP or UDP are intentionally ignored.
    This function does not capture traffic and is suitable for synthetic tests.
    """
    if packet.haslayer(IP):
        ip_layer = packet[IP]
    elif packet.haslayer(IPv6):
        ip_layer = packet[IPv6]
    else:
        return None

    if packet.haslayer(TCP):
        transport = packet[TCP]
        protocol = "TCP"
        tcp_flags = _normalize_tcp_flags(transport.flags)
    elif packet.haslayer(UDP):
        transport = packet[UDP]
        protocol = "UDP"
        tcp_flags = frozenset()
    else:
        return None

    return PacketObservation(
        timestamp=float(packet.time),
        source_ip=str(ip_layer.src),
        source_port=int(transport.sport),
        destination_ip=str(ip_layer.dst),
        destination_port=int(transport.dport),
        protocol=protocol,
        byte_count=len(packet),
        tcp_flags=tcp_flags,
    )


def _normalize_tcp_flags(flags: object) -> frozenset[str]:
    """Map Scapy's compact TCP flags to ``PacketObservation`` flag names."""
    return frozenset(name for flag, name in _TCP_FLAG_NAMES.items() if flag in str(flags))


class WindowsScapyPacketSource:
    """Blocking, bounded Scapy capture that forwards observations to a collector."""

    def __init__(
        self,
        *,
        collector: NetworkTelemetryCollector,
        interface: str | None = None,
        capture_timeout: float | None = None,
        capture_count: int = 0,
        packet_filter: str | None = None,
        sniff_function: Callable[..., object] = sniff,
    ) -> None:
        if capture_timeout is not None and capture_timeout <= 0:
            raise ValueError("capture_timeout must be positive when provided.")
        if capture_count < 0:
            raise ValueError("capture_count cannot be negative.")
        self.collector = collector
        self.interface = interface
        self.capture_timeout = capture_timeout
        self.capture_count = capture_count
        self.packet_filter = packet_filter
        self._sniff_function = sniff_function

    def capture(self) -> None:
        """Capture once, forwarding supported packets to ``collector``.

        The configurable timeout and count are passed to Scapy. This method
        creates no background service.
        """
        # Npcap is the verified Windows capture backend for this adapter.
        conf.use_pcap = True
        sniff_options: dict[str, object] = {
            "iface": self.interface,
            "count": self.capture_count,
            "prn": self._handle_packet,
            "store": False,
        }
        if self.capture_timeout is not None:
            sniff_options["timeout"] = self.capture_timeout
        if self.packet_filter is not None:
            sniff_options["filter"] = self.packet_filter
        logger.info(
            "Starting bounded Windows Scapy capture interface=%s timeout=%s count=%s",
            self.interface or "default", self.capture_timeout, self.capture_count,
        )
        self._sniff_function(**sniff_options)
        logger.info("Windows Scapy capture completed.")

    def _handle_packet(self, packet: Packet) -> None:
        observation = packet_to_observation(packet)
        if observation is not None:
            self.collector.observe_packet(observation)
