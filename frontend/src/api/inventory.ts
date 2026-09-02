import { apiFetch } from './client'
import type { DeviceInventory } from '../types/api'

export function getDeviceInventory(agentId: string): Promise<DeviceInventory> {
  return apiFetch<DeviceInventory>(`/devices/${agentId}/inventory`)
}