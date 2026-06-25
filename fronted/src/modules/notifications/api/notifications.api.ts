import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type { AppNotification, NotificationListQuery } from '../notifications.types'

export async function fetchNotifications(
  query: NotificationListQuery,
): Promise<ApiPage<AppNotification>> {
  const response = await apiClient.get<ApiPage<AppNotification>>('/notifications/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function fetchNotification(notificationId: number): Promise<AppNotification> {
  const response = await apiClient.get<AppNotification>(`/notifications/${notificationId}/`)
  return response.data
}

export async function markNotificationRead(notificationId: number): Promise<AppNotification> {
  const response = await apiClient.post<AppNotification>(`/notifications/${notificationId}/read/`)
  return response.data
}

export async function markNotificationUnread(notificationId: number): Promise<AppNotification> {
  const response = await apiClient.post<AppNotification>(`/notifications/${notificationId}/unread/`)
  return response.data
}

function cleanQuery(query: NotificationListQuery): NotificationListQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
