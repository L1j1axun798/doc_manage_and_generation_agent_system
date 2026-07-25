import { env, normalizeApiBaseUrl, parseBooleanFlag } from '@/config/env'

it('normalizes the API base URL', () => {
  expect(normalizeApiBaseUrl('/api/v1/')).toBe('/api/v1')
  expect(normalizeApiBaseUrl('  /api/v1  ')).toBe('/api/v1')
})

it('uses the configured API prefix', () => {
  expect(env.apiBaseUrl).toBe('/api/v1')
})

it('keeps opt-in feature flags disabled unless explicitly enabled', () => {
  expect(parseBooleanFlag(undefined)).toBe(false)
  expect(parseBooleanFlag('false')).toBe(false)
  expect(parseBooleanFlag('TRUE')).toBe(true)
  expect(parseBooleanFlag('1')).toBe(true)
})
