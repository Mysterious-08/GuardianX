import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ApiError } from '../../api/client'
import { getDeviceInventory } from '../../api/inventory'
import { getDeviceSecurityEvents } from '../../api/securityEvents'
import { ErrorState } from '../../components/ErrorState'
import { LoadingState } from '../../components/LoadingState'
import { StatusBadge } from '../../components/StatusBadge'
import type { ConsoleState, DeviceInventory, DeviceSummary, SecurityEvent } from '../../types/api'

interface EndpointPosturePageProps {
  agentId: string
  device: DeviceSummary | null
  onBack: () => void
  onConsoleStateChange: (state: ConsoleState) => void
  onLoadingChange: (isLoading: boolean) => void
  onSessionExpired: () => void
  refreshSignal: number
}

function formatValue(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === '' ? 'Not reported' : String(value)
}

function formatLastSeen(value: string | null): string {
  if (!value) return 'Never checked in'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function formatMemory(value: number | null): string {
  return value === null ? 'Not reported' : `${(value / 1024).toFixed(value >= 1024 ? 1 : 0)} GB`
}

function formatDisk(value: number | null): string {
  return value === null ? 'Not reported' : `${(value / 1024).toFixed(value >= 1024 ? 1 : 0)} GB`
}

function formatTimestamp(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Timestamp unavailable' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
  return <div className="posture-detail"><span>{label}</span><strong>{formatValue(value)}</strong></div>
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="panel posture-section"><p className="eyebrow">{title}</p><div className="posture-details">{children}</div></section>
}

export function EndpointPosturePage({ agentId, device, onBack, onConsoleStateChange, onLoadingChange, onSessionExpired, refreshSignal }: EndpointPosturePageProps) {
  const [inventory, setInventory] = useState<DeviceInventory | null>(null)
  const [inventoryLoading, setInventoryLoading] = useState(true)
  const [inventoryUnavailable, setInventoryUnavailable] = useState(false)
  const [inventoryError, setInventoryError] = useState(false)
  const [events, setEvents] = useState<SecurityEvent[]>([])
  const [eventsLoading, setEventsLoading] = useState(true)
  const [eventsError, setEventsError] = useState(false)

  const handleApiError = useCallback((error: unknown): boolean => {
    if (error instanceof ApiError && error.status === 401) {
      onConsoleStateChange('authentication-required')
      onSessionExpired()
      return true
    }
    return false
  }, [onConsoleStateChange, onSessionExpired])

  const loadPosture = useCallback(() => {
    setInventoryLoading(true)
    setInventoryUnavailable(false)
    setInventoryError(false)
    setEventsLoading(true)
    setEventsError(false)
    onLoadingChange(true)

    void getDeviceInventory(agentId).then((result) => {
      setInventory(result)
    }).catch((error: unknown) => {
      if (handleApiError(error)) return
      if (error instanceof ApiError && error.status === 404) setInventoryUnavailable(true)
      else setInventoryError(true)
    }).finally(() => setInventoryLoading(false))

    void getDeviceSecurityEvents(agentId).then((result) => {
      setEvents(result)
    }).catch((error: unknown) => {
      if (!handleApiError(error)) setEventsError(true)
    }).finally(() => setEventsLoading(false))
  }, [agentId, handleApiError, onLoadingChange])

  useEffect(() => {
    queueMicrotask(loadPosture)
  }, [loadPosture, refreshSignal])

  useEffect(() => {
    if (!inventoryLoading && !eventsLoading) onLoadingChange(false)
  }, [eventsLoading, inventoryLoading, onLoadingChange])

  if (!device) return <ErrorState authenticationRequired={false} onRetry={onBack} title="Endpoint unavailable" description="This endpoint is no longer available in your GuardianX inventory." />

  const statusLabel = device.status === 'REGISTERED' && device.last_seen === null ? 'Uninitialized' : undefined

  return (
    <div className="posture-content">
      <button className="button posture-back" type="button" onClick={onBack}>← Endpoint Inventory</button>
      <div className="posture-heading">
        <div><p className="eyebrow">Endpoint posture</p><h2>{device.device_name ?? device.hostname}</h2><p>{device.hostname} <span className="posture-id">{device.id}</span></p></div>
        <StatusBadge status={device.status} label={statusLabel} />
      </div>
      <section className="panel posture-section posture-device-section">
        <p className="eyebrow">Device</p>
        <div className="posture-details"><Detail label="Device name" value={device.device_name ?? device.hostname} /><Detail label="Hostname" value={device.hostname} /><Detail label="Operating system" value={inventory?.operating_system} /><Detail label="OS version" value={inventory?.os_version} /><Detail label="Architecture" value={inventory?.architecture} /><Detail label="Agent version" value={inventory?.agent_version} /><Detail label="Status" value={statusLabel ?? device.status} /><Detail label="Last seen" value={formatLastSeen(device.last_seen)} /></div>
      </section>
      {inventoryLoading && <LoadingState />}
      {!inventoryLoading && inventoryUnavailable && <section className="state-panel posture-empty"><div><p className="eyebrow">Hardware inventory</p><h2>Inventory unavailable</h2><p>This endpoint has not reported an inventory snapshot yet.</p></div></section>}
      {!inventoryLoading && inventoryError && <ErrorState authenticationRequired={false} onRetry={loadPosture} title="Unable to load inventory" description="Check the connection to GuardianX and try again." />}
      {!inventoryLoading && inventory && <>
        <Section title="Hardware"><Detail label="CPU model" value={inventory.cpu_model} /><Detail label="CPU cores" value={inventory.cpu_cores} /><Detail label="Total memory" value={formatMemory(inventory.total_memory_mb)} /><Detail label="Total disk" value={formatDisk(inventory.total_disk_mb)} /></Section>
        <Section title="Network"><Detail label="Local IP" value={inventory.local_ip} /><Detail label="MAC address" value={inventory.mac_address} /><div className="posture-detail posture-wide"><span>Network interfaces</span><strong>{inventory.network_interfaces?.length ? inventory.network_interfaces.map((item, index) => <code key={index}>{JSON.stringify(item)}</code>) : 'Not reported'}</strong></div></Section>
      </>}
      <section className="panel posture-section events-section"><div className="panel-heading"><p className="eyebrow">Security activity</p><span className="panel-meta">{events.length} events</span></div>
        {eventsLoading && <div className="posture-inline-loading" aria-busy="true">Loading security activity...</div>}
        {!eventsLoading && eventsError && <ErrorState authenticationRequired={false} onRetry={loadPosture} title="Unable to load security activity" description="Check the connection to GuardianX and try again." />}
        {!eventsLoading && !eventsError && events.length === 0 && <div className="posture-inline-empty">No security events have been recorded for this endpoint.</div>}
        {!eventsLoading && !eventsError && events.length > 0 && <div className="events-list">{events.map((event) => <article className="event-row" key={event.id}><strong>{event.event_type}</strong><span className={`event-severity severity-${event.severity.toLowerCase()}`}>{event.severity}</span><span>{event.source}</span><time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time></article>)}</div>}
      </section>
    </div>
  )
}