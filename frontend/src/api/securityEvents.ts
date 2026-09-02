import { apiFetch } from './client'
import type { SecurityEvent } from '../types/api'

export function getSecurityEvents(): Promise<SecurityEvent[]> {
  return apiFetch<SecurityEvent[]>('/security-events')
}

export function getDeviceSecurityEvents(agentId: string): Promise<SecurityEvent[]> {
  return apiFetch<SecurityEvent[]>(`/devices/${agentId}/events`)
}