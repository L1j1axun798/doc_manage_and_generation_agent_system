const DEFAULT_APP_TITLE = '绿能信盾资料管理系统'
const DEFAULT_API_BASE_URL = '/api/v1'

export function normalizeApiBaseUrl(value: string): string {
  const normalized = value.trim().replace(/\/+$/, '')
  return normalized || DEFAULT_API_BASE_URL
}

export const env = {
  appTitle: import.meta.env.VITE_APP_TITLE || DEFAULT_APP_TITLE,
  apiBaseUrl: normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL),
}
