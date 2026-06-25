import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type { DocumentGrant, DocumentGrantPayload, DocumentGrantQuery } from '../access.types'

export async function fetchDocumentGrants(
  query: DocumentGrantQuery,
): Promise<ApiPage<DocumentGrant>> {
  const response = await apiClient.get<ApiPage<DocumentGrant>>('/document-grants/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function createDocumentGrant(payload: DocumentGrantPayload): Promise<DocumentGrant> {
  const response = await apiClient.post<DocumentGrant>('/document-grants/', payload)
  return response.data
}

export async function updateDocumentGrant(
  grantId: number,
  payload: Partial<DocumentGrantPayload>,
): Promise<DocumentGrant> {
  const response = await apiClient.patch<DocumentGrant>(`/document-grants/${grantId}/`, payload)
  return response.data
}

export async function revokeDocumentGrant(grantId: number): Promise<DocumentGrant> {
  const response = await apiClient.post<DocumentGrant>(`/document-grants/${grantId}/revoke/`)
  return response.data
}

function cleanQuery(query: DocumentGrantQuery): DocumentGrantQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
