from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.api.dependencies import BackupRecoveryServiceDep
from app.database.session import SessionLocal
from app.models.backup import BackupSnapshot, RecoveryJob
from app.schemas.backup import (
    BackupResponse,
    BackupSchedulerStatusResponse,
    CreateBackupRequest,
    RecoveryJobResponse,
    StartRecoveryRequest,
)
from app.security.dependencies import CurrentUserDep
from app.services.backup import BackupRecoveryService
from app.services.backup_scheduler import (
    build_backup_scheduler,
    get_latest_persisted_scheduled_run,
    get_scheduled_device_owner,
)

router = APIRouter(tags=["Backup & Recovery"])


def _run_background(operation: str, record_id: UUID) -> None:
    with SessionLocal() as db:
        service = BackupRecoveryService(db)
        if operation == "backup":
            service.run_backup(record_id)
        elif operation == "verify":
            service.run_verification(record_id)
        elif operation == "recovery":
            service.run_recovery(record_id)
        else:
            raise ValueError(f"Unknown backup operation: {operation}")


@router.post("/backups", response_model=BackupResponse, status_code=status.HTTP_202_ACCEPTED)
def create_backup(
    request: CreateBackupRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> BackupSnapshot:
    try:
        backup = service.create_backup(
            user=current_user,
            source=request.source_directory,
            destination=request.destination_directory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    background_tasks.add_task(_run_background, "backup", backup.id)
    return backup


@router.get("/backups", response_model=list[BackupResponse])
def list_backups(
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> list[BackupSnapshot]:
    return service.list_backups(user=current_user)


@router.post(
    "/backups/{backup_id}/verify",
    response_model=BackupResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def verify_backup(
    backup_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> BackupSnapshot:
    try:
        backup = service.verify_backup(user=current_user, backup_id=backup_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    background_tasks.add_task(_run_background, "verify", backup.id)
    return backup


@router.post(
    "/backups/{backup_id}/restore",
    response_model=RecoveryJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_recovery(
    backup_id: UUID,
    request: StartRecoveryRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> RecoveryJob:
    try:
        job = service.start_recovery(
            user=current_user,
            backup_id=backup_id,
            recovery_directory=request.recovery_directory,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    background_tasks.add_task(_run_background, "recovery", job.id)
    return job


@router.get("/recovery-jobs", response_model=list[RecoveryJobResponse])
def list_recovery_jobs(
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> list[RecoveryJob]:
    return service.list_recovery_jobs(user=current_user)


@router.get("/recovery-jobs/{job_id}", response_model=RecoveryJobResponse)
def get_recovery_job(
    job_id: UUID,
    current_user: CurrentUserDep,
    service: BackupRecoveryServiceDep,
) -> RecoveryJob:
    try:
        return service.get_recovery_job(user=current_user, job_id=job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/backups/scheduler/status", response_model=BackupSchedulerStatusResponse)
def get_backup_scheduler_status(
    request: Request,
    current_user: CurrentUserDep,
) -> dict[str, object]:
    scheduler = getattr(request.app.state, "backup_scheduler", None)
    if scheduler is None:
        scheduler = build_backup_scheduler()
    status_result = scheduler.get_status()
    authorized_device_owner = (
        get_scheduled_device_owner(scheduler.device_agent_id)
        if scheduler.device_agent_id is not None
        else None
    )
    if (
        status_result["enabled"]
        and status_result["last_run_at"] is None
        and scheduler.source_directory
        and scheduler.destination_directory
        and authorized_device_owner == current_user.id
    ):
        persisted_result = get_latest_persisted_scheduled_run(
            scheduler.source_directory,
            scheduler.destination_directory,
            scheduler.device_agent_id,
        )
        if persisted_result is not None:
            status_result.update(persisted_result)
    if authorized_device_owner != current_user.id:
        status_result.update(
            {
                "last_run_at": None,
                "last_outcome": None,
                "backup_id": None,
                "error": None,
            }
        )
    return status_result
