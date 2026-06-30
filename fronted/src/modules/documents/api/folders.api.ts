import { apiClient } from '@/core/http/client'
import type { FolderTreeNode } from '../documents.types'

export interface FolderCreatePayload {
  project: number | null
  parent: number | null
  name: string
  code: string
  sort_order: number
}

export async function fetchFolderTree(projectId?: number | 'public'): Promise<FolderTreeNode[]> {
  const response = await apiClient.get<FolderTreeNode[]>('/folders/tree/', {
    params: projectId ? { project_id: projectId } : undefined,
  })
  return response.data
}

export async function createFolder(payload: FolderCreatePayload): Promise<FolderTreeNode> {
  const response = await apiClient.post<FolderTreeNode>('/folders/', payload)
  return response.data
}

export async function disableFolder(folderId: number): Promise<void> {
  await apiClient.post(`/folders/${folderId}/disable/`)
}
