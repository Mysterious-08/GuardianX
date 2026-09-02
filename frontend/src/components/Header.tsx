interface HeaderProps {
  consoleState: 'checking' | 'authenticated' | 'authentication-required' | 'unavailable'
  description: string
  isRefreshing: boolean
  onRefresh: () => void
  onLogout: () => void
  username: string
  title: string
}

export function Header({ consoleState, description, isRefreshing, onLogout, onRefresh, title, username }: HeaderProps) {
  const profileLabel = consoleState === 'authenticated' ? 'Session active' : consoleState === 'authentication-required' ? 'Sign-in required' : consoleState === 'unavailable' ? 'Backend unavailable' : 'Checking session'

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Intelligence core</p>
        <h1>{title}</h1>
        <p className="header-subtitle">{description}</p>
      </div>
      <div className="header-actions">
        <button
          className="button button-refresh"
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          aria-label="Refresh dashboard"
        >
          <span aria-hidden="true">↻</span>
          {isRefreshing ? 'Refreshing' : 'Refresh'}
        </button>
        <div className="profile" aria-label={profileLabel}>
          <span className="profile-avatar" aria-hidden="true">{consoleState === 'authenticated' ? 'OP' : '--'}</span>
          <div>
            <strong>{username}</strong>
            <span>{profileLabel}</span>
          </div>
          <button className="logout-button" type="button" onClick={onLogout}>Log out</button>
        </div>
      </div>
    </header>
  )
}
