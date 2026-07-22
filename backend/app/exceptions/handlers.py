from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions.device import (
    DeviceNotFoundError,
    DeviceOwnershipError,
    DeviceRegistrationError,
)


def _device_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a 404 response when a device cannot be found."""
    return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_404_NOT_FOUND)


def _device_ownership_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a 403 response when a device ownership rule is violated."""
    return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_403_FORBIDDEN)


def _device_registration_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a 409 response when device registration fails due to business rules."""
    return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_409_CONFLICT)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers for device-related errors.

    This single entry point allows the FastAPI application to wire domain
    exceptions to HTTP responses in a centralized and extensible manner.
    """
    app.add_exception_handler(DeviceNotFoundError, _device_not_found_handler)
    app.add_exception_handler(DeviceOwnershipError, _device_ownership_handler)
    app.add_exception_handler(DeviceRegistrationError, _device_registration_handler)
