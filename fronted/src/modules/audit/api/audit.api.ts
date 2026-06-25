import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type { AuditLog, AuditLogQuery } from '../audit.types'

export async function fetchAuditLogs(query: AuditLogQuery): Promise<ApiPage<AuditLog>> {
  const response = await apiClient.get<ApiPage<AuditLog>>('/audit-logs/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function fetchAuditLog(auditLogId: number): Promise<AuditLog> {
  const response = await apiClient.get<AuditLog>(`/audit-logs/${auditLogId}/`)
  return response.data
}

function cleanQuery(query: AuditLogQuery): AuditLogQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
