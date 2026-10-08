import { useCallback, useEffect, useState } from 'react'
import { ApiError, getAccessToken } from '../../api/client'
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

interface LauncherStatus {
  running: boolean
}

function MonitoringControl() {
  const [isRunning, setIsRunning] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [launcherUnavailable, setLauncherUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    const pollStatus = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8765/status')
        if (!response.ok) throw new Error('Launcher status request failed')
        const status = (await response.json()) as LauncherStatus
        if (active) {
          setIsRunning(status.running)
          setLauncherUnavailable(false)
        }
      } catch {
        if (active) {
          setIsRunning(false)
          setLauncherUnavailable(true)
        }
      }
    }

    void pollStatus()
    const interval = window.setInterval(() => void pollStatus(), 3000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  const startMonitoring = async () => {
    setIsBusy(true)
    try {
      const response = await fetch('http://127.0.0.1:8765/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ access_token: getAccessToken() }),
      })
      if (!response.ok) throw new Error('Launcher start request failed')
      const status = (await response.json()) as LauncherStatus
      setIsRunning(status.running)
      setLauncherUnavailable(false)
    } catch {
      setLauncherUnavailable(true)
    } finally {
      setIsBusy(false)
    }
  }

  const stopMonitoring = async () => {
    setIsBusy(true)
    try {
      const response = await fetch('http://127.0.0.1:8765/stop', { method: 'POST' })
      if (!response.ok) throw new Error('Launcher stop request failed')
      const status = (await response.json()) as LauncherStatus
      setIsRunning(status.running)
      setLauncherUnavailable(false)
    } catch {
      setLauncherUnavailable(true)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <section
      className="panel-surface"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '14px 18px' }}
    >
      <div>
        {isRunning && <strong>Monitoring Active</strong>}
        {launcherUnavailable && <p role="status">GuardianX local launcher is not running.</p>}
      </div>
      {isRunning ? (
        <button className="button" type="button" disabled={isBusy} onClick={() => void stopMonitoring()}>
          Stop Monitoring
        </button>
      ) : (
        <button className="button" type="button" disabled={isBusy} onClick={() => void startMonitoring()}>
          Start Monitoring
        </button>
      )}
    </section>
  )
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
      <div className="dashboard-content">
        <MonitoringControl />
        <section className="state-panel empty-state">
          <span className="state-mark state-mark-empty" aria-hidden="true">+</span>
          <div>
            <p className="eyebrow">Endpoint inventory</p>
            <h2>No endpoints are connected yet</h2>
            <p>Register a GuardianX endpoint to begin monitoring device activity and security status.</p>
          </div>
        </section>
      </div>
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
      <MonitoringControl />

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