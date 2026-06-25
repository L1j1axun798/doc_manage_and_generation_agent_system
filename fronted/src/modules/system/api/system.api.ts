import { apiClient } from '@/core/http/client'
import type { HealthStatus } from '../system.types'

export async function fetchHealthStatus(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>('/health/')
  return response.data
}
