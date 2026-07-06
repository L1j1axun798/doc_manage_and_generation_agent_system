import { describe, expect, it, vi } from 'vitest'

import {
  INSECURE_ORIGIN_MESSAGE,
  isInsecureGeolocationContext,
  normalizeGeolocationErrorMessage,
} from '@/modules/locations/utils/geolocation-error'

describe('geolocation error helpers', () => {
  it('normalizes insecure origin errors', () => {
    expect(
      normalizeGeolocationErrorMessage({
        message: 'Only secure origins are allowed (see: https://goo.gl/Y0ZkNV).',
      }),
    ).toBe(INSECURE_ORIGIN_MESSAGE)
  })

  it('keeps browser geolocation messages when they are actionable', () => {
    expect(normalizeGeolocationErrorMessage({ message: '用户拒绝定位授权' })).toBe(
      '用户拒绝定位授权',
    )
  })

  it('normalizes browser geolocation error codes', () => {
    expect(normalizeGeolocationErrorMessage({ code: 1 })).toBe('用户拒绝定位授权')
    expect(normalizeGeolocationErrorMessage({ code: 2 })).toBe('设备暂时无法获取位置')
    expect(normalizeGeolocationErrorMessage({ code: 3 })).toBe('定位超时，请到室外或稍后重试')
  })

  it('detects insecure browser contexts', () => {
    vi.stubGlobal('isSecureContext', false)
    expect(isInsecureGeolocationContext()).toBe(true)
    vi.unstubAllGlobals()
  })
})
