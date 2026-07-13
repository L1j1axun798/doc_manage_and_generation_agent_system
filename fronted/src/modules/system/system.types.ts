export interface SystemFolder {
  id: number
  project: number | null
  project_name: string | null
  parent: number | null
  parent_name: string | null
  name: string
  code: string
  sort_order: number
  is_active: boolean
  is_system_root: boolean
  created_by: number | null
  created_by_name: string
  created_at: string
  updated_at: string
}

export interface FolderListQuery {
  page?: number
  search?: string
  ordering?: string
}

export interface FolderCreatePayload {
  project: number | null
  parent: number | null
  name: string
  code: string
  sort_order: number
}

export interface FolderUpdatePayload {
  name: string
  code: string
  sort_order: number
}

export interface FolderMovePayload {
  parent?: number | null
  sort_order?: number
}

export interface HealthStatus {
  status: string
  service: string
  debug: boolean
  request_id: string | null
}

export type SystemBackupStatus = 'running' | 'success' | 'failure'
export type SystemBackupTrigger = 'scheduled' | 'manual'

export interface SystemBackupRun {
  id: number
  trigger: SystemBackupTrigger
  status: SystemBackupStatus
  started_at: string
  finished_at: string | null
  local_available: boolean
  offsite_available: boolean
  sha256: string
  size_bytes: number
  error_summary: string
  created_by: number | null
  created_by_username: string
  created_by_real_name: string
  created_at: string
  updated_at: string
}
