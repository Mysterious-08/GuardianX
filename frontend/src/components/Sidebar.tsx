import type { ConsoleState } from '../types/api'

interface SidebarProps {
  activeItem: string
  consoleState: ConsoleState
  onNavigate: (path: string) => void
}

const navigationItems = [
  'Overview',
  'Endpoints',
  'Security Events',
  'Threat Intelligence',
  'Response',
  'Recovery Vault',
  'Reports',
  'Settings',
]

export function Sidebar({ activeItem, consoleState, onNavigate }: SidebarProps) {
  const connectionLabel = {
    checking: 'Checking backend',
    authenticated: 'Session active',
    'authentication-required': 'Authentication required',
    unavailable: 'Backend unavailable',
  }[consoleState]

  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">GX</span>
        <div>
          <strong>GuardianX</strong>
          <span>Endpoint defense</span>
        </div>
      </div>

      <nav className="nav-list">
        <p className="nav-heading">Workspace</p>
        {navigationItems.map((item) => {
          const isActive = item === activeItem
          const isSupported = item === 'Overview' || item === 'Endpoints' || item === 'Security Events'
          return (
            <button
              className={`nav-item${isActive ? ' nav-item-active' : ''}`}
              disabled={!isSupported}
              key={item}
              type="button"
              aria-current={isActive ? 'page' : undefined}
              title={isSupported ? undefined : `${item} is not available in this milestone`}
              onClick={() => onNavigate(item === 'Overview' ? '/dashboard' : item === 'Endpoints' ? '/devices' : '/security-events')}
            >
              <span className="nav-indicator" aria-hidden="true" />
              {item}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <span className={`connection-dot connection-${consoleState}`} aria-hidden="true" />
        <span>{connectionLabel}</span>
      </div>
    </aside>
  )
}
