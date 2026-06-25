import { AxiosError } from 'axios'

import { normalizeApiError } from '@/core/http/error-normalizer'

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
