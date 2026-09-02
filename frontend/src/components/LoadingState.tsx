export function LoadingState() {
  return (
    <div className="dashboard-loading" aria-busy="true" aria-label="Loading dashboard">
      <div className="skeleton skeleton-heading" />
      <div className="metric-grid">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="metric-card skeleton-card" key={index}>
            <div className="skeleton skeleton-label" />
            <div className="skeleton skeleton-value" />
            <div className="skeleton skeleton-line" />
          </div>
        ))}
      </div>
      <div className="content-grid">
        <div className="panel skeleton-panel" />
        <div className="panel skeleton-panel" />
      </div>
    </div>
  )
}
