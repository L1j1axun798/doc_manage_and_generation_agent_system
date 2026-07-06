import AMapLoader from '@amap/amap-jsapi-loader'

import { env } from '@/config/env'
import {
  INSECURE_ORIGIN_MESSAGE,
  isInsecureGeolocationContext,
  normalizeGeolocationErrorMessage,
} from '../utils/geolocation-error'

const BROWSER_LOCATION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  maximumAge: 60_000,
  timeout: 15_000,
}

const UNSUPPORTED_MESSAGE = '当前浏览器不支持定位'
const PERMISSION_DENIED_MESSAGE = '浏览器定位权限已被拒绝，请在浏览器设置中允许定位后重试'

type LocationProvider = 'browser' | 'amap'

export type LocationFailureCode =
  | 'insecure_origin'
  | 'unsupported'
  | 'permission_denied'
  | 'unavailable'
  | 'timeout'
  | 'unknown'

type LocationSuccessResult = {
  ok: true
  longitude: number
  latitude: number
  accuracy: number | null
  address?: string
  provider: LocationProvider
}

type LocationFailureResult = {
  ok: false
  code: LocationFailureCode
  message: string
  shouldReportFailure: boolean
}

export type LocationResult = LocationSuccessResult | LocationFailureResult

interface AMapPosition {
  lng?: number
  lat?: number
  getLng?: () => number
  getLat?: () => number
}

interface AMapGeolocationResult {
  position?: AMapPosition
  accuracy?: number
  formattedAddress?: string
  message?: string
  info?: string
}

interface AMapGeolocation {
  getCurrentPosition(
    callback: (status: 'complete' | 'error', result: AMapGeolocationResult) => void,
  ): void
}

interface AMapNamespace {
  Geolocation: new (options: {
    enableHighAccuracy: boolean
    timeout: number
    zoomToAccuracy: boolean
  }) => AMapGeolocation
}

export async function locateCurrentUser(): Promise<LocationResult> {
  const precheck = await precheckBrowserLocation()
  if (precheck) {
    if (env.amapKey && canTryAmapAfterPrecheckFailure(precheck.code)) {
      const amapResult = await tryLocateByAmap()
      if (amapResult?.ok) {
        return amapResult
      }
    }
    return precheck
  }

  const browserResult = await locateByBrowser()
  if (browserResult.ok || !env.amapKey || browserResult.code === 'permission_denied') {
    return browserResult
  }

  return locateByAmap().catch((error: unknown) => ({
    ok: false,
    code: getFailureCode(error),
    message: normalizeGeolocationErrorMessage(error),
    shouldReportFailure: true,
  }))
}

function canTryAmapAfterPrecheckFailure(code: LocationFailureCode): boolean {
  return code === 'insecure_origin' || code === 'unsupported'
}

async function tryLocateByAmap(): Promise<LocationResult | null> {
  try {
    return await locateByAmap()
  } catch {
    return null
  }
}

async function precheckBrowserLocation(): Promise<LocationFailureResult | null> {
  if (isInsecureGeolocationContext()) {
    return {
      ok: false,
      code: 'insecure_origin',
      message: INSECURE_ORIGIN_MESSAGE,
      shouldReportFailure: false,
    }
  }

  if (!navigator.geolocation) {
    return {
      ok: false,
      code: 'unsupported',
      message: UNSUPPORTED_MESSAGE,
      shouldReportFailure: false,
    }
  }

  const permissionState = await getGeolocationPermissionState()
  if (permissionState === 'denied') {
    return {
      ok: false,
      code: 'permission_denied',
      message: PERMISSION_DENIED_MESSAGE,
      shouldReportFailure: false,
    }
  }

  return null
}

async function getGeolocationPermissionState(): Promise<PermissionState | null> {
  if (!navigator.permissions?.query) {
    return null
  }

  try {
    const status = await navigator.permissions.query({ name: 'geolocation' })
    return status.state
  } catch {
    return null
  }
}

async function locateByBrowser(): Promise<LocationResult> {
  try {
    const position = await getBrowserCurrentPosition()
    return {
      ok: true,
      longitude: position.coords.longitude,
      latitude: position.coords.latitude,
      accuracy: position.coords.accuracy,
      provider: 'browser',
    }
  } catch (error) {
    return {
      ok: false,
      code: getFailureCode(error),
      message: normalizeGeolocationErrorMessage(error),
      shouldReportFailure: true,
    }
  }
}

function getBrowserCurrentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, BROWSER_LOCATION_OPTIONS)
  })
}

async function locateByAmap(): Promise<LocationResult> {
  if (env.amapSecurityJsCode) {
    window._AMapSecurityConfig = {
      securityJsCode: env.amapSecurityJsCode,
    }
  }

  const amap = (await AMapLoader.load({
    key: env.amapKey,
    version: '2.0',
    plugins: ['AMap.Geolocation'],
  })) as AMapNamespace

  return new Promise((resolve) => {
    const geolocation = new amap.Geolocation({
      enableHighAccuracy: true,
      timeout: BROWSER_LOCATION_OPTIONS.timeout ?? 15_000,
      zoomToAccuracy: false,
    })

    geolocation.getCurrentPosition((status, result) => {
      if (status === 'complete' && result.position) {
        const longitude = getAmapLongitude(result.position)
        const latitude = getAmapLatitude(result.position)
        if (longitude === null || latitude === null) {
          resolve({
            ok: false,
            code: 'unavailable',
            message: '高德定位未返回有效坐标',
            shouldReportFailure: true,
          })
          return
        }

        resolve({
          ok: true,
          longitude,
          latitude,
          accuracy: result.accuracy ?? null,
          address: result.formattedAddress,
          provider: 'amap',
        })
        return
      }

      const message = result.message || result.info || '高德定位失败'
      resolve({
        ok: false,
        code: 'unavailable',
        message,
        shouldReportFailure: true,
      })
    })
  })
}

function getAmapLongitude(position: AMapPosition): number | null {
  return position.lng ?? position.getLng?.() ?? null
}

function getAmapLatitude(position: AMapPosition): number | null {
  return position.lat ?? position.getLat?.() ?? null
}

function getFailureCode(error: unknown): LocationFailureCode {
  if (error && typeof error === 'object' && 'code' in error) {
    const code = Number((error as { code?: unknown }).code)
    if (code === 1) {
      return 'permission_denied'
    }
    if (code === 2) {
      return 'unavailable'
    }
    if (code === 3) {
      return 'timeout'
    }
  }
  return 'unknown'
}
