interface SecurityPostureProps {
  totalDevices: number
  onlineDevices: number
  offlineDevices: number
  totalEvents: number
  criticalEvents: number
}

export function SecurityPosture({ totalDevices, onlineDevices, offlineDevices, totalEvents, criticalEvents }: SecurityPostureProps) {
  let state: 'PROTECTED' | 'MONITORING' | 'ATTENTION REQUIRED' | 'CRITICAL' = 'MONITORING'
  let tone: 'ok' | 'warn' | 'critical' = 'ok'

  if (criticalEvents > 0) {
    state = 'CRITICAL'
    tone = 'critical'
  } else if (totalEvents > 0 || offlineDevices > 0) {
    state = 'ATTENTION REQUIRED'
    tone = 'warn'
  } else if (totalDevices > 0 && onlineDevices === totalDevices) {
    state = 'PROTECTED'
    tone = 'ok'
  }

  const reasoning = `${totalDevices} endpoints monitored • ${onlineDevices} online • ${offlineDevices} offline • ${totalEvents} security events`

  return (
    <section className="panel-surface posture-panel">
      <div className="panel-topline">
        <div>
          <p className="eyebrow">Posture</p>
          <h2>Real-time security state</h2>
        </div>
        <span className={`system-state system-state--${tone}`}>{state}</span>
      </div>

      <p className="posture-reasoning">{reasoning}</p>
      <p className="posture-description">
        {state === 'CRITICAL' && 'Critical event severity is present in the backend stream and requires operator review.'}
        {state === 'ATTENTION REQUIRED' && 'The current backend state indicates telemetry gaps or recorded security events that merit review.'}
        {state === 'PROTECTED' && 'Monitored endpoints are healthy and the backend is not reporting security events.'}
        {state === 'MONITORING' && 'GuardianX is monitoring active endpoints and awaiting new telemetry.'}
      </p>
    </section>
  )
}
