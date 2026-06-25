import type { AxiosInstance } from 'axios'

import { normalizeApiError } from './error-normalizer'

export function attachErrorInterceptor(instance: AxiosInstance): void {
  instance.interceptors.response.use(
    (response) => response,
    (error: unknown) => Promise.reject(normalizeApiError(error)),
  )
}
