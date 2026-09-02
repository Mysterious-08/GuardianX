import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiError } from '../../api/client'
import { getSecurityEvents } from '../../api/securityEvents'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import type { ConsoleState, GuardianXFeatureKey, SecurityEvent, SecurityEventMlDetection } from '../../types/api'

interface SecurityEventsPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

const FEATURE_LABELS: Array<{ key: GuardianXFeatureKey; label: string }> = [
  { key: 'flow_duration', label: 'Flow duration' },
  { key: 'forward_packet_count', label: 'Forward packets' },
  { key: 'backward_packet_count', label: 'Backward packets' },
  { key: 'forward_byte_count', label: 'Forward bytes' },
  { key: 'backward_byte_count', label: 'Backward bytes' },
  { key: 'packet_rate', label: 'Packet rate' },
  { key: 'byte_rate', label: 'Byte rate' },
  { key: 'is_one_way_flow', label: 'Is one-way flow' },
]

const NETWORK_FIELD_ORDER = [
  { key: 'protocol', label: 'Protocol' },
  { key: 'source_ip', label: 'Source IP' },
  { key: 'source_port', label: 'Source port' },
  { key: 'destination_ip', label: 'Destination IP' },
  { key: 'destination_port', label: 'Destination port' },
  { key: 'flow_duration', label: 'Flow duration' },
  { key: 'forward_packet_count', label: 'Forward packets' },
  { key: 'backward_packet_count', label: 'Backward packets' },
  { key: 'forward_byte_count', label: 'Forward bytes' },
  { key: 'backward_byte_count', label: 'Backward bytes' },
  { key: 'packet_rate', label: 'Packet rate' },
  { key: 'byte_rate', label: 'Byte rate' },
  { key: 'quality_status', label: 'Quality status' },
  { key: 'model_ready', label: 'Model ready' },
] as const

function formatTimestamp(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function toRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : null
}

function getMlDetection(event: SecurityEvent): SecurityEventMlDetection | null {
  const payload = toRecord(event.payload)
  const detection = payload?.ml_detection
  if (typeof detection !== 'object' || detection === null) return null

  const candidate = detection as Partial<SecurityEventMlDetection>
  if (
    typeof candidate.model !== 'string' ||
    typeof candidate.schema_version !== 'string' ||
    typeof candidate.prediction !== 'number' ||
    typeof candidate.anomaly_score !== 'number'
  ) {
    return null
  }

  return candidate as SecurityEventMlDetection
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not reported'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'Not reported'
  return String(value)
}

function describePrediction(prediction: number): { title: string; detail: string } {
  if (prediction === 1) return { title: 'Behavioral inlier', detail: 'Normal' }
  if (prediction === -1) return { title: 'Behavioral outlier', detail: 'Anomalous' }
  return { title: 'Prediction unavailable', detail: 'Unclassified' }
}

