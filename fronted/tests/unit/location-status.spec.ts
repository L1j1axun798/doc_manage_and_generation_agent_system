import { describe, expect, it } from 'vitest'

import type { LocationSnapshot } from '@/modules/locations'
import {
  getAttentionLocations,
  getLocationDisplayAddress,
  getLocationStatusLabel,
  hasAmapConfig,
  hasUsableCoordinates,
} from '@/modules/locations/utils/location-status'

function makeSnapshot(
  status: LocationSnapshot['location_status'],
  overrides: Partial<LocationSnapshot> = {},
): LocationSnapshot {
  return {
    user: {
      id: 1,
      username: 'operator',
      real_name: '资料员',
      employee_no: null,
      role: 'data_operator',
      phone: '',
    },
    latest_report: {
      id: 1,
      longitude: '116.397128',
      latitude: '39.916527',
      accuracy: '20.00',
      address: '',
      report_status: 'success',
      failure_reason: '',
      reported_at: '2026-07-02T10:00:00+08:00',
      created_at: '2026-07-02T10:00:00+08:00',
    },
    location_status: status,
    should_report: status !== 'normal',
    ...overrides,
  }
}

describe('location status helpers', () => {
  it('formats status labels and attention rows', () => {
    const rows = [
      makeSnapshot('normal'),
      makeSnapshot('expired', { user: { ...makeSnapshot('expired').user, id: 2 } }),
      makeSnapshot('today_unreported', { user: { ...makeSnapshot('today_unreported').user, id: 3 } }),
      makeSnapshot('locate_failed', { user: { ...makeSnapshot('locate_failed').user, id: 4 } }),
    ]

    expect(getLocationStatusLabel('normal')).toBe('正常')
    expect(getLocationStatusLabel('expired')).toBe('已过期')
    expect(getAttentionLocations(rows).map((row) => row.location_status)).toEqual([
      'expired',
      'today_unreported',
      'locate_failed',
    ])
  })

  it('uses address, coordinates, failure reason, or fallback for display', () => {
    expect(
      getLocationDisplayAddress(
        makeSnapshot('normal', {
          latest_report: { ...makeSnapshot('normal').latest_report!, address: '北京市东城区' },
        }),
      ),
    ).toBe('北京市东城区')
    expect(getLocationDisplayAddress(makeSnapshot('normal'))).toBe('116.397128, 39.916527')
    expect(
      getLocationDisplayAddress(
        makeSnapshot('locate_failed', {
          latest_report: {
            ...makeSnapshot('normal').latest_report!,
            longitude: null,
            latitude: null,
            report_status: 'locate_failed',
            failure_reason: '用户拒绝定位授权',
          },
        }),
      ),
    ).toBe('用户拒绝定位授权')
    expect(getLocationDisplayAddress(makeSnapshot('today_unreported', { latest_report: null }))).toBe('-')
  })

  it('detects usable map coordinates and map configuration', () => {
    expect(hasUsableCoordinates(makeSnapshot('normal'))).toBe(true)
    expect(
      hasUsableCoordinates(
        makeSnapshot('locate_failed', {
          latest_report: {
            ...makeSnapshot('normal').latest_report!,
            report_status: 'locate_failed',
          },
        }),
      ),
    ).toBe(false)
    expect(hasAmapConfig('')).toBe(false)
    expect(hasAmapConfig('  test-key  ')).toBe(true)
  })
})
