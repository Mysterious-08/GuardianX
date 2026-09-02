import type { DeviceSummary, SecurityEvent } from '../../types/api'

interface SecurityEventStreamProps {
  events: SecurityEvent[]
  devices: DeviceSummary[]
  onOpenSecurityEvents: () => void
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Timestamp unavailable'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function getDeviceLabel(deviceId: string, devices: DeviceSummary[]): string {
  const device = devices.find((item) => item.id === deviceId)
  return device ? (device.device_name ?? device.hostname) : deviceId
}

function hasMlDetection(event: SecurityEvent): boolean {
  const payload = event.payload as Record<string, unknown> | undefined
  if (!payload || typeof payload !== 'object') return false
  const ml = payload.ml_detection as Record<string, unknown> | undefined
  return Boolean(ml && typeof ml === 'object')
}

export function SecurityEventStream({ events, devices, onOpenSecurityEvents }: SecurityEventStreamProps) {
  const stream = events.slice(0, 6)

  return (
    <section className="panel-surface stream-panel">
      <div className="panel-topline">
        <div>
          <p className="eyebrow">Live backend stream</p>
          <h2>Security event stream</h2>
        </div>
        <button className="text-action" type="button" onClick={onOpenSecurityEvents}>Open Security Events</button>
      </div>

      {stream.length === 0 ? (
        <div className="empty-inline">
          <strong>No security events recorded.</strong>
          <span>Events reported by GuardianX endpoints will appear here when telemetry is recorded.</span>
        </div>
      ) : (
        <ul className="event-list">
          {stream.map((event) => (
            <li key={event.id} className="event-item">
              <div className="event-heading">
                <div>
                  <span className="event-type">{event.event_type}</span>
                  <span className={`event-severity severity-${event.severity.toLowerCase()}`}>{event.severity}</span>
                </div>
                <span className="event-time">{formatTimestamp(event.timestamp)}</span>
              </div>

              <div className="event-meta-row">
                <span>Source</span>
                <strong>{event.source}</strong>
              </div>
              <div className="event-meta-row">
                <span>Device</span>
                <strong>{getDeviceLabel(event.device_id, devices)}</strong>
              </div>
              {hasMlDetection(event) && (
                <div className="event-ml-pill">ML context available</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
