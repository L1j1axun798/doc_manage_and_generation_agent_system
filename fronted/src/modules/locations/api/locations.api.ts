import { apiClient } from '@/core/http/client'
import type {
  LocationReport,
  LocationReportChallenge,
  LocationReportPayload,
  LocationSnapshot,
} from '../locations.types'

export async function createLocationReportChallenge(
  payload: LocationReportPayload,
): Promise<LocationReportChallenge> {
  const response = await apiClient.post<LocationReportChallenge>(
    '/locations/report/challenge/',
    payload,
  )
  return response.data
}

export async function reportLocation(payload: LocationReportPayload): Promise<LocationReport> {
  const response = await apiClient.post<LocationReport>('/locations/report/', payload)
  return response.data
}

export async function fetchMyLatestLocation(): Promise<LocationSnapshot> {
  const response = await apiClient.get<LocationSnapshot>('/locations/me/latest/')
  return response.data
}

export async function fetchAdminLatestLocations(): Promise<LocationSnapshot[]> {
  const response = await apiClient.get<LocationSnapshot[]>('/locations/admin/latest/')
  return response.data
}
