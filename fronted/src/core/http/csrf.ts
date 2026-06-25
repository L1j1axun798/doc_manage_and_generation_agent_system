import { AxiosHeaders, type AxiosInstance } from 'axios'

export const CSRF_COOKIE_NAME = 'csrftoken'
export const CSRF_HEADER_NAME = 'X-CSRFToken'

const SAFE_METHODS = new Set(['get', 'head', 'options'])

export function readCookie(name: string): string | null {
  if (typeof document === 'undefined') {
    return null
  }

  const cookies = document.cookie ? document.cookie.split('; ') : []
  const prefix = `${encodeURIComponent(name)}=`
  const match = cookies.find((cookie) => cookie.startsWith(prefix))

  if (!match) {
    return null
  }

  return decodeURIComponent(match.slice(prefix.length))
}

export function attachCsrfInterceptor(instance: AxiosInstance): void {
  instance.interceptors.request.use((config) => {
    const method = (config.method || 'get').toLowerCase()

    if (SAFE_METHODS.has(method)) {
      return config
    }

    const token = readCookie(CSRF_COOKIE_NAME)

    if (!token) {
      return config
    }

    const headers = AxiosHeaders.from(config.headers)
    if (!headers.has(CSRF_HEADER_NAME)) {
      headers.set(CSRF_HEADER_NAME, token)
    }
    config.headers = headers

    return config
  })
}
