import { apiClient } from '@/core/http/client'
import type { FolderTreeNode } from '../documents.types'

export async function fetchFolderTree(projectId?: number | 'public'): Promise<FolderTreeNode[]> {
  const response = await apiClient.get<FolderTreeNode[]>('/folders/tree/', {
    params: projectId ? { project_id: projectId } : undefined,
  })
  return response.data
}
