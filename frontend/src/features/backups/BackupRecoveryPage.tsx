import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import {
  createBackup,
  getBackupSchedulerStatus,
  getBackups,
  getRecoveryJobs,
  restoreBackup,
  verifyBackup,
} from '../../api/backups'
import type { BackupSchedulerStatus, BackupSnapshot, RecoveryJob } from '../../api/backups'
import { LoadingState } from '../../components/LoadingState'
import type { ConsoleState } from '../../types/api'

interface BackupRecoveryPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

type BackupDataOperation = 'backups' | 'recoveryJobs' | 'scheduler'

const OPERATION_LABELS: Record<BackupDataOperation, string> = {
  backups: 'snapshots',
  recoveryJobs: 'recovery jobs',
  scheduler: 'automatic backup status',
}

function formatTimestamp(value: string | null): string {
  if (!value) return 'Not yet completed'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Timestamp unavailable'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function humanizeStatus(status: string): string {
  return status.toLowerCase().replaceAll('_', ' ')
}

function describeOperationError(operation: string, error: unknown): string {
  if (error instanceof TypeError && /fetch|network/i.test(error.message)) {
    return `Could not load ${operation}: GuardianX could not be reached. Check the backend connection and retry.`
  }
  const detail = error instanceof Error ? error.message : 'An unexpected error occurred.'
  return `${operation} failed: ${detail}`
}

function OperationError({
  loading,
  message,
  operation,
  onRetry,
}: {
  loading: boolean
  message: string
  operation: string
  onRetry: () => void
}) {
  return (
    <div className="backup-operation-error" role="alert">
      <p>{message}</p>
      <button
        className="button button-secondary"
        type="button"
        onClick={onRetry}
        disabled={loading}
        aria-label={`Retry loading ${operation}`}
      >
        {loading ? 'Retrying…' : 'Retry'}
      </button>
    </div>
  )
}

