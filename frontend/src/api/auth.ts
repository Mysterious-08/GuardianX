import { apiFetch } from './client'
import type { AuthToken, UserResponse } from '../types/api'

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export function login(identifier: string, password: string): Promise<AuthToken> {
  const formData = new URLSearchParams()
  formData.set('username', identifier)
  formData.set('password', password)

  return apiFetch<AuthToken>(
    '/auth/login',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    },
    null,
  )
}

export function getCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>('/auth/me')
}

export function registerAccount(account: RegisterRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(account),
  }, null)
}
