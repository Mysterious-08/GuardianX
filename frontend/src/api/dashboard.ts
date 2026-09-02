import { apiFetch } from './client'
import type { DashboardOverview } from '../types/api'

export function getDashboardOverview(): Promise<DashboardOverview> {
  return apiFetch<DashboardOverview>('/dashboard/overview')
}
