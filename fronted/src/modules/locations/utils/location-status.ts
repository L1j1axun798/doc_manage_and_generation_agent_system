import type { LocationSnapshot, LocationStatus } from '../locations.types'

export const LOCATION_STATUS_LABELS: Record<LocationStatus, string> = {
  normal: '正常',
  expired: '已过期',
  today_unreported: '今日未上报',
  locate_failed: '定位失败',
}

export const LOCATION_STATUS_TAG_TYPES: Record<LocationStatus, 'success' | 'warning' | 'info' | 'danger'> = {
  normal: 'success',
  expired: 'warning',
  today_unreported: 'info',
  locate_failed: 'danger',
}

export function getLocationStatusLabel(status: LocationStatus): string {
  return LOCATION_STATUS_LABELS[status]
}

export function getLocationStatusTagType(status: LocationStatus): 'success' | 'warning' | 'info' | 'danger' {
  return LOCATION_STATUS_TAG_TYPES[status]
}

export function hasUsableCoordinates(snapshot: LocationSnapshot): boolean {
  const report = snapshot.latest_report
  return Boolean(report?.longitude && report.latitude && report.report_status === 'success')
}

export function getAttentionLocations(snapshots: LocationSnapshot[]): LocationSnapshot[] {
  return snapshots.filter((snapshot) => snapshot.location_status !== 'normal')
}

export function getLocationDisplayAddress(snapshot: LocationSnapshot): string {
  const report = snapshot.latest_report
  if (!report) {
    return '-'
  }

  if (report.address) {
    return report.address
  }

  if (report.longitude && report.latitude) {
    return `${report.longitude}, ${report.latitude}`
  }

  return report.failure_reason || '-'
}

export function hasAmapConfig(key: string): boolean {
  return key.trim().length > 0
}
