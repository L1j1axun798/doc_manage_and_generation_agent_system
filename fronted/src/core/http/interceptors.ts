import type { AxiosInstance } from 'axios'

import { normalizeApiError } from './error-normalizer'
import { notifySessionReplaced } from './session-events'

export function attachErrorInterceptor(instance: AxiosInstance): void {
  instance.interceptors.response.use(
    (response) => response,
    (error: unknown) => {
      const normalizedError = normalizeApiError(error)
      if (normalizedError.code === 'session_replaced') {
        notifySessionReplaced()
      }
      return Promise.reject(normalizedError)
    },
  )
}