export function SecurityEventsPage({ onConsoleStateChange, onLoadingChange, onSessionExpired, refreshSignal }: SecurityEventsPageProps) {
  const [events, setEvents] = useState<SecurityEvent[] | null>(null)
  const [error, setError] = useState(false)
  const [authenticationRequired, setAuthenticationRequired] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)

  const loadEvents = useCallback(async () => {
    setIsLoading(true)
    setError(false)
    setAuthenticationRequired(false)
    onLoadingChange(true)
    onConsoleStateChange('checking')
    try {
      const nextEvents = await getSecurityEvents()
      setEvents(nextEvents)
      setSelectedEventId((current) => {
        if (nextEvents.length === 0) return null
        if (current && nextEvents.some((event) => event.id === current)) return current
        return nextEvents[0].id
      })
      onConsoleStateChange('authenticated')
    } catch (caughtError) {
      setEvents(null)
      setError(true)
      setSelectedEventId(null)
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

  const selectedEvent = useMemo(() => {
    if (!events || events.length === 0 || !selectedEventId) return null
    return events.find((event) => event.id === selectedEventId) ?? events[0]
  }, [events, selectedEventId])

  if (isLoading && !events) return <LoadingState />
  if (error || !events) return <ErrorState authenticationRequired={authenticationRequired} onRetry={() => void loadEvents()} title="Unable to load security events" />

  return (
    <div className="events-content">
      <div className="inventory-heading">
        <div>
          <p className="eyebrow">Detection surface</p>
          <h2>Security events</h2>
          <p>Investigate GuardianX endpoint activity and behavioral evidence.</p>
        </div>
        <strong className="inventory-total">{events.length}<span>Total events</span></strong>
      </div>

      {events.length === 0 ? (
        <section className="state-panel empty-state">
          <span className="state-mark state-mark-empty" aria-hidden="true">+</span>
          <div>
            <h2>No security events recorded</h2>
            <p>Events reported by GuardianX endpoints will appear here.</p>
          </div>
        </section>
      ) : (
        <div className="events-investigation-layout">
          <section className="panel event-stream-panel" aria-label="Security event stream">
            <div className="panel-heading">
              <p className="eyebrow">Event stream</p>
              <span className="panel-meta">{events.length} records</span>
            </div>
            <div className="events-list" role="listbox" aria-label="Security events">
              {events.map((event) => {
                const ml = getMlDetection(event)
                const isSelected = selectedEvent?.id === event.id
                return (
                  <button
                    key={event.id}
                    type="button"
                    className={`event-row-button ${isSelected ? 'event-row-button-selected' : ''}`}
                    aria-pressed={isSelected}
                    onClick={() => setSelectedEventId(event.id)}
                  >
                    <div className="event-row-head">
                      <span className={`event-severity severity-${event.severity.toLowerCase()}`}>{event.severity}</span>
                      <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
                    </div>
                    <div className="event-row-main">
                      <strong>{event.event_type}</strong>
                      <span>{event.source}</span>
                    </div>
                    <div className="event-row-meta">
                      <span>Device</span>
                      <strong>{event.device_id}</strong>
                    </div>
                    {ml ? <span className="event-ml-pill">ML evidence</span> : <span className="event-ml-pill event-ml-pill-muted">No ML</span>}
                  </button>
                )
              })}
            </div>
          </section>

          <aside className="panel event-detail-panel" aria-live="polite">
            {!selectedEvent ? (
              <div className="empty-inline">
                <strong>No event selected</strong>
                <span>Choose an event from the stream to inspect GuardianX telemetry and ML evidence.</span>
              </div>
            ) : (
              <>
                <div className="event-detail-header">
                  <div>
                    <p className="eyebrow">Investigation</p>
                    <div className="event-detail-title-row">
                      <h2>{selectedEvent.event_type}</h2>
                      <span className={`event-severity severity-${selectedEvent.severity.toLowerCase()}`}>{selectedEvent.severity}</span>
                    </div>
                  </div>
                  {(() => {
                    const ml = getMlDetection(selectedEvent)
                    if (!ml) return null
                    const behavior = describePrediction(ml.prediction)
                    return (
                      <span className="behavior-pill">
                        {behavior.title}
                      </span>
                    )
                  })()}
                </div>

                <div className="event-detail-meta">
                  <div><span>Device</span><strong>{selectedEvent.device_id}</strong></div>
                  <div><span>Timestamp</span><strong>{formatTimestamp(selectedEvent.timestamp)}</strong></div>
                  <div><span>Source</span><strong>{selectedEvent.source}</strong></div>
                </div>

                {(() => {
                  const payload = toRecord(selectedEvent.payload)
                  const ml = payload ? getMlDetection(selectedEvent) : null
                  if (!ml) {
                    return (
                      <section className="detail-block no-ml-section">
                        <p className="eyebrow">Machine-learning evidence</p>
                        <p className="no-ml-copy">No machine-learning detection attached to this event.</p>
                      </section>
                    )
                  }

                  const behavior = describePrediction(ml.prediction)
                  return (
                    <section className="detail-block ml-section">
                      <p className="eyebrow">Machine-learning evidence</p>
                      <div className="ml-header-row">
                        <span className="model-badge">{ml.model}</span>
                        <span className="model-badge model-badge-muted">Schema {ml.schema_version}</span>
                      </div>
                      <div className="ml-summary-grid">
                        <div>
                          <span>Decision</span>
                          <strong>{ml.prediction}</strong>
                        </div>
                        <div>
                          <span>Behavior</span>
                          <strong>{behavior.title}</strong>
                        </div>
                        <div className="ml-summary-grid-wide">
                          <span>Interpretation</span>
                          <strong>{behavior.detail}</strong>
                        </div>
                        <div className="ml-summary-grid-wide">
                          <span>Anomaly score</span>
                          <strong>{String(ml.anomaly_score)}</strong>
                        </div>
                      </div>

                      <div className="feature-section">
                        <p className="eyebrow">Model evidence</p>
                        <p className="feature-caption">Captured from the inference feature vector</p>
                        <div className="feature-grid">
                          {FEATURE_LABELS.map(({ key, label }) => {
                            const value = ml.features?.[key]
                            return (
                              <div key={key} className="feature-row">
                                <span>{label}</span>
                                <strong>{formatValue(value)}</strong>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    </section>
                  )
                })()}

                {(() => {
                  const payload = toRecord(selectedEvent.payload)
                  if (!payload) return null

                  const items = NETWORK_FIELD_ORDER.filter(({ key }) => payload[key] !== undefined)
                  if (items.length === 0) return null

                  return (
                    <section className="detail-block evidence-section">
                      <p className="eyebrow">Network evidence</p>
                      <div className="evidence-grid">
                        {items.map(({ key, label }) => (
                          <div key={key} className="evidence-item">
                            <span>{label}</span>
                            <strong>{formatValue(payload[key])}</strong>
                          </div>
                        ))}
                      </div>
                    </section>
                  )
                })()}

                <details className="detail-block raw-payload-block">
                  <summary>Raw event payload</summary>
                  <pre>{JSON.stringify(selectedEvent.payload, null, 2)}</pre>
                </details>
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}