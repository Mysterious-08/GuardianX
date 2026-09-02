import type { ReactNode } from 'react'
import type { ConsoleState } from '../types/api'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

interface AppShellProps {
  children: ReactNode
  consoleState: ConsoleState
  description: string
  isRefreshing: boolean
  onLogout: () => void
  onRefresh: () => void
  username: string
  title: string
  onNavigate: (path: string) => void
}

export function AppShell({ children, consoleState, description, isRefreshing, onLogout, onNavigate, onRefresh, title, username }: AppShellProps) {
  return (
    <div className="app-shell">
      <Sidebar activeItem={title === 'Security Events' ? 'Security Events' : title.startsWith('Endpoint') ? 'Endpoints' : 'Overview'} consoleState={consoleState} onNavigate={onNavigate} />
      <div className="main-column">
        <Header consoleState={consoleState} description={description} isRefreshing={isRefreshing} onLogout={onLogout} onRefresh={onRefresh} title={title} username={username} />
        <main className="main-content">{children}</main>
      </div>
    </div>
  )
}
