import type { DeviceStatus } from '../types/api'

interface StatusBadgeProps {
  status: DeviceStatus
  label?: string
}

const statusLabels: Record<DeviceStatus, string> = {
  ONLINE: 'Online',
  OFFLINE: 'Offline',
  REGISTERED: 'Registered',
  ISOLATED: 'Isolated',
  QUARANTINED: 'Quarantined',
  UNINSTALLED: 'Uninstalled',
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      <span className="status-dot" aria-hidden="true" />
      {label ?? statusLabels[status]}
    </span>
  )
}
