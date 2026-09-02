"""Compatibility imports for the Windows Scapy packet-source adapter.

New code should import from ``app.agent.collectors.scapy_windows``.
"""

from .collectors.scapy_windows import WindowsScapyPacketSource, packet_to_observation


WindowsPacketCapture = WindowsScapyPacketSource

__all__ = ["WindowsPacketCapture", "WindowsScapyPacketSource", "packet_to_observation"]
