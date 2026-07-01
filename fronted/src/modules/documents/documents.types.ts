export interface FolderTreeNode {
  id: number
  project: number | null
  parent: number | null
  name: string
  code: string
  sort_order: number
  is_active: boolean
  is_system_root: boolean
  children: FolderTreeNode[]
}

export interface DocumentVersion {
  id: number
  document: number
  version_number: number
  original_filename: string
  content_type: string
  file_size: number
  sha256: string
  uploaded_by: number | null
  uploaded_by_name: string | null
  created_at: string
}

export interface DocumentItem {
  id: number
  project: number | null
  project_name: string | null
  folder: number
  folder_name: string
  title: string
  description: string
  current_version: DocumentVersion | null
  can_download: boolean
  lock_version: number
  deleted_at: string | null
  deleted_by: number | null
  deleted_by_name: string | null
  created_by: number | null
  created_by_name: string | null
  created_at: string
  updated_at: string
}

export interface DocumentListQuery {
  page?: number
  search?: string
  ordering?: string
  project?: number
  folder?: number
}

export interface DocumentUploadPayload {
  folder: number
  file: File
  title?: string
  description?: string
}

export interface DocumentUpdatePayload {
  title?: string
  description?: string
  expected_updated_at: string
}

export interface DocumentMovePayload {
  folder: number
  expected_updated_at: string
}

export interface DocumentMutationPayload {
  expected_updated_at: string
}
