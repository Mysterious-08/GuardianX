import { apiFetch } from './client'

export type BackupStatus = 'QUEUED' | 'RUNNING' | 'VERIFYING' | 'VERIFIED' | 'FAILED' | 'CORRUPT'
export type RecoveryStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED'

export interface BackupSnapshot {
  id: string
  source_directory: string
  destination_directory: string
  snapshot_directory: string
  device_id: string | null
  status: BackupStatus
  trigger: 'manual' | 'scheduled'
  file_count: number
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface RecoveryJob {
  id: string
  backup_id: string | null
  security_event_id: string | null
  device_id: string | null
  source_directory: string | null
  recovery_directory: string | null
  status: RecoveryStatus
  error: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface BackupSchedulerStatus {
  enabled: boolean
  state: 'disabled' | 'starting' | 'enabled' | 'misconfigured' | 'stopped'
  interval_minutes: number
  message: string | null
  last_run_at: string | null
  last_outcome: string | null
  backup_id: string | null
  error: string | null
}

export function getBackups(): Promise<BackupSnapshot[]> {
  return apiFetch<BackupSnapshot[]>('/backups')
}

export function createBackup(source_directory: string, destination_directory: string): Promise<BackupSnapshot> {
  return apiFetch<BackupSnapshot>('/backups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_directory, destination_directory }),
  })
}

export function verifyBackup(backupId: string): Promise<BackupSnapshot> {
  return apiFetch<BackupSnapshot>(`/backups/${backupId}/verify`, { method: 'POST' })
}

export function restoreBackup(backupId: string): Promise<RecoveryJob> {
  return apiFetch<RecoveryJob>(`/backups/${backupId}/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
}

export function getRecoveryJobs(): Promise<RecoveryJob[]> {
  return apiFetch<RecoveryJob[]>('/recovery-jobs')
}

export function getBackupSchedulerStatus(): Promise<BackupSchedulerStatus> {
  return apiFetch<BackupSchedulerStatus>('/backups/scheduler/status')
}
