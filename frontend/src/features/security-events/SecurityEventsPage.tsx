import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getSecurityEvents } from '../../api/securityEvents'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import type { ConsoleState, SecurityEvent } from '../../types/api'

interface SecurityEventsPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function SecurityEventsPage({ onConsoleStateChange, onLoadingChange, onSessionExpired, refreshSignal }: SecurityEventsPageProps) {
  const [events, setEvents] = useState<SecurityEvent[] | null>(null)
  const [error, setError] = useState(false)
  const [authenticationRequired, setAuthenticationRequired] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const loadEvents = useCallback(async () => {
    setIsLoading(true)
    setError(false)
    setAuthenticationRequired(false)
    onLoadingChange(true)
    onConsoleStateChange('checking')
    try {
      setEvents(await getSecurityEvents())
      onConsoleStateChange('authenticated')
    } catch (caughtError) {
      setEvents(null)
      setError(true)
      const requiresAuthentication = caughtError instanceof ApiError && caughtError.status === 401
      setAuthenticationRequired(requiresAuthentication)
      onConsoleStateChange(requiresAuthentication ? 'authentication-required' : 'unavailable')
      if (requiresAuthentication) onSessionExpired()
    } finally {
      setIsLoading(false)
      onLoadingChange(false)
    }
  }, [onConsoleStateChange, onLoadingChange, onSessionExpired])

  useEffect(() => {
    queueMicrotask(() => void loadEvents())
  }, [loadEvents, refreshSignal])

  if (isLoading && !events) return <LoadingState />
  if (error || !events) return <ErrorState authenticationRequired={authenticationRequired} onRetry={() => void loadEvents()} title="Unable to load security events" />

  return (
    <div className="events-content">
      <div className="inventory-heading">
        <div>
          <p className="eyebrow">Detection surface</p>
          <h2>Security events</h2>
          <p>Review security activity across your GuardianX endpoints.</p>
        </div>
        <strong className="inventory-total">{events.length}<span>Total events</span></strong>
      </div>
      {events.length === 0 ? (
        <section className="state-panel empty-state">
          <span className="state-mark state-mark-empty" aria-hidden="true">+</span>
          <div><h2>No security events recorded</h2><p>Events reported by GuardianX endpoints will appear here.</p></div>
        </section>
      ) : (
        <section className="inventory-table-panel">
          <table className="inventory-table security-events-table">
            <thead><tr><th>Timestamp</th><th>Event type</th><th>Severity</th><th>Source</th><th>Device identifier</th></tr></thead>
            <tbody>{events.map((event) => (
              <tr key={event.id}>
                <td>{formatTimestamp(event.timestamp)}</td>
                <td><strong>{event.event_type}</strong></td>
                <td><span className={`event-severity severity-${event.severity.toLowerCase()}`}>{event.severity}</span></td>
                <td>{event.source}</td>
                <td><span className="event-device-id">{event.device_id}</span></td>
              </tr>
            ))}</tbody>
          </table>
        </section>
      )}
    </div>
  )
}