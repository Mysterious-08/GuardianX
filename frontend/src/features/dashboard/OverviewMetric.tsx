interface OverviewMetricProps {
  label: string
  value: number
  tone?: 'default' | 'success' | 'warning' | 'critical'
}

export function OverviewMetric({ label, value, tone = 'default' }: OverviewMetricProps) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <div className="metric-label">
        <span className="metric-marker" aria-hidden="true" />
        {label}
      </div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-caption">Current inventory</span>
    </article>
  )
}
