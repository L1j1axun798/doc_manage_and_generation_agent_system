export interface DocumentGrant {
  id: number
  document: number
  document_title: string
  user: number
  user_username: string
  user_real_name: string
  user_phone: string
  can_view: boolean
  can_download: boolean
  can_update: boolean
  can_delete: boolean
  can_restore: boolean
  expires_at: string | null
  is_expired: boolean
  is_active: boolean
  created_by: number | null
  created_by_name: string
  created_at: string
  updated_at: string
  revoked_at: string | null
  revoked_by: number | null
  revoked_by_name: string
}

export interface DocumentGrantPayload {
  document: number
  user: number
  can_view: boolean
  can_download: boolean
  can_update: boolean
  can_delete: boolean
  can_restore: boolean
  expires_at: string | null
}

export interface DocumentGrantQuery {
  page?: number
  document?: number
  user?: number
  revoked_at?: string
  search?: string
  ordering?: string
}

export interface TemporaryAccessGrant {
  id: number
  document_version: number
  document: number
  document_title: string
  original_filename: string
  max_downloads: number
  used_count: number
  remaining_downloads: number
  expires_at: string
  is_expired: boolean
  is_active: boolean
  created_by: number | null
  created_by_name: string
  created_at: string
  revoked_at: string | null
  revoked_by: number | null
  revoked_by_name: string
  last_used_at: string | null
}

export interface TemporaryAccessGrantCreated extends TemporaryAccessGrant {
  token: string
  download_url: string
}

export interface TemporaryAccessGrantPayload {
  document_version: number
  max_downloads: number
  expires_at?: string
}

export interface TemporaryAccessGrantQuery {
  page?: number
  document_version?: number
  revoked_at?: string
  search?: string
  ordering?: string
}
