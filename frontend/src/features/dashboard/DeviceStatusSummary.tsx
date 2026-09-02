import { StatusBadge } from '../../components/StatusBadge'
import type { DashboardOverview, DeviceStatus } from '../../types/api'

interface DeviceStatusSummaryProps {
  overview: DashboardOverview
}

const statuses: Array<{ key: keyof Pick<DashboardOverview, 'online_devices' | 'offline_devices' | 'registered_devices' | 'isolated_devices' | 'quarantined_devices'>; status: DeviceStatus }> = [
  { key: 'online_devices', status: 'ONLINE' },
  { key: 'offline_devices', status: 'OFFLINE' },
  { key: 'registered_devices', status: 'REGISTERED' },
  { key: 'isolated_devices', status: 'ISOLATED' },
  { key: 'quarantined_devices', status: 'QUARANTINED' },
]

export function DeviceStatusSummary({ overview }: DeviceStatusSummaryProps) {
  return (
    <section className="panel status-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Endpoint posture</p>
          <h2>Device status distribution</h2>
        </div>
        <span className="panel-meta">{overview.total_devices} total</span>
      </div>
      <div className="status-bars" aria-label="Device status distribution">
        {statuses.map(({ key, status }) => {
          const value = overview[key]
          const width = overview.total_devices > 0 ? `${(value / overview.total_devices) * 100}%` : '0%'
          return (
            <div className="status-row" key={status}>
              <div className="status-row-label"><StatusBadge status={status} label={status === 'REGISTERED' ? 'Uninitialized' : undefined} /></div>
              <div className="status-track"><span className={`status-fill fill-${status.toLowerCase()}`} style={{ width }} /></div>
              <strong>{value}</strong>
            </div>
          )
        })}
      </div>
    </section>
  )
}
