import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getDashboardOverview } from '../../api/dashboard'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import type { ConsoleState, DashboardOverview } from '../../types/api'
import { DeviceActivity } from './DeviceActivity'
import { DeviceStatusSummary } from './DeviceStatusSummary'
import { InventoryCoverage } from './InventoryCoverage'
import { OverviewMetric } from './OverviewMetric'
import { SecurityEventSummary } from './SecurityEventSummary'

interface DashboardPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

export function DashboardPage({ onConsoleStateChange, onLoadingChange, onSessionExpired, refreshSignal }: DashboardPageProps) {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState(false)
  const [authenticationRequired, setAuthenticationRequired] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    setError(false)
    setAuthenticationRequired(false)
    onLoadingChange(true)
    onConsoleStateChange('checking')
    try {
      setOverview(await getDashboardOverview())
      onConsoleStateChange('authenticated')
    } catch (caughtError) {
      setOverview(null)
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
    queueMicrotask(() => void loadDashboard())
  }, [loadDashboard, refreshSignal])

  if (isLoading && !overview) return <LoadingState />
  if (error || !overview) {
    return <ErrorState authenticationRequired={authenticationRequired} onRetry={() => void loadDashboard()} />
  }

  if (overview.total_devices === 0) {
    return (
      <section className="state-panel empty-state">
        <span className="state-mark state-mark-empty" aria-hidden="true">+</span>
        <div>
          <p className="eyebrow">Endpoint inventory</p>
          <h2>No endpoints are connected yet</h2>
          <p>Register a GuardianX endpoint to begin monitoring device activity and security status.</p>
        </div>
      </section>
    )
  }

  return (
    <div className="dashboard-content">
      <section className="metric-grid" aria-label="Device metrics">
        <OverviewMetric label="Total devices" value={overview.total_devices} />
        <OverviewMetric label="Online" value={overview.online_devices} tone="success" />
        <OverviewMetric label="Offline" value={overview.offline_devices} tone="warning" />
        <OverviewMetric label="Uninitialized" value={overview.registered_devices} />
        <OverviewMetric label="Isolated" value={overview.isolated_devices} tone="warning" />
        <OverviewMetric label="Quarantined" value={overview.quarantined_devices} tone="critical" />
      </section>
      <section className="content-grid">
        <DeviceStatusSummary overview={overview} />
        <InventoryCoverage overview={overview} />
        <SecurityEventSummary total={overview.total_security_events} />
        <DeviceActivity latestActivity={overview.latest_device_activity} />
      </section>
    </div>
  )
}