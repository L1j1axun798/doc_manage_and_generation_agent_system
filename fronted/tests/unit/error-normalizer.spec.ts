import axios, { AxiosError } from 'axios'
import { expect, it, vi } from 'vitest'

import { normalizeApiError } from '@/core/http/error-normalizer'
import { attachErrorInterceptor } from '@/core/http/interceptors'
import {
  consumePendingSessionReplacement,
  SESSION_REPLACED_EVENT,
} from '@/core/http/session-events'

it('uses backend message fields as error details', () => {
  const error = new AxiosError('Request failed')
  error.response = {
    data: {
      message: '原密码错误',
      code: 'authentication_failed',
    },
    status: 401,
    statusText: 'Unauthorized',
    headers: {},
    config: {} as never,
  }

  expect(normalizeApiError(error).detail).toBe('原密码错误')
})

it('preserves Axios cancellation codes', () => {
  const error = new AxiosError('canceled', 'ERR_CANCELED')

  expect(normalizeApiError(error)).toMatchObject({
    code: 'ERR_CANCELED',
    detail: 'canceled',
  })
})

it('announces a replaced session after normalizing the backend response', async () => {
  const instance = axios.create()
  attachErrorInterceptor(instance)
  const listener = vi.fn()
  window.addEventListener(SESSION_REPLACED_EVENT, listener, { once: true })
  const error = new AxiosError('Forbidden')
  error.response = {
    data: {
      message: '您的账号已在其他设备或浏览器重新登录，当前登录已下线。',
      code: 'session_replaced',
    },
    status: 403,
    statusText: 'Forbidden',
    headers: {},
    config: {} as never,
  }

  await expect(instance.request({
    url: '/auth/me/',
    adapter: () => Promise.reject(error),
  })).rejects.toMatchObject({ code: 'session_replaced' })

  expect(listener).toHaveBeenCalledOnce()
  expect(consumePendingSessionReplacement()).toBe(true)
})
