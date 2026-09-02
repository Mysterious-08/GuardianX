interface DeviceActivityProps {
  latestActivity: string | null
}

function formatActivity(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Activity timestamp unavailable'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function DeviceActivity({ latestActivity }: DeviceActivityProps) {
  return (
    <section className="panel activity-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Endpoint telemetry</p>
          <h2>Latest device activity</h2>
        </div>
        <span className="activity-pulse" aria-hidden="true" />
      </div>
      {latestActivity ? (
        <div className="activity-value">
          <strong>{formatActivity(latestActivity)}</strong>
          <span>Latest heartbeat recorded</span>
        </div>
      ) : (
        <div className="activity-empty">
          <strong>No endpoint activity yet</strong>
          <span>Activity will appear when an endpoint reports in.</span>
        </div>
      )}
    </section>
  )
}