export function BackupRecoveryPage({
  onConsoleStateChange,
  onLoadingChange,
  onSessionExpired,
  refreshSignal,
}: BackupRecoveryPageProps) {
  const [backups, setBackups] = useState<BackupSnapshot[]>([])
  const [jobs, setJobs] = useState<RecoveryJob[]>([])
  const [schedulerStatus, setSchedulerStatus] = useState<BackupSchedulerStatus | null>(null)
  const [sourcePath, setSourcePath] = useState('')
  const [destinationPath, setDestinationPath] = useState('')
  const [operationErrors, setOperationErrors] = useState<Partial<Record<BackupDataOperation, string>>>({})
  const [loadingOperations, setLoadingOperations] = useState<BackupDataOperation[]>([])
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; message: string } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [activeAction, setActiveAction] = useState<string | null>(null)

  const loadOperation = useCallback(async (operation: BackupDataOperation): Promise<boolean> => {
    setLoadingOperations((current) => current.includes(operation) ? current : [...current, operation])
    try {
      if (operation === 'backups') setBackups(await getBackups())
      if (operation === 'recoveryJobs') setJobs(await getRecoveryJobs())
      if (operation === 'scheduler') setSchedulerStatus(await getBackupSchedulerStatus())
      setOperationErrors((current) => {
        const next = { ...current }
        delete next[operation]
        return next
      })
      return true
    } catch (caughtError) {
      setOperationErrors((current) => ({
        ...current,
        [operation]: describeOperationError(`Loading ${OPERATION_LABELS[operation]}`, caughtError),
      }))
      if (caughtError instanceof ApiError && caughtError.status === 401) onSessionExpired()
      return false
    } finally {
      setHasLoaded(true)
      setLoadingOperations((current) => current.filter((item) => item !== operation))
    }
  }, [onSessionExpired])

  const loadData = useCallback(async () => {
    setIsLoading(true)
    onLoadingChange(true)
    onConsoleStateChange('checking')
    const outcomes = await Promise.all([
      loadOperation('backups'),
      loadOperation('recoveryJobs'),
      loadOperation('scheduler'),
    ])
    setHasLoaded(true)
    onConsoleStateChange(outcomes.every(Boolean) ? 'authenticated' : 'unavailable')
    setIsLoading(false)
    onLoadingChange(false)
  }, [loadOperation, onConsoleStateChange, onLoadingChange])

  const retryOperation = useCallback(async (operation: BackupDataOperation) => {
    onLoadingChange(true)
    const succeeded = await loadOperation(operation)
    const hasOtherErrors = Object.keys(operationErrors).some((key) => key !== operation)
    if (succeeded) onConsoleStateChange(hasOtherErrors ? 'unavailable' : 'authenticated')
    else if (operationErrors[operation] === undefined) onConsoleStateChange('unavailable')
    onLoadingChange(false)
  }, [loadOperation, onConsoleStateChange, onLoadingChange, operationErrors])

  useEffect(() => {
    queueMicrotask(() => void loadData())
  }, [loadData, refreshSignal])

  const hasPendingWork = backups.some((backup) => ['QUEUED', 'RUNNING', 'VERIFYING'].includes(backup.status))
    || jobs.some((job) => ['QUEUED', 'RUNNING'].includes(job.status))

  useEffect(() => {
    const refreshInterval = hasPendingWork ? 2000 : 30000
    const timer = window.setInterval(() => void loadData(), refreshInterval)
    return () => window.clearInterval(timer)
  }, [hasPendingWork, loadData])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFeedback(null)
    setActiveAction('create')
    try {
      const backup = await createBackup(sourcePath, destinationPath)
      setFeedback({ kind: 'success', message: `Backup ${backup.id} queued. Its integrity status will update when processing finishes.` })
      await loadData()
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) onSessionExpired()
      setFeedback({ kind: 'error', message: describeOperationError('Creating the backup', caughtError) })
    } finally {
      setActiveAction(null)
    }
  }

  async function handleVerify(backup: BackupSnapshot) {
    setFeedback(null)
    setActiveAction(`verify-${backup.id}`)
    try {
      await verifyBackup(backup.id)
      setFeedback({ kind: 'success', message: `Verification started for snapshot ${backup.id}.` })
      await loadData()
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) onSessionExpired()
      setFeedback({ kind: 'error', message: describeOperationError('Starting snapshot verification', caughtError) })
    } finally {
      setActiveAction(null)
    }
  }

  async function handleRestore(backup: BackupSnapshot) {
    if (!window.confirm('Restore this verified snapshot into a new recovery directory? Original files will not be overwritten.')) return
    setFeedback(null)
    setActiveAction(`restore-${backup.id}`)
    try {
      const job = await restoreBackup(backup.id)
      setFeedback({ kind: 'success', message: `Recovery job ${job.id} started in a separate directory.` })
      await loadData()
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) onSessionExpired()
      setFeedback({ kind: 'error', message: describeOperationError('Starting recovery', caughtError) })
    } finally {
      setActiveAction(null)
    }
  }

  if (isLoading && !hasLoaded) return <LoadingState />

  return (
    <div className="backup-content">
      <div className="inventory-heading">
        <div>
          <p className="eyebrow">File protection</p>
          <h2>Backup snapshots</h2>
          <p>Snapshots are verified before they can be restored. Recovery always uses a separate directory.</p>
        </div>
        <strong className="inventory-total">{backups.length}<span>Snapshots</span></strong>
      </div>

      <section className="panel-surface backup-scheduler-panel" aria-label="Automatic backup schedule">
        <div>
          <p className="eyebrow">Automatic backups</p>
          <h2>Scheduler {schedulerStatus && <span className={`backup-status backup-status-${schedulerStatus.state}`}>{schedulerStatus.state}</span>}</h2>
          {schedulerStatus ? (
            <>
              <p>
                {schedulerStatus.enabled
                  ? `Configured interval: every ${schedulerStatus.interval_minutes} minutes`
                  : 'Scheduled backups are disabled by configuration.'}
              </p>
              {schedulerStatus.message && <p className={schedulerStatus.state === 'misconfigured' ? 'backup-error-detail' : 'backup-scheduler-message'}>{schedulerStatus.message}</p>}
            </>
          ) : (
            !operationErrors.scheduler && <p>{loadingOperations.includes('scheduler') ? 'Loading automatic backup status…' : 'Automatic backup status is not available.'}</p>
          )}
          {operationErrors.scheduler && (
            <OperationError
              message={operationErrors.scheduler}
              operation={OPERATION_LABELS.scheduler}
              loading={loadingOperations.includes('scheduler')}
              onRetry={() => void retryOperation('scheduler')}
            />
          )}
        </div>
        {schedulerStatus && (
          <div className="backup-scheduler-last-run">
            <span>Last scheduled run</span>
            <strong>{schedulerStatus.last_run_at ? formatTimestamp(schedulerStatus.last_run_at) : 'No run recorded this session'}</strong>
            {schedulerStatus.last_outcome && <span>Outcome: {humanizeStatus(schedulerStatus.last_outcome)}</span>}
            {schedulerStatus.backup_id && <span>Snapshot: {schedulerStatus.backup_id}</span>}
            {schedulerStatus.error && <span className="backup-error-detail">{schedulerStatus.error}</span>}
          </div>
        )}
      </section>

      <section className="panel-surface backup-create-panel">
        <div>
          <p className="eyebrow">New snapshot</p>
          <h2>Create backup</h2>
          <p>Choose directories permitted by the backend&apos;s <code>BACKUP_ALLOWED_ROOTS</code> configuration.</p>
        </div>
        <form className="backup-form" onSubmit={(event) => void handleCreate(event)}>
          <label>
            Protected source directory
            <input
              autoComplete="off"
              required
              value={sourcePath}
              onChange={(event) => setSourcePath(event.target.value)}
              placeholder="C:\Users\Public\Documents\protected"
            />
          </label>
          <label>
            Backup destination directory (outside source)
            <input
              autoComplete="off"
              required
              value={destinationPath}
              onChange={(event) => setDestinationPath(event.target.value)}
              placeholder="D:\GuardianX\Backups"
            />
          </label>
          <button className="button backup-primary-button" type="submit" disabled={activeAction !== null}>
            {activeAction === 'create' ? 'Creating…' : 'Create backup'}
          </button>
        </form>
      </section>

      {feedback && (
        <p className={`backup-feedback backup-feedback-${feedback.kind}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>
          {feedback.message}
        </p>
      )}
      <section className="panel-surface backup-list-panel">
        <div className="backup-section-heading">
          <div><p className="eyebrow">Integrity</p><h2>Snapshots</h2></div>
          <button className="button button-refresh" type="button" onClick={() => void loadData()} disabled={isLoading} aria-label="Refresh snapshots, recovery jobs, and scheduler status">
            <span aria-hidden="true">↻</span>{isLoading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
        {operationErrors.backups && (
          <OperationError
            message={operationErrors.backups}
            operation={OPERATION_LABELS.backups}
            loading={loadingOperations.includes('backups')}
            onRetry={() => void retryOperation('backups')}
          />
        )}
        {backups.length === 0 && !operationErrors.backups ? (
          <p className="backup-empty">
            {loadingOperations.includes('backups')
              ? 'Loading snapshots…'
              : 'No snapshots yet. Create a backup from an allowed source and destination.'}
          </p>
        ) : backups.length > 0 && (
          <div className="backup-table-wrapper">
            <table className="backup-table">
              <thead>
                <tr>
                  <th scope="col">Created</th>
                  <th scope="col">Protected source</th>
                  <th scope="col">Type</th>
                  <th scope="col">Integrity</th>
                  <th scope="col">Files</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((backup) => {
                  const actionBusy = activeAction === `verify-${backup.id}` || activeAction === `restore-${backup.id}`
                  return (
                    <tr key={backup.id}>
                      <td>{formatTimestamp(backup.created_at)}<span className="backup-path">{backup.snapshot_directory}</span></td>
                      <td><span className="backup-path">{backup.source_directory}</span></td>
                      <td>{backup.trigger === 'scheduled' ? 'Automatic' : 'Manual'}</td>
                      <td>
                        <span className={`backup-status backup-status-${backup.status.toLowerCase()}`}>{humanizeStatus(backup.status)}</span>
                        {backup.error && <span className="backup-error-detail" title={backup.error}>{backup.error}</span>}
                      </td>
                      <td>{backup.file_count}</td>
                      <td>
                        <div className="backup-actions">
                          <button
                            className="button button-secondary backup-verify-button"
                            type="button"
                            disabled={actionBusy || ['QUEUED', 'RUNNING', 'VERIFYING'].includes(backup.status)}
                            onClick={() => void handleVerify(backup)}
                          >
                            {activeAction === `verify-${backup.id}` ? 'Verifying…' : 'Verify'}
                          </button>
                          <button
                            className="button backup-restore-button"
                            type="button"
                            disabled={actionBusy || backup.status !== 'VERIFIED'}
                            onClick={() => void handleRestore(backup)}
                          >
                            Restore
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel-surface recovery-jobs-panel">
        <div className="backup-section-heading">
          <div><p className="eyebrow">Restore activity</p><h2>Recovery jobs</h2></div>
        </div>
        {operationErrors.recoveryJobs && (
          <OperationError
            message={operationErrors.recoveryJobs}
            operation={OPERATION_LABELS.recoveryJobs}
            loading={loadingOperations.includes('recoveryJobs')}
            onRetry={() => void retryOperation('recoveryJobs')}
          />
        )}
        {jobs.length === 0 && !operationErrors.recoveryJobs ? (
          <p className="backup-empty">
            {loadingOperations.includes('recoveryJobs')
              ? 'Loading recovery jobs…'
              : 'No recovery jobs have been started.'}
          </p>
        ) : jobs.length > 0 && (
          <ul className="recovery-job-list">
            {jobs.map((job) => (
              <li key={job.id}>
                <div>
                  <strong>{humanizeStatus(job.status)}</strong>
                  <span>Created {formatTimestamp(job.created_at)} · Completed {formatTimestamp(job.completed_at)}</span>
                  {job.security_event_id && <span>Incident {job.security_event_id}</span>}
                  {job.backup_id && <span>Snapshot {job.backup_id}</span>}
                  {job.source_directory && <span className="backup-path">Protected source: {job.source_directory}</span>}
                  {job.recovery_directory && <span className="backup-path">Recovery destination: {job.recovery_directory}</span>}
                  {job.error && <span className="backup-error-detail">{job.error}</span>}
                </div>
                <span className={`backup-status backup-status-${job.status.toLowerCase()}`}>{humanizeStatus(job.status)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
