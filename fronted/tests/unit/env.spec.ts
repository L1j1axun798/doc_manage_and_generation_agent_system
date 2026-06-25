import { env, normalizeApiBaseUrl } from '@/config/env'

it('normalizes the API base URL', () => {
  expect(normalizeApiBaseUrl('/api/v1/')).toBe('/api/v1')
  expect(normalizeApiBaseUrl('  /api/v1  ')).toBe('/api/v1')
})

it('uses the configured API prefix', () => {
  expect(env.apiBaseUrl).toBe('/api/v1')
})
