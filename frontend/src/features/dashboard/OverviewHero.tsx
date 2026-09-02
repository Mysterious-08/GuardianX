interface OverviewHeroProps {
  totalDevices: number
  onlineDevices: number
  offlineDevices: number
  totalEvents: number
  latestActivity: string | null
}

function formatActivity(value: string | null): string {
  if (!value) return 'No endpoint activity yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Activity timestamp unavailable'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function OverviewHero({ totalDevices, onlineDevices, offlineDevices, totalEvents, latestActivity }: OverviewHeroProps) {
  const statusMessage = totalDevices === 0
    ? 'No endpoints are connected yet.'
    : totalEvents > 0
      ? 'Security events require investigation.'
      : offlineDevices > 0
        ? `Attention required: ${offlineDevices} endpoint${offlineDevices === 1 ? '' : 's'} offline.`
        : `All monitored endpoints are online.`

  return (
    <section className="overview-hero panel-surface">
      <div className="hero-copy">
        <p className="eyebrow">GuardianX</p>
        <h1>Endpoint Security Command Center</h1>
        <p className="hero-status">{statusMessage}</p>
      </div>

      <div className="hero-meta">
        <div className="hero-kpi">
          <span className="hero-kpi-label">Monitored</span>
          <strong>{totalDevices}</strong>
          <span className="hero-kpi-sub">endpoints</span>
        </div>
        <div className="hero-kpi">
          <span className="hero-kpi-label">Online</span>
          <strong>{onlineDevices}</strong>
          <span className="hero-kpi-sub">active</span>
        </div>
        <div className="hero-kpi">
          <span className="hero-kpi-label">Last updated</span>
          <strong>{formatActivity(latestActivity)}</strong>
          <span className="hero-kpi-sub">latest backend state</span>
        </div>
      </div>
    </section>
  )
}
