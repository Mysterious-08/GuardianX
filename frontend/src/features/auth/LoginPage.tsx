import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/auth-context'

interface LoginPageProps {
  onNavigate: (path: string) => void
  registrationComplete?: boolean
}

export function LoginPage({ onNavigate, registrationComplete = false }: LoginPageProps) {
  const { login } = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!identifier.trim() || !password) {
      setErrorMessage('Enter your username or email and password.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await login(identifier.trim(), password)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setErrorMessage('Invalid username or password.')
      } else {
        setErrorMessage('Unable to sign in. Check the GuardianX backend and try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-brand">
          <span className="brand-mark" aria-hidden="true">GX</span>
          <div>
            <strong>GuardianX</strong>
            <span>Endpoint defense</span>
          </div>
        </div>
        <div className="login-copy">
          <p className="eyebrow">Secure console access</p>
          <h1 id="login-title">Sign in to GuardianX</h1>
          <p>Access endpoint visibility and security status for your organization.</p>
          {registrationComplete && <p className="login-success" role="status">Account created. Sign in to continue.</p>}
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <label htmlFor="identifier">Username or email</label>
          <input
            id="identifier"
            name="username"
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            disabled={isSubmitting}
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={isSubmitting}
            required
          />
          {errorMessage && <p className="login-error" role="alert">{errorMessage}</p>}
          <button className="login-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <button className="login-link" type="button" onClick={() => onNavigate('/register')}>Create account</button>
        <p className="login-footer">GuardianX protected console</p>
      </section>
    </main>
  )
}
