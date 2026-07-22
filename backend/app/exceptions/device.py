from __future__ import annotations


class DeviceError(Exception):
    """Base exception for device-related business rule failures."""


class DeviceNotFoundError(DeviceError):
    """Raised when a device cannot be found in persistence."""


class DeviceOwnershipError(DeviceError):
    """Raised when an operation violates device ownership constraints."""


class DeviceRegistrationError(DeviceError):
    """Raised when a device registration attempt fails due to business rules."""
