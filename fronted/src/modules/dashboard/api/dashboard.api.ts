import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'

export interface DashboardCounts {
  visibleDocuments: number
  myProjects: number
  unreadNotifications: number
  activeGrants: number
}

export async function fetchDashboardCounts(): Promise<DashboardCounts> {
  const [documentsRes, projectsRes, notificationsRes, grantsRes] =
    await Promise.allSettled([
      apiClient.get<ApiPage<unknown>>('/documents/', { params: { limit: 1 } }),
      apiClient.get<ApiPage<unknown>>('/projects/', { params: { limit: 1 } }),
      apiClient.get<ApiPage<unknown>>('/notifications/', {
        params: { limit: 1, is_read: 'false' },
      }),
      apiClient.get<ApiPage<unknown>>('/document-grants/', { params: { limit: 1 } }),
    ])

  return {
    visibleDocuments: extractCount(documentsRes),
    myProjects: extractCount(projectsRes),
    unreadNotifications: extractCount(notificationsRes),
    activeGrants: extractCount(grantsRes),
  }
}

function extractCount(result: PromiseSettledResult<{ data: ApiPage<unknown> }>): number {
  if (result.status === 'fulfilled') {
    return result.value.data.count
  }
  return 0
}
