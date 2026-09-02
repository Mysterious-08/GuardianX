interface ErrorStateProps {
  authenticationRequired: boolean
  onRetry: () => void
  title?: string
  description?: string
}

export function ErrorState({ authenticationRequired, description, onRetry, title }: ErrorStateProps) {
  return (
    <section className="state-panel error-state" role="alert">
      <span className="state-mark state-mark-error" aria-hidden="true">{authenticationRequired ? '!' : '×'}</span>
      <div>
        <h2>{title ?? (authenticationRequired ? 'Authentication required' : 'Unable to load dashboard')}</h2>
        <p>{description ?? (authenticationRequired ? 'Sign in to access the GuardianX console.' : 'Check the connection to GuardianX and try again.')}</p>
      </div>
      <button className="button button-secondary" type="button" onClick={onRetry}>
        Retry
      </button>
    </section>
  )
}
