import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  PersonnelListQuery,
  PersonnelRecord,
  PersonnelUpdatePayload,
} from '../system.types'

export async function fetchPersonnel(
  query: PersonnelListQuery,
): Promise<ApiPage<PersonnelRecord>> {
  const response = await apiClient.get<ApiPage<PersonnelRecord>>('/personnel/', {
    params: Object.fromEntries(
      Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
    ),
  })
  return response.data
}

export async function updatePersonnel(
  folderId: number,
  payload: PersonnelUpdatePayload,
): Promise<PersonnelRecord> {
  const response = await apiClient.patch<PersonnelRecord>(`/personnel/${folderId}/`, payload)
  return response.data
}
