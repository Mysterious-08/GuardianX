from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.models.security_event import SecurityEvent


class RecoveryEligibilityPolicy(Protocol):
    def is_eligible(self, event: SecurityEvent) -> bool:
        """Return whether an event is explicitly eligible for recovery consideration."""


class ExplicitFileIntegrityPolicy:
    """Require explicit file integrity evidence and an in-source file identity.

    The booleans are agent attestations; file/source identity is independently
    checked against the registered device's matching snapshot before restore.
    """

    def is_eligible(self, event: SecurityEvent) -> bool:
        return self.ineligibility_reason(event) is None

    def ineligibility_reason(self, event: SecurityEvent) -> str | None:
        if event.event_type.value != "FILE":
            return "Only FILE security events can be considered for recovery."
        if event.payload.get("recovery_eligible") is not True:
            return "The file event is not explicitly marked as recovery eligible."
        if event.payload.get("integrity_verified") is not True:
            return "The file event does not contain explicit integrity verification."
        source_directory = event.payload.get("source_directory")
        file_path = event.payload.get("file_path")
        if not isinstance(source_directory, str) or not source_directory.strip():
            return "The event is missing its protected source directory."
        if not isinstance(file_path, str) or not file_path.strip():
            return "The event is missing the affected file path."
        source = Path(os.path.expandvars(source_directory)).expanduser()
        affected_file = Path(os.path.expandvars(file_path)).expanduser()
        if not source.is_absolute() or not affected_file.is_absolute():
            return "The source directory and affected file path must be absolute."
        try:
            resolved_source = source.resolve(strict=False)
            resolved_file = affected_file.resolve(strict=False)
            resolved_file.relative_to(resolved_source)
        except (OSError, RuntimeError, ValueError):
            return "The affected file path is outside the reported source directory."
        if resolved_file == resolved_source:
            return "The affected file path must identify a file beneath the source directory."
        return None


class RecoveryOrchestrator:
    """Apply the single recovery eligibility policy used by event orchestration."""

    def __init__(self, policy: RecoveryEligibilityPolicy) -> None:
        self.policy = policy

    def is_recovery_eligible(self, event: SecurityEvent) -> bool:
        return self.policy.is_eligible(event)

    def ineligibility_reason(self, event: SecurityEvent) -> str | None:
        reason_getter = getattr(self.policy, "ineligibility_reason", None)
        if reason_getter is not None:
            return reason_getter(event)
        return None if self.is_recovery_eligible(event) else "The event is not eligible for recovery."
