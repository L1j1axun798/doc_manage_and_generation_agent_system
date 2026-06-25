export type AuditResult = 'success' | 'failure' | 'denied'

export interface AuditLog {
  id: number
  user: number | null
  user_username: string
  user_real_name: string
  action: string
  resource_type: string
  resource_id: string
  result: AuditResult
  ip_address: string | null
  user_agent: string
  request_id: string
  before_data: Record<string, unknown> | null
  after_data: Record<string, unknown> | null
  error_message: string
  created_at: string
}

export interface AuditLogQuery {
  page?: number
  search?: string
  ordering?: string
  user?: number
  action?: string
  resource_type?: string
  resource_id?: string
  result?: AuditResult | ''
}
