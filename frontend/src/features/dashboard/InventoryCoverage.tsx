import type { DashboardOverview } from '../../types/api'

interface InventoryCoverageProps {
  overview: DashboardOverview
}

export function InventoryCoverage({ overview }: InventoryCoverageProps) {
  const total = overview.devices_with_inventory + overview.devices_without_inventory
  const coverageWidth = total > 0 ? `${(overview.devices_with_inventory / total) * 100}%` : '0%'

  return (
    <section className="panel inventory-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Asset visibility</p>
          <h2>Inventory coverage</h2>
        </div>
        <span className="panel-meta">{overview.devices_with_inventory} tracked</span>
      </div>
      <div className="coverage-track" aria-label="Inventory coverage">
        <span className="coverage-fill" style={{ width: coverageWidth }} />
      </div>
      <div className="coverage-values">
        <div><strong>{overview.devices_with_inventory}</strong><span>With inventory</span></div>
        <div><strong>{overview.devices_without_inventory}</strong><span>Without inventory</span></div>
      </div>
    </section>
  )
}
