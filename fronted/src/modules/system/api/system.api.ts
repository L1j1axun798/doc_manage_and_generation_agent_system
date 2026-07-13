import { apiClient } from '@/core/http/client'
import type { HealthStatus, SystemBackupRun } from '../system.types'

export async function fetchHealthStatus(): Promise<HealthStatus> {
  const response = await apiClient.get<HealthStatus>('/health/')
  return response.data
}

export async function fetchLatestSystemBackup(): Promise<SystemBackupRun | null> {
  const response = await apiClient.get<SystemBackupRun | null>('/system/backups/latest/')
  return response.data || null
}
