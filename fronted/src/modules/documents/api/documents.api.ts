import { apiClient } from '@/core/http/client'
import { getFilenameFromContentDisposition, saveBlob } from '@/core/http/download'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  DocumentItem,
  DocumentListQuery,
  DocumentMovePayload,
  DocumentMutationPayload,
  SingleDocumentUploadPayload,
  DocumentUpdatePayload,
  DocumentVersion,
} from '../documents.types'

export async function fetchDocuments(query: DocumentListQuery): Promise<ApiPage<DocumentItem>> {
  const response = await apiClient.get<ApiPage<DocumentItem>>('/documents/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function fetchDocument(documentId: number): Promise<DocumentItem> {
  const response = await apiClient.get<DocumentItem>(`/documents/${documentId}/`)
  return response.data
}

export async function fetchTrashDocuments(query: DocumentListQuery): Promise<ApiPage<DocumentItem>> {
  const response = await apiClient.get<ApiPage<DocumentItem>>('/documents/trash/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function uploadDocument(payload: SingleDocumentUploadPayload): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('folder', String(payload.folder))
  formData.append('file', payload.file)
  formData.append('title', payload.title || '')
  formData.append('description', payload.description || '')
  formData.append('access_level', payload.access_level)
  if (payload.source_type) {
    formData.append('source_type', payload.source_type)
  }

  const response = await apiClient.post<DocumentItem>('/documents/', formData)
  return response.data
}

export async function updateDocument(
  documentId: number,
  payload: DocumentUpdatePayload,
): Promise<DocumentItem> {
  const response = await apiClient.patch<DocumentItem>(`/documents/${documentId}/`, payload)
  return response.data
}

export async function moveDocument(
  documentId: number,
  payload: DocumentMovePayload,
): Promise<DocumentItem> {
  const response = await apiClient.post<DocumentItem>(`/documents/${documentId}/move/`, payload)
  return response.data
}

export async function deleteDocument(
  documentId: number,
  payload: DocumentMutationPayload,
): Promise<void> {
  await apiClient.post(`/documents/${documentId}/delete/`, payload)
}

export async function restoreDocument(
  documentId: number,
  payload: DocumentMutationPayload,
): Promise<DocumentItem> {
  const response = await apiClient.post<DocumentItem>(`/documents/${documentId}/restore/`, payload)
  return response.data
}

export async function uploadDocumentVersion(documentId: number, file: File): Promise<DocumentVersion> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post<DocumentVersion>(`/documents/${documentId}/versions/`, formData)
  return response.data
}

export async function downloadDocument(document: DocumentItem): Promise<void> {
  const response = await apiClient.get<Blob>(`/documents/${document.id}/download/`, {
    responseType: 'blob',
  })
  const filename = getFilenameFromContentDisposition(response.headers['content-disposition'] ?? null)
    || document.current_version?.original_filename
    || `${document.title}.bin`
  saveBlob(response.data, filename)
}

function cleanQuery(query: DocumentListQuery): DocumentListQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
