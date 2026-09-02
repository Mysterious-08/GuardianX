import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getDevices } from '../../api/devices'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import type { ConsoleState, DeviceListResponse, DeviceSummary } from '../../types/api'

interface EndpointInventoryPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  onSelectDevice: (device: DeviceSummary) => void
  refreshSignal: number
}

function formatLastSeen(value: string | null): string {
  if (!value) return 'Never checked in'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Timestamp unavailable'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function EndpointInventoryPage({ onConsoleStateChange, onLoadingChange, onSessionExpired, onSelectDevice, refreshSignal }: EndpointInventoryPageProps) {
  const [result, setResult] = useState<DeviceListResponse | null>(null)
  const [error, setError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const loadDevices = useCallback(async () => {
    setIsLoading(true)
    setError(false)
    onLoadingChange(true)
    onConsoleStateChange('checking')
    try {
      setResult(await getDevices())
      onConsoleStateChange('authenticated')
    } catch (caughtError) {
      setResult(null)
      setError(true)
      const requiresAuthentication = caughtError instanceof ApiError && caughtError.status === 401
      onConsoleStateChange(requiresAuthentication ? 'authentication-required' : 'unavailable')
      if (requiresAuthentication) onSessionExpired()
    } finally {
      setIsLoading(false)
      onLoadingChange(false)
    }
  }, [onConsoleStateChange, onLoadingChange, onSessionExpired])

  useEffect(() => {
    queueMicrotask(() => void loadDevices())
  }, [loadDevices, refreshSignal])

  if (isLoading && !result) return <LoadingState />
  if (error || !result) return <ErrorState authenticationRequired={false} onRetry={() => void loadDevices()} />

  return (
    <div className="inventory-content">
      <div className="inventory-heading">
        <div>
          <p className="eyebrow">Managed endpoints</p>
          <h2>GuardianX-managed endpoints</h2>
          <p>Review the endpoints enrolled in this GuardianX console.</p>
        </div>
        <strong className="inventory-total">{result.total}<span>Total endpoints</span></strong>
      </div>
      {result.devices.length === 0 ? (
        <section className="state-panel empty-state">
          <span className="state-mark state-mark-empty" aria-hidden="true">+</span>
          <div><h2>No endpoints are enrolled yet</h2><p>Registered endpoints will appear here when they are added to GuardianX.</p></div>
        </section>
      ) : (
        <section className="inventory-table-panel">
          <table className="inventory-table">
            <thead><tr><th>Device</th><th>Hostname</th><th>Status</th><th>Last seen</th></tr></thead>
            <tbody>{result.devices.map((device) => (
              <tr className="inventory-row" key={device.id} tabIndex={0} onClick={() => onSelectDevice(device)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectDevice(device) } }}>
                <td><strong>{device.device_name ?? device.hostname}</strong>{device.device_name && <span>{device.id}</span>}</td>
                <td>{device.hostname}</td>
                <td><StatusBadge status={device.status} label={device.status === 'REGISTERED' && device.last_seen === null ? 'Uninitialized' : undefined} /></td>
                <td>{formatLastSeen(device.last_seen)}</td>
              </tr>
            ))}</tbody>
          </table>
        </section>
      )}
    </div>
  )
}
