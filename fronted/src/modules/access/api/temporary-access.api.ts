import { apiClient } from '@/core/http/client'
import { getFilenameFromContentDisposition, saveBlob } from '@/core/http/download'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  TemporaryAccessGrant,
  TemporaryAccessGrantCreated,
  TemporaryAccessGrantPayload,
  TemporaryAccessGrantQuery,
} from '../access.types'

export async function fetchTemporaryAccessGrants(
  query: TemporaryAccessGrantQuery,
): Promise<ApiPage<TemporaryAccessGrant>> {
  const response = await apiClient.get<ApiPage<TemporaryAccessGrant>>('/temporary-access-grants/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function createTemporaryAccessGrant(
  payload: TemporaryAccessGrantPayload,
): Promise<TemporaryAccessGrantCreated> {
  const response = await apiClient.post<TemporaryAccessGrantCreated>(
    '/temporary-access-grants/',
    payload,
  )
  return response.data
}

export async function revokeTemporaryAccessGrant(grantId: number): Promise<TemporaryAccessGrant> {
  const response = await apiClient.post<TemporaryAccessGrant>(
    `/temporary-access-grants/${grantId}/revoke/`,
  )
  return response.data
}

export async function downloadTemporaryAccess(token: string): Promise<void> {
  const response = await apiClient.get<Blob>(`/temporary-access/${token}/download/`, {
    responseType: 'blob',
  })
  const filename = getFilenameFromContentDisposition(response.headers['content-disposition'] ?? null)
    || 'temporary-download.bin'
  saveBlob(response.data, filename)
}

function cleanQuery(query: TemporaryAccessGrantQuery): TemporaryAccessGrantQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
