export type ProjectStatus = 'active' | 'archived'
export type ProjectMemberRole = 'manager' | 'operator' | 'viewer'

export interface Project {
  id: number
  name: string
  code: string
  description: string
  manager: number | null
  manager_name: string | null
  status: ProjectStatus
  created_by: number | null
  created_by_name: string | null
  created_at: string
  updated_at: string
  archived_at: string | null
  archived_by: number | null
}

export interface ProjectMember {
  id: number
  project: number
  user: number
  user_username: string
  user_real_name: string
  role: ProjectMemberRole
  can_upload: boolean
  can_download_restricted: boolean
  can_manage_folder: boolean
  can_delete: boolean
  can_restore: boolean
  can_manage_permission: boolean
  joined_at: string
}

export interface ProjectListQuery {
  page?: number
  search?: string
  ordering?: string
}

export interface ProjectPayload {
  name: string
  code: string
  description?: string
  manager?: number | null
}

export interface ProjectMemberPayload {
  user?: number
  role: ProjectMemberRole
  can_upload: boolean
  can_download_restricted: boolean
  can_manage_folder: boolean
  can_delete: boolean
  can_restore: boolean
  can_manage_permission: boolean
}
