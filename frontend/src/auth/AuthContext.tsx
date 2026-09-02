import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { getCurrentUser, login as loginRequest } from '../api/auth'
import { ApiError, clearAccessToken, getAccessToken, setAccessToken } from '../api/client'
import { AuthContext, type AuthContextValue, type AuthStatus } from './auth-context'
import type { UserResponse } from '../types/api'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<UserResponse | null>(null)

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
    setStatus('unauthenticated')
  }, [])

  const login = useCallback(async (identifier: string, password: string) => {
    const token = await loginRequest(identifier, password)
    setAccessToken(token.access_token)
    try {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
      setStatus('authenticated')
    } catch (error) {
      clearAccessToken()
      setUser(null)
      setStatus('unauthenticated')
      throw error
    }
  }, [])

  useEffect(() => {
    queueMicrotask(() => {
      if (!getAccessToken()) {
        setStatus('unauthenticated')
        return
      }

      void getCurrentUser()
        .then((currentUser) => {
          setUser(currentUser)
          setStatus('authenticated')
        })
        .catch((error: unknown) => {
          if (error instanceof ApiError && error.status === 401) clearAccessToken()
          setUser(null)
          setStatus('unauthenticated')
        })
    })
  }, [])

  const value: AuthContextValue = { status, user, login, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
