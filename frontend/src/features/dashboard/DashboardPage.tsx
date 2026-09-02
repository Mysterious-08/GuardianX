import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../api/client'
import { getDashboardOverview } from '../../api/dashboard'
import { getDevices } from '../../api/devices'
import { getSecurityEvents } from '../../api/securityEvents'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import type { ConsoleState, DashboardOverview, DeviceSummary, SecurityEvent } from '../../types/api'
import { BehavioralDetectionPanel } from './BehavioralDetectionPanel'
import { DeviceActivity } from './DeviceActivity'
import { EndpointCoverage } from './EndpointCoverage'
import { OverviewHero } from './OverviewHero'
import { SecurityEventStream } from './SecurityEventStream'
import { SecurityPosture } from './SecurityPosture'

interface DashboardPageProps {
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

export function DashboardPage({ onConsoleStateChange, onLoadingChange, onSessionExpired, refreshSignal }: DashboardPageProps) {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [devices, setDevices] = useState<DeviceSummary[] | null>(null)
  const [events, setEvents] = useState<SecurityEvent[] | null>(null)
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
      const [overviewData, devicesData, eventsData] = await Promise.all([
        getDashboardOverview(),
        getDevices(),
        getSecurityEvents(),
      ])
      setOverview(overviewData)
      setDevices(devicesData.devices)
      setEvents(eventsData)
      onConsoleStateChange('authenticated')
    } catch (caughtError) {
      setOverview(null)
      setDevices(null)
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

  const openSecurityEvents = useCallback(() => {
    window.history.pushState({}, '', '/security-events')
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, [])

  useEffect(() => {
    queueMicrotask(() => void loadDashboard())
  }, [loadDashboard, refreshSignal])

  if (isLoading && !overview) return <LoadingState />
  if (error || !overview || !devices || !events) {
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

  const criticalEvents = events.filter((event) => event.severity === 'CRITICAL').length

  return (
    <div className="dashboard-content">
      <OverviewHero
        totalDevices={overview.total_devices}
        onlineDevices={overview.online_devices}
        offlineDevices={overview.offline_devices}
        totalEvents={overview.total_security_events}
        latestActivity={overview.latest_device_activity}
      />

      <div className="overview-grid">
        <SecurityPosture
          totalDevices={overview.total_devices}
          onlineDevices={overview.online_devices}
          offlineDevices={overview.offline_devices}
          totalEvents={overview.total_security_events}
          criticalEvents={criticalEvents}
        />

        <EndpointCoverage overview={overview} />
        <SecurityEventStream events={events} devices={devices} onOpenSecurityEvents={openSecurityEvents} />
        <BehavioralDetectionPanel events={events} />
        <DeviceActivity latestActivity={overview.latest_device_activity} />
      </div>
    </div>
  )
}