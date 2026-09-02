import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { registerAccount } from '../../api/auth'

interface RegisterPageProps {
  onNavigate: (path: string) => void
}

export function RegisterPage({ onNavigate }: RegisterPageProps) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedUsername = username.trim()
    if (!/^[A-Za-z0-9_]{3,50}$/.test(trimmedUsername)) {
      setErrorMessage('Username must be 3-50 characters using only letters, numbers, or underscores.')
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
      setErrorMessage('Enter a valid email address.')
      return
    }
    if (password.length < 8 || password.length > 128 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      setErrorMessage('Password must be 8-128 characters and include uppercase, lowercase, and numeric characters.')
      return
    }
    if (password !== confirmation) {
      setErrorMessage('Passwords do not match.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await registerAccount({ username: trimmedUsername, email: email.trim(), password })
      onNavigate('/login?registered=1')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setErrorMessage('An account with that username or email already exists.')
      else if (error instanceof ApiError && error.status === 422) setErrorMessage(error.message || 'Check the registration details and try again.')
      else setErrorMessage('GuardianX backend unavailable. Check the connection and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel register-panel" aria-labelledby="register-title">
        <div className="login-brand">
          <span className="brand-mark" aria-hidden="true">GX</span>
          <div><strong>GuardianX</strong><span>Endpoint defense</span></div>
        </div>
        <div className="login-copy">
          <p className="eyebrow">Secure console access</p>
          <h1 id="register-title">Create a GuardianX account</h1>
          <p>Set up an operator account for the protected security console.</p>
        </div>
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <label htmlFor="register-username">Username</label>
          <input id="register-username" type="text" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} disabled={isSubmitting} required />
          <label htmlFor="register-email">Email</label>
          <input id="register-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={isSubmitting} required />
          <label htmlFor="register-password">Password</label>
          <input id="register-password" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={isSubmitting} required />
          <label htmlFor="register-confirmation">Confirm password</label>
          <input id="register-confirmation" type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} disabled={isSubmitting} required />
          {errorMessage && <p className="login-error" role="alert">{errorMessage}</p>}
          <button className="login-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Creating account...' : 'Create account'}</button>
        </form>
        <button className="login-link" type="button" onClick={() => onNavigate('/login')}>Back to sign in</button>
        <p className="login-footer">GuardianX protected console</p>
      </section>
    </main>
  )
}