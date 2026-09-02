import { apiFetch } from './client'
import type { DeviceListResponse } from '../types/api'

export function getDevices(): Promise<DeviceListResponse> {
  return apiFetch<DeviceListResponse>('/devices')
}
