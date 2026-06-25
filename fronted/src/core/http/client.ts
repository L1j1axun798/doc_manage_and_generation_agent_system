import axios from 'axios'

import { env } from '@/config/env'
import { attachCsrfInterceptor } from './csrf'
import { attachErrorInterceptor } from './interceptors'

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  withCredentials: true,
  headers: {
    Accept: 'application/json',
  },
})

attachCsrfInterceptor(apiClient)
attachErrorInterceptor(apiClient)
