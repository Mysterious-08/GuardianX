from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.models.backup import BackupSnapshot, BackupStatus, RecoveryJob, RecoveryStatus
from app.models.user import User

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
FILES_DIRECTORY = "files"
CHUNK_SIZE = 1024 * 1024
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SENSITIVE_NAMES = {
    ".aws",
    ".azure",
    ".docker",
    ".gcloud",
    ".gnupg",
    ".kube",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".ssh",
    "credential",
    "credentials",
    "appsettings.json",
    "config.json",
    "settings.json",
    "secrets.json",
    "firebase-adminsdk",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "private",
    "service-account",
    "service_account",
    "secret",
    "secrets",
    "token",
    "tokens",
}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore", ".properties"}


def _is_sensitive_name(part: str) -> bool:
    name = part.casefold()
    return (
        name in SENSITIVE_NAMES
        or name == ".env"
        or name.startswith(".env.")
        or any(
            word in name
            for word in (
                "credential",
                "password",
                "secret",
                "token",
                "config",
                "settings",
                "service-account",
                "service_account",
            )
        )
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _has_reparse_point(path: Path) -> bool:
    info = path.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _excluded(relative_path: PurePosixPath) -> bool:
    if any(_is_sensitive_name(part) for part in relative_path.parts):
        return True
    return relative_path.suffix.casefold() in SENSITIVE_SUFFIXES


class BackupRecoveryService:
    """Persist and execute file snapshots and isolated recovery jobs."""

    def __init__(
        self,
        db: Session,
        allowed_roots: Iterable[str | Path] | None = None,
    ) -> None:
        self.db = db
        configured_roots = settings.backup_allowed_root_list if allowed_roots is None else allowed_roots
        self.allowed_roots = tuple(Path(root).expanduser().resolve() for root in configured_roots)

    def _validate_path(self, value: str | Path, *, must_exist: bool) -> Path:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("Paths must be absolute and must not contain '..'.")

        current = Path(candidate.anchor)
        for part in candidate.parts[1:]:
            current = current / part
            try:
                if _has_reparse_point(current):
                    raise ValueError(f"Reparse points and symbolic links are not allowed: {current}")
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ValueError(f"Path component cannot be accessed: {current} ({exc}).") from exc

        try:
            resolved = candidate.resolve(strict=must_exist)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"Path cannot be accessed: {candidate} ({exc}).") from exc
        if not self.allowed_roots:
            raise ValueError("No filesystem roots are configured; set BACKUP_ALLOWED_ROOTS first.")
        if not any(_is_within(resolved, root) for root in self.allowed_roots):
            raise ValueError("The path is outside the configured BACKUP_ALLOWED_ROOTS.")

        root = next(root for root in self.allowed_roots if _is_within(resolved, root))
        if not root.is_dir():
            raise ValueError(f"Configured backup root does not exist or is not a directory: {root}")

        current = root
        for part in resolved.relative_to(root).parts:
            current = current / part
            if current.exists():
                if _has_reparse_point(current):
                    raise ValueError(f"Reparse points and symbolic links are not allowed: {current}")
                if current != resolved and not current.is_dir():
                    raise ValueError(f"Path component is not a directory: {current}")

        if must_exist and not resolved.exists():
            raise ValueError(f"Path does not exist: {resolved}")
        if resolved.exists() and not resolved.is_dir():
            raise ValueError(f"Path must be a directory: {resolved}")
        return resolved

    def _validate_source_and_destination(self, source: str, destination: str) -> tuple[Path, Path]:
        source_path = self._validate_path(source, must_exist=True)
        destination_path = self._validate_path(destination, must_exist=False)
        if not source_path.is_dir():
            raise ValueError("The source path must be an existing directory.")
        allowed_root = next(root for root in self.allowed_roots if _is_within(source_path, root))
        sensitive_path_parts = (allowed_root.name, *source_path.relative_to(allowed_root).parts)
        if any(_is_sensitive_name(part) for part in sensitive_path_parts):
            raise ValueError("The selected source path is a credential or secret directory.")
        if destination_path == source_path or _is_within(destination_path, source_path) or _is_within(source_path, destination_path):
            raise ValueError("The backup destination must not overlap the protected source directory.")
        return source_path, destination_path

    def validate_source_and_destination(self, source: str, destination: str) -> tuple[Path, Path]:
        """Validate configured backup paths with the same rules as manual backups."""
        return self._validate_source_and_destination(source, destination)

    def _get_backup(self, backup_id: UUID, user: User | None = None) -> BackupSnapshot:
        statement = select(BackupSnapshot).where(BackupSnapshot.id == backup_id)
        if user is not None:
            statement = statement.where(BackupSnapshot.user_id == user.id)
        backup = self.db.scalar(statement)
        if backup is None:
            raise LookupError("Backup snapshot not found.")
        return backup

    def _get_recovery(self, job_id: UUID, user: User | None = None) -> RecoveryJob:
        statement = select(RecoveryJob).where(RecoveryJob.id == job_id)
        if user is not None:
            statement = statement.where(RecoveryJob.user_id == user.id)
        job = self.db.scalar(statement)
        if job is None:
            raise LookupError("Recovery job not found.")
        return job

    def create_backup(
        self,
        *,
        user: User,
        source: str,
        destination: str,
        device_id: UUID | None = None,
    ) -> BackupSnapshot:
        source_path, destination_path = self._validate_source_and_destination(source, destination)
        if device_id is not None:
            device = self.db.scalar(
                select(Device).where(
                    Device.id == device_id,
                    Device.user_id == user.id,
                    Device.status != DeviceStatus.UNINSTALLED,
                )
            )
            if device is None:
                raise ValueError("The backup device must belong to the owner and remain registered.")
        try:
            backup = BackupSnapshot(
                user_id=user.id,
                device_id=device_id,
                source_directory=str(source_path),
                destination_directory=str(destination_path),
                snapshot_directory="",
                status=BackupStatus.QUEUED,
            )
            self.db.add(backup)
            self.db.flush()
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            snapshot_path = destination_path / f"guardianx-{timestamp}-{backup.id.hex}"
            backup.snapshot_directory = str(snapshot_path)
            self.db.commit()
            self.db.refresh(backup)
            return backup
        except Exception:
            self.db.rollback()
            raise

    def list_backups(self, *, user: User) -> list[BackupSnapshot]:
        statement = (
            select(BackupSnapshot)
            .where(BackupSnapshot.user_id == user.id)
            .order_by(BackupSnapshot.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def run_backup(self, backup_id: UUID, *, scheduled: bool = False) -> None:
        backup = self._get_backup(backup_id)
        backup.status = BackupStatus.RUNNING
        backup.started_at = datetime.now(timezone.utc)
        backup.error = None
        self.db.commit()

        try:
            source = self._validate_path(backup.source_directory, must_exist=True)
            destination = self._validate_path(backup.destination_directory, must_exist=False)
            if not source.is_dir():
                raise ValueError("The protected source directory is no longer accessible.")
            snapshot = self._validate_path(backup.snapshot_directory, must_exist=False)
            if not _is_within(snapshot, destination):
                raise ValueError("Snapshot path is outside its configured destination.")
            snapshot.mkdir(parents=True, exist_ok=False)
            files_root = snapshot / FILES_DIRECTORY
            files_root.mkdir()
            entries = self._copy_source_tree(source, files_root)
            manifest: dict[str, Any] = {"version": 1, "files": entries}
            if scheduled:
                manifest["trigger"] = "scheduled"
            manifest_path = snapshot / MANIFEST_NAME
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            backup.manifest = manifest
            self.db.commit()
            self._verify_snapshot(backup)
            backup.status = BackupStatus.VERIFIED
            backup.completed_at = datetime.now(timezone.utc)
            backup.error = None
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            failed = self._get_backup(backup_id)
            failed.status = BackupStatus.FAILED
            failed.completed_at = datetime.now(timezone.utc)
            failed.error = str(exc) or exc.__class__.__name__
            self.db.commit()
            logger.exception("Backup %s failed.", backup_id)

    def _copy_source_tree(self, source: Path, files_root: Path) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def copy_directory(directory: Path, relative_directory: PurePosixPath) -> None:
            for item in sorted(os.scandir(directory), key=lambda entry: entry.name.casefold()):
                relative = relative_directory / item.name
                source_item = Path(item.path)
                if _has_reparse_point(source_item):
                    raise ValueError(f"Symbolic links and reparse points are not backed up: {source_item}")
                if _excluded(relative):
                    continue
                if item.is_dir(follow_symlinks=False):
                    copy_directory(source_item, relative)
                    continue
                if not item.is_file(follow_symlinks=False):
                    raise ValueError(f"Unsupported filesystem entry: {source_item}")
                resolved_item = source_item.resolve(strict=True)
                if not _is_within(resolved_item, source):
                    raise ValueError(f"Source entry escapes the protected directory: {source_item}")
                target = files_root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                before = source_item.stat()
                digest = hashlib.sha256()
                size = 0
                with source_item.open("rb") as source_stream, target.open("xb") as target_stream:
                    while chunk := source_stream.read(CHUNK_SIZE):
                        target_stream.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                after = source_item.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f"Source file changed while being backed up: {source_item}")
                entries.append(
                    {"path": relative.as_posix(), "size": size, "sha256": digest.hexdigest()}
                )

        copy_directory(source, PurePosixPath())
        return entries

    def verify_backup(self, *, user: User, backup_id: UUID) -> BackupSnapshot:
        backup = self._get_backup(backup_id, user)
        if backup.status in (BackupStatus.QUEUED, BackupStatus.RUNNING, BackupStatus.VERIFYING):
            raise RuntimeError("Backup is already queued or being processed.")
        backup.status = BackupStatus.VERIFYING
        backup.error = None
        backup.completed_at = None
        backup.started_at = None
        self.db.commit()
        return backup

    def run_verification(self, backup_id: UUID) -> None:
        backup = self._get_backup(backup_id)
        backup.started_at = datetime.now(timezone.utc)
        self.db.commit()
        try:
            self._verify_snapshot(backup)
            backup.status = BackupStatus.VERIFIED
            backup.error = None
        except Exception as exc:
            backup.status = BackupStatus.CORRUPT
            backup.error = str(exc) or exc.__class__.__name__
            logger.exception("Backup verification failed for %s.", backup_id)
        backup.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _verify_snapshot(self, backup: BackupSnapshot) -> dict[str, Any]:
        destination = self._validate_path(backup.destination_directory, must_exist=False)
        snapshot = self._validate_path(backup.snapshot_directory, must_exist=True)
        if not _is_within(snapshot, destination) or snapshot == destination:
            raise ValueError("Snapshot path is outside its recorded backup destination.")
        with os.scandir(snapshot) as entries:
            top_level: set[str] = set()
            for item in entries:
                item_path = Path(item.path)
                if _has_reparse_point(item_path):
                    raise ValueError(f"Snapshot contains a symbolic link or reparse point: {item_path}")
                top_level.add(item.name)
        if top_level != {MANIFEST_NAME, FILES_DIRECTORY}:
            raise ValueError("Snapshot has missing or unexpected top-level contents.")

        manifest_path = snapshot / MANIFEST_NAME
        if not manifest_path.exists():
            raise ValueError("Snapshot manifest is missing.")
        if _has_reparse_point(manifest_path) or not manifest_path.is_file():
            raise ValueError("Snapshot manifest is missing or is not a regular file.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Snapshot manifest cannot be read: {exc}") from exc
        if not isinstance(manifest, dict) or manifest.get("version") != 1 or not isinstance(manifest.get("files"), list):
            raise ValueError("Snapshot manifest has an unsupported or invalid format.")
        if backup.manifest != manifest:
            raise ValueError("Snapshot manifest does not match the persisted backup record.")

        expected: dict[str, dict[str, Any]] = {}
        for entry in manifest["files"]:
            if not isinstance(entry, dict):
                raise ValueError("Snapshot manifest contains an invalid file entry.")
            relative = entry.get("path")
            size = entry.get("size")
            digest = entry.get("sha256")
            posix_path = PurePosixPath(relative) if isinstance(relative, str) else None
            windows_path = PureWindowsPath(relative) if isinstance(relative, str) else None
            if (
                posix_path is None
                or not relative
                or posix_path.is_absolute()
                or windows_path is None
                or windows_path.is_absolute()
                or bool(windows_path.drive)
                or ".." in posix_path.parts
                or "\\" in relative
                or ":" in relative
                or any(part in ("", ".") for part in posix_path.parts)
            ):
                raise ValueError(f"Unsafe path in snapshot manifest: {relative!r}")
            if not isinstance(size, int) or size < 0 or not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
                raise ValueError(f"Invalid size or SHA-256 value for {relative}.")
            if relative in expected:
                raise ValueError(f"Duplicate path in snapshot manifest: {relative}.")
            expected[relative] = entry

        files_root = snapshot / FILES_DIRECTORY
        if not files_root.exists() or _has_reparse_point(files_root) or not files_root.is_dir():
            raise ValueError("Snapshot files directory is missing or unsafe.")
        actual_files = self._list_snapshot_files(files_root)
        if set(actual_files) != set(expected):
            missing = sorted(set(expected) - set(actual_files))
            extra = sorted(set(actual_files) - set(expected))
            details = []
            if missing:
                details.append(f"missing files: {', '.join(missing[:10])}")
            if extra:
                details.append(f"unexpected files: {', '.join(extra[:10])}")
            raise ValueError("Snapshot contents do not match the manifest (" + "; ".join(details) + ").")

        for relative, file_path in actual_files.items():
            expected_entry = expected[relative]
            digest = hashlib.sha256()
            size = 0
            with file_path.open("rb") as stream:
                while chunk := stream.read(CHUNK_SIZE):
                    digest.update(chunk)
                    size += len(chunk)
            if size != expected_entry["size"] or digest.hexdigest() != expected_entry["sha256"]:
                raise ValueError(f"Snapshot file failed integrity verification: {relative}.")
        return manifest

    def _list_snapshot_files(self, files_root: Path) -> dict[str, Path]:
        result: dict[str, Path] = {}

        def scan(directory: Path) -> None:
            for item in os.scandir(directory):
                path = Path(item.path)
                if _has_reparse_point(path):
                    raise ValueError(f"Snapshot contains a symbolic link or reparse point: {path}")
                if item.is_dir(follow_symlinks=False):
                    scan(path)
                elif item.is_file(follow_symlinks=False):
                    result[path.relative_to(files_root).as_posix()] = path
                else:
                    raise ValueError(f"Snapshot contains an unsupported filesystem entry: {path}")

        scan(files_root)
        return result

    def start_recovery(
        self,
        *,
        user: User,
        backup_id: UUID,
        recovery_directory: str | None = None,
        security_event_id: UUID | None = None,
    ) -> RecoveryJob:
        backup = self._get_backup(backup_id, user)
        if backup.status is not BackupStatus.VERIFIED:
            raise RuntimeError("Only a VERIFIED backup can be restored.")
        recovery_root = self._get_recovery_root(backup)
        requested_path = (
            recovery_root / backup.id.hex
            if recovery_directory is None
            else self._validate_path(recovery_directory, must_exist=False)
        )
        if not _is_within(requested_path, recovery_root) or requested_path == recovery_root:
            raise ValueError("Recovery destination must be inside the configured RECOVERY_ROOT.")
        recovery_path = self._validate_path(requested_path, must_exist=False)
        if recovery_path.exists():
            raise ValueError("Recovery destination already exists; choose a new directory.")
        try:
            job = RecoveryJob(
                backup_id=backup.id,
                security_event_id=security_event_id,
                device_id=backup.device_id,
                user_id=user.id,
                source_directory=str(backup.source_directory),
                recovery_directory=str(recovery_path),
                status=RecoveryStatus.QUEUED,
            )
            self.db.add(job)
            job.recovery_directory = str(recovery_path)
            self.db.commit()
            self.db.refresh(job)
            return job
        except Exception:
            self.db.rollback()
            raise

    def list_recovery_jobs(self, *, user: User) -> list[RecoveryJob]:
        statement = (
            select(RecoveryJob)
            .where(RecoveryJob.user_id == user.id)
            .order_by(RecoveryJob.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_recovery_job(self, *, user: User, job_id: UUID) -> RecoveryJob:
        return self._get_recovery(job_id, user)

    def _get_recovery_root(self, backup: BackupSnapshot) -> Path:
        source = self._validate_path(backup.source_directory, must_exist=True)
        backup_destination = self._validate_path(backup.destination_directory, must_exist=False)
        snapshot = self._validate_path(backup.snapshot_directory, must_exist=True)

        if settings.recovery_root is not None:
            recovery_root = self._validate_path(settings.recovery_root, must_exist=False)
        else:
            candidates = [
                root
                for root in self.allowed_roots
                if not any(
                    _is_within(root, protected) or _is_within(protected, root)
                    for protected in (source, backup_destination, snapshot)
                )
            ]
            if len(candidates) != 1:
                raise ValueError(
                    "Set RECOVERY_ROOT to a directory in BACKUP_ALLOWED_ROOTS that is separate "
                    "from the protected source and backup destination."
                )
            recovery_root = self._validate_path(candidates[0], must_exist=False)

        if any(
            _is_within(recovery_root, protected) or _is_within(protected, recovery_root)
            for protected in (source, backup_destination, snapshot)
        ):
            raise ValueError(
                "RECOVERY_ROOT must be separate from the protected source, backup destination, "
                "and snapshot."
            )
        return recovery_root

    def run_recovery(self, job_id: UUID) -> None:
        job = self._get_recovery(job_id)
        job.status = RecoveryStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.error = None
        self.db.commit()
        recovery_path = Path(job.recovery_directory)
        backup: BackupSnapshot | None = None
        verified_during_recovery = False

        try:
            backup = self._get_backup(job.backup_id)
            if backup.status is not BackupStatus.VERIFIED:
                raise ValueError("Recovery refused because the snapshot is not VERIFIED.")
            manifest = self._verify_snapshot(backup)
            verified_during_recovery = True
            destination = self._validate_path(job.recovery_directory, must_exist=False)
            if destination.exists():
                raise ValueError("Recovery destination already exists; refusing to overwrite files.")
            self._validate_path(backup.snapshot_directory, must_exist=True)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.mkdir(exist_ok=False)

            files_root = Path(backup.snapshot_directory) / FILES_DIRECTORY
            for entry in manifest["files"]:
                relative = PurePosixPath(entry["path"])
                source_file = files_root.joinpath(*relative.parts)
                target_file = destination.joinpath(*relative.parts)
                if _has_reparse_point(source_file):
                    raise ValueError(f"Snapshot file became unsafe before recovery: {entry['path']}.")
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_file, target_file)
            self._verify_restored_tree(destination, manifest)
            job.status = RecoveryStatus.COMPLETED
            job.error = None
        except Exception as exc:
            self.db.rollback()
            job = self._get_recovery(job_id)
            job.status = RecoveryStatus.FAILED
            job.error = str(exc) or exc.__class__.__name__
            if backup is not None and not verified_during_recovery:
                backup = self._get_backup(backup.id)
                backup.status = BackupStatus.CORRUPT
                backup.error = job.error
                backup.completed_at = datetime.now(timezone.utc)
            logger.exception("Recovery job %s failed.", job_id)
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _verify_restored_tree(self, root: Path, manifest: dict[str, Any]) -> None:
        expected = {entry["path"]: entry for entry in manifest["files"]}
        actual = self._list_snapshot_files(root)
        if set(actual) != set(expected):
            raise ValueError("Restored contents do not match the snapshot manifest.")
        for relative, path in actual.items():
            digest = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                while chunk := stream.read(CHUNK_SIZE):
                    digest.update(chunk)
                    size += len(chunk)
            entry = expected[relative]
            if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                raise ValueError(f"Restored file failed integrity verification: {relative}.")
