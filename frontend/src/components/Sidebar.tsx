import type { ConsoleState } from '../types/api'

interface SidebarProps {
  activeItem: string
  consoleState: ConsoleState
  onNavigate: (path: string) => void
}

const navigationItems = [
  { label: 'Overview', path: '/dashboard' },
  { label: 'Endpoints', path: '/devices' },
  { label: 'Security Events', path: '/security-events' },
  { label: 'Backup & Recovery', path: '/backups' },
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
        <div className="brand-identity">
          <img className="brand-wordmark" src="/brand/guardianx-wordmark.svg" alt="GuardianX" />
          <span>AI-powered endpoint security</span>
        </div>
      </div>

      <nav className="nav-list" aria-label="GuardianX sections">
        <p className="nav-heading">Command center</p>
        {navigationItems.map((item) => {
          const isActive = item.label === activeItem
          return (
            <button
              className={`nav-item${isActive ? ' nav-item-active' : ''}`}
              key={item.label}
              type="button"
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onNavigate(item.path)}
            >
              <span className="nav-indicator" aria-hidden="true" />
              {item.label}
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
