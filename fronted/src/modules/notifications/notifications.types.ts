export type NotificationCategory = 'system' | 'document' | 'access'

export interface AppNotification {
  id: number
  title: string
  message: string
  category: NotificationCategory
  resource_type: string
  resource_id: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationListQuery {
  page?: number
  search?: string
  ordering?: string
  category?: NotificationCategory | ''
  is_read?: boolean | ''
}
