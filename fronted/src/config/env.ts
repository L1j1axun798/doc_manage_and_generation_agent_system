const DEFAULT_APP_TITLE = '绿能信盾资料管理系统'
const DEFAULT_API_BASE_URL = '/api/v1'

export function normalizeApiBaseUrl(value: string): string {
  const normalized = value.trim().replace(/\/+$/, '')
  return normalized || DEFAULT_API_BASE_URL
}

export function parseBooleanFlag(value: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on'].includes((value || '').trim().toLowerCase())
}

export const env = {
  appTitle: import.meta.env.VITE_APP_TITLE || DEFAULT_APP_TITLE,
  apiBaseUrl: normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL),
  amapKey: import.meta.env.VITE_AMAP_KEY || '',
  amapSecurityJsCode: import.meta.env.VITE_AMAP_SECURITY_JS_CODE || '',
  documentAgentEnabled: parseBooleanFlag(import.meta.env.VITE_DOCUMENT_AGENT_ENABLED),
}
