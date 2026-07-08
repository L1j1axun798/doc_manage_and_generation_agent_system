import axios from 'axios'

export interface NormalizedApiError {
  status?: number
  detail: string
  fieldErrors?: Record<string, string[]>
}

export function normalizeApiError(error: unknown): NormalizedApiError {
  if (isNormalizedApiError(error)) {
    return error
  }

  if (!axios.isAxiosError(error)) {
    if (error instanceof Error && error.message.trim()) {
      return {
        detail: error.message,
      }
    }

    return {
      detail: '请求处理失败',
    }
  }

  const status = error.response?.status
  const data = error.response?.data

  if (isRecord(data)) {
    return {
      status,
      detail: readDetail(data),
      fieldErrors: readFieldErrors(data),
    }
  }

  return {
    status,
    detail: error.message || '请求处理失败',
  }
}

export function isNormalizedApiError(error: unknown): error is NormalizedApiError {
  return (
    typeof error === 'object'
    && error !== null
    && 'detail' in error
    && typeof (error as { detail: unknown }).detail === 'string'
  )
}

export function getErrorMessage(error: unknown): string {
  return normalizeApiError(error).detail
}

function readDetail(data: Record<string, unknown>): string {
  const detail = data.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }

  const message = data.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }

  return '请求处理失败'
}

function readFieldErrors(data: Record<string, unknown>): Record<string, string[]> | undefined {
  const entries = Object.entries(data)
    .filter(([key]) => key !== 'detail')
    .map(([key, value]) => [key, normalizeFieldError(value)] as const)
    .filter(([, value]) => value.length > 0)

  if (entries.length === 0) {
    return undefined
  }

  return Object.fromEntries(entries)
}

function normalizeFieldError(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string')
  }

  if (typeof value === 'string') {
    return [value]
  }

  return []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
