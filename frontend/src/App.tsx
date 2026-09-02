import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/auth-context'
import { AppShell } from './components/AppShell'
import { LoadingState } from './components/LoadingState'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { EndpointInventoryPage } from './features/devices/EndpointInventoryPage'
import { EndpointPosturePage } from './features/devices/EndpointPosturePage'
import { SecurityEventsPage } from './features/security-events/SecurityEventsPage'
import type { ConsoleState, DeviceSummary } from './types/api'

function navigate(path: string): void {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function AuthenticatedApp() {
  const { logout, user } = useAuth()
  const [refreshSignal, setRefreshSignal] = useState(0)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [consoleState, setConsoleState] = useState<ConsoleState>('checking')
  const [path, setPath] = useState(window.location.pathname)
  const [selectedDevice, setSelectedDevice] = useState<DeviceSummary | null>(null)
  const postureMatch = path.match(/^\/devices\/([^/]+)\/posture$/)
  const isPosture = postureMatch !== null
  const isSecurityEvents = path === '/security-events'
  const goToLogin = useCallback(() => {
    logout()
    navigate('/login')
  }, [logout])

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  if (!user) return null

  return (
    <AppShell
      consoleState={consoleState}
      description={isSecurityEvents ? 'Security activity across GuardianX-managed endpoints' : isPosture ? 'Device health, inventory, and security activity' : path === '/devices' ? 'GuardianX-managed endpoint inventory' : 'Endpoint visibility and security status'}
      isRefreshing={isRefreshing}
      onLogout={goToLogin}
      onNavigate={navigate}
      onRefresh={() => setRefreshSignal((signal) => signal + 1)}
      title={isSecurityEvents ? 'Security Events' : isPosture ? 'Endpoint Posture' : path === '/devices' ? 'Endpoint Inventory' : 'Overview'}
      username={user.username}
    >
      {isSecurityEvents ? (
        <SecurityEventsPage
          onLoadingChange={setIsRefreshing}
          onConsoleStateChange={setConsoleState}
          onSessionExpired={goToLogin}
          refreshSignal={refreshSignal}
        />
      ) : isPosture ? (
        <EndpointPosturePage
          agentId={postureMatch[1]}
          device={selectedDevice}
          onBack={() => navigate('/devices')}
          onLoadingChange={setIsRefreshing}
          onConsoleStateChange={setConsoleState}
          onSessionExpired={goToLogin}
          refreshSignal={refreshSignal}
        />
      ) : path === '/devices' ? (
        <EndpointInventoryPage
          refreshSignal={refreshSignal}
          onLoadingChange={setIsRefreshing}
          onConsoleStateChange={setConsoleState}
          onSessionExpired={goToLogin}
          onSelectDevice={(device) => {
            setSelectedDevice(device)
            navigate(`/devices/${device.agent_id}/posture`)
          }}
        />
      ) : (
        <DashboardPage
          refreshSignal={refreshSignal}
          onLoadingChange={setIsRefreshing}
          onConsoleStateChange={setConsoleState}
          onSessionExpired={goToLogin}
        />
      )}
    </AppShell>
  )
}

function RoutedApp() {
  const { status } = useAuth()
  const [path, setPath] = useState(window.location.pathname)

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (status === 'loading') return
    if (status === 'authenticated' && path !== '/dashboard' && path !== '/devices' && path !== '/security-events' && !/^\/devices\/[^/]+\/posture$/.test(path)) navigate('/dashboard')
    if (status === 'unauthenticated' && path !== '/login' && path !== '/register') navigate('/login')
  }, [path, status])

  if (status === 'loading') return <LoadingState />
  if (status === 'unauthenticated' && path === '/register') return <RegisterPage onNavigate={navigate} />
  if (status === 'unauthenticated') return <LoginPage onNavigate={navigate} registrationComplete={window.location.search.includes('registered=1')} />
  return <AuthenticatedApp />
}

function App() {
  return (
    <AuthProvider>
      <RoutedApp />
    </AuthProvider>
  )
}

export default App