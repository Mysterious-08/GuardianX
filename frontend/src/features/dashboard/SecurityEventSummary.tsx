export interface SecurityEventSummaryProps {
  total: number
}

export function SecurityEventSummary({ total }: SecurityEventSummaryProps) {
  return (
    <section className="panel event-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Detection surface</p>
          <h2>Security events</h2>
        </div>
        <span className="event-symbol" aria-hidden="true">!</span>
      </div>
      <strong className="event-total">{total}</strong>
      <p className="panel-description">Events recorded across your endpoints.</p>
      <button className="text-action" type="button" disabled title="Security Events is not available yet">
        Open Security Events <span aria-hidden="true">-&gt;</span>
      </button>
    </section>
  )
}
