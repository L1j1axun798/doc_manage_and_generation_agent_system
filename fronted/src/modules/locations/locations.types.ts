import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialRequestOptionsJSON,
} from '@simplewebauthn/browser'

export type LocationReportStatus = 'success' | 'locate_failed'

export type LocationStatus = 'normal' | 'expired' | 'today_unreported' | 'locate_failed'

export interface LocationReport {
  id: number
  longitude: string | null
  latitude: string | null
  accuracy: string | null
  address: string
  report_status: LocationReportStatus
  failure_reason: string
  reported_at: string
  created_at: string
}

export interface LocationUser {
  id: number
  username: string
  real_name: string
  employee_no: string | null
  role: string
  phone: string
}

export interface LocationSnapshot {
  user: LocationUser
  latest_report: LocationReport | null
  location_status: LocationStatus
  should_report: boolean
}

export interface LocationReportPayload {
  longitude?: number
  latitude?: number
  accuracy?: number | null
  address?: string
  report_status?: LocationReportStatus
  failure_reason?: string
  webauthn?: LocationReportWebAuthnPayload
}

export interface LocationReportWebAuthnPayload {
  challenge_token: string
  credential: AuthenticationResponseJSON
}

export interface LocationReportWebAuthnChallenge {
  status: 'webauthn_required'
  token: string
  options: PublicKeyCredentialRequestOptionsJSON
}

export interface LocationReportVerificationNotRequired {
  status: 'not_required'
}

export type LocationReportChallenge =
  | LocationReportWebAuthnChallenge
  | LocationReportVerificationNotRequired
