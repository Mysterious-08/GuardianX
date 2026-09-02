import type { SecurityEvent } from '../../types/api'

interface BehavioralDetectionPanelProps {
  events: SecurityEvent[]
}

interface MlDetection {
  model: string
  schema_version: string
  prediction: number
  anomaly_score: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getMlDetection(event: SecurityEvent): MlDetection | null {
  const payload = event.payload
  if (!isRecord(payload)) return null
  const ml = payload.ml_detection
  if (!isRecord(ml)) return null

  const model = typeof ml.model === 'string' ? ml.model : null
  const schemaVersion = typeof ml.schema_version === 'string' ? ml.schema_version : null
  const prediction = typeof ml.prediction === 'number' ? ml.prediction : null
  const anomalyScore = typeof ml.anomaly_score === 'number' ? ml.anomaly_score : null

  if (!model || !schemaVersion || prediction === null || anomalyScore === null) {
    return null
  }

  return {
    model,
    schema_version: schemaVersion,
    prediction,
    anomaly_score: anomalyScore,
  }
}

export function BehavioralDetectionPanel({ events }: BehavioralDetectionPanelProps) {
  const detectionEvents = events
    .map((event) => ({ event, detection: getMlDetection(event) }))
    .filter((item): item is { event: SecurityEvent; detection: MlDetection } => item.detection !== null)
    .slice(0, 3)

  return (
    <section className="panel-surface ml-panel">
      <div className="panel-topline">
        <div>
          <p className="eyebrow">Behavioral analysis</p>
          <h2>AI anomaly detection</h2>
        </div>
        <span className="model-badge">ML</span>
      </div>

      <p className="ml-summary">
        GuardianX evaluates endpoint network behavior against a learned baseline and flags behavioral outliers for investigation.
      </p>

      {detectionEvents.length === 0 ? (
        <div className="empty-inline compact">
          <strong>ML detections will appear here when network telemetry produces a completed flow.</strong>
        </div>
      ) : (
        <ul className="ml-detection-list">
          {detectionEvents.map(({ event, detection }) => (
            <li key={event.id} className="ml-detection-row">
              <div className="ml-headline">
                <span className="event-type">{detection.prediction === -1 ? 'Anomalous' : 'Normal'}</span>
                <span className="event-severity severity-neutral">{detection.prediction === -1 ? 'Prediction -1' : 'Prediction 1'}</span>
              </div>
              <div className="ml-meta-grid">
                <div>
                  <span>Model</span>
                  <strong>{detection.model}</strong>
                </div>
                <div>
                  <span>Schema</span>
                  <strong>{detection.schema_version}</strong>
                </div>
                <div>
                  <span>Behavior</span>
                  <strong>{detection.prediction === -1 ? 'Behavioral outlier' : 'Behavioral inlier'}</strong>
                </div>
                <div>
                  <span>Anomaly score</span>
                  <strong>{Number(detection.anomaly_score).toFixed(6)}</strong>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
