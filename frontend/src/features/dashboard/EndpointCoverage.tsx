import type { DashboardOverview } from '../../types/api'

interface EndpointCoverageProps {
  overview: DashboardOverview
}

export function EndpointCoverage({ overview }: EndpointCoverageProps) {
  const total = overview.total_devices
  const coveragePercent = total > 0 ? (overview.devices_with_inventory / total) * 100 : 0

  return (
    <section className="panel-surface coverage-panel">
      <div className="panel-topline compact">
        <div>
          <p className="eyebrow">Endpoint coverage</p>
          <h2>Managed endpoints</h2>
        </div>
        <span className="coverage-total">{total}</span>
      </div>

      <div className="coverage-value-block">
        <div>
          <strong>{total}</strong>
          <span>Total endpoints</span>
        </div>
        <div>
          <strong>{overview.online_devices}</strong>
          <span>Online</span>
        </div>
        <div>
          <strong>{overview.offline_devices}</strong>
          <span>Offline</span>
        </div>
      </div>

      <div className="coverage-breakdown">
        <div className="coverage-row emphasis">
          <span>Registered</span>
          <strong>{overview.registered_devices}</strong>
        </div>
        <div className="coverage-row">
          <span>Isolated</span>
          <strong>{overview.isolated_devices}</strong>
        </div>
        <div className="coverage-row">
          <span>Quarantined</span>
          <strong>{overview.quarantined_devices}</strong>
        </div>
      </div>

      <div className="coverage-meter" aria-label={`Inventory coverage ${coveragePercent.toFixed(0)} percent`}>
        <span style={{ width: `${coveragePercent}%` }} />
      </div>
      <div className="coverage-meter-label">
        <span>Inventory coverage</span>
        <strong>{coveragePercent.toFixed(0)}%</strong>
      </div>
    </section>
  )
}
