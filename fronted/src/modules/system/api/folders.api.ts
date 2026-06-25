import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  FolderCreatePayload,
  FolderListQuery,
  FolderMovePayload,
  FolderUpdatePayload,
  SystemFolder,
} from '../system.types'

export async function fetchFolders(query: FolderListQuery): Promise<ApiPage<SystemFolder>> {
  const response = await apiClient.get<ApiPage<SystemFolder>>('/folders/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function createFolder(payload: FolderCreatePayload): Promise<SystemFolder> {
  const response = await apiClient.post<SystemFolder>('/folders/', payload)
  return response.data
}

export async function updateFolder(
  folderId: number,
  payload: FolderUpdatePayload,
): Promise<SystemFolder> {
  const response = await apiClient.patch<SystemFolder>(`/folders/${folderId}/`, payload)
  return response.data
}

export async function moveFolder(folderId: number, payload: FolderMovePayload): Promise<SystemFolder> {
  const response = await apiClient.post<SystemFolder>(`/folders/${folderId}/move/`, payload)
  return response.data
}

export async function disableFolder(folderId: number): Promise<void> {
  await apiClient.post(`/folders/${folderId}/disable/`)
}

function cleanQuery(query: FolderListQuery): FolderListQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
