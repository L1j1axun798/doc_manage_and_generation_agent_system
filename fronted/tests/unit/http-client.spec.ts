import { apiClient } from '@/core/http/client'

it('enables cookie credentials for session based APIs', () => {
  expect(apiClient.defaults.withCredentials).toBe(true)
  expect(apiClient.defaults.baseURL).toBe('/api/v1')
})
