import { beforeEach, describe, expect, it, vi } from 'vitest'

import { locateCurrentUser } from '@/modules/locations/services/location-provider'
import { INSECURE_ORIGIN_MESSAGE } from '@/modules/locations/utils/geolocation-error'

const testState = vi.hoisted(() => ({
  amapLoad: vi.fn(),
  env: {
    amapKey: '',
    amapSecurityJsCode: '',
  },
}))

vi.mock('@amap/amap-jsapi-loader', () => ({
  default: {
    load: testState.amapLoad,
  },
}))

vi.mock('@/config/env', () => ({
  env: testState.env,
}))

const geolocation = {
  getCurrentPosition: vi.fn(),
}

const permissions = {
  query: vi.fn(),
}

function setSecureContext(value: boolean): void {
  Object.defineProperty(window, 'isSecureContext', {
    configurable: true,
    value,
  })
}

function setGeolocation(value: typeof geolocation | undefined): void {
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value,
  })
}

function setPermissions(value: typeof permissions | undefined): void {
  Object.defineProperty(navigator, 'permissions', {
    configurable: true,
    value,
  })
}

describe('location provider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    testState.env.amapKey = ''
    testState.env.amapSecurityJsCode = ''
    setSecureContext(true)
    setGeolocation(geolocation)
    setPermissions(permissions)
    permissions.query.mockResolvedValue({ state: 'prompt' })
  })

  it('does not call geolocation or report failure for insecure origins', async () => {
    setSecureContext(false)

    const result = await locateCurrentUser()

    expect(result).toEqual({
      ok: false,
      code: 'insecure_origin',
      message: INSECURE_ORIGIN_MESSAGE,
      shouldReportFailure: false,
    })
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled()
  })

  it('can use amap before giving up on insecure origins when configured', async () => {
    testState.env.amapKey = 'test-key'
    setSecureContext(false)
    testState.amapLoad.mockResolvedValueOnce({
      Geolocation: class {
        getCurrentPosition(callback: (status: string, result: unknown) => void): void {
          callback('complete', {
            position: {
              lng: 116.397128,
              lat: 39.916527,
            },
            accuracy: 30,
            formattedAddress: '北京市东城区',
          })
        }
      },
    })

    const result = await locateCurrentUser()

    expect(result).toEqual({
      ok: true,
      longitude: 116.397128,
      latitude: 39.916527,
      accuracy: 30,
      address: '北京市东城区',
      provider: 'amap',
    })
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled()
  })

  it('returns browser coordinates with resilient options', async () => {
    geolocation.getCurrentPosition.mockImplementationOnce((success) => {
      success({
        coords: {
          longitude: 116.397128,
          latitude: 39.916527,
          accuracy: 25.507,
        },
      })
    })

    const result = await locateCurrentUser()

    expect(result).toEqual({
      ok: true,
      longitude: 116.397128,
      latitude: 39.916527,
      accuracy: 25.507,
      provider: 'browser',
    })
    expect(geolocation.getCurrentPosition).toHaveBeenCalledWith(
      expect.any(Function),
      expect.any(Function),
      {
        enableHighAccuracy: true,
        maximumAge: 60_000,
        timeout: 15_000,
      },
    )
  })

  it('normalizes actual browser failures and marks them reportable', async () => {
    geolocation.getCurrentPosition.mockImplementationOnce((_, error) => {
      error({ code: 3, message: '' })
    })

    const result = await locateCurrentUser()

    expect(result).toEqual({
      ok: false,
      code: 'timeout',
      message: '定位超时，请到室外或稍后重试',
      shouldReportFailure: true,
    })
  })

  it('does not report failures when permission was already denied', async () => {
    permissions.query.mockResolvedValueOnce({ state: 'denied' })

    const result = await locateCurrentUser()

    expect(result).toEqual({
      ok: false,
      code: 'permission_denied',
      message: '浏览器定位权限已被拒绝，请在浏览器设置中允许定位后重试',
      shouldReportFailure: false,
    })
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled()
  })
})
