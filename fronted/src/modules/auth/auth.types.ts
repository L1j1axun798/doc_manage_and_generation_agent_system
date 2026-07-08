import type {
  AuthenticationResponseJSON,
  PublicKeyCredentialCreationOptionsJSON,
  PublicKeyCredentialRequestOptionsJSON,
  RegistrationResponseJSON,
} from '@simplewebauthn/browser'

export type UserRole = 'system_admin' | 'project_manager' | 'data_operator' | 'temporary_user'

export interface AuthUser {
  id: number
  username: string
  real_name: string
  employee_no: string | null
  role: UserRole
  phone: string
  email: string
  is_active: boolean
  must_change_password: boolean
  webauthn_enabled: boolean
  webauthn_credentials_count: number
  created_at: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

export interface CsrfResponse {
  csrfToken: string
}

export interface LoginChallengeResponse {
  status: 'webauthn_required'
  pending_token: string
  options: PublicKeyCredentialRequestOptionsJSON
}

export interface WebAuthnLoginVerifyPayload {
  pending_token: string
  credential: AuthenticationResponseJSON
}

export interface WebAuthnEnrollmentTicket {
  token: string
  expires_at: string
  user: AuthUser
}

export interface WebAuthnRegisterOptionsPayload {
  ticket: string
  device_name?: string
}

export interface WebAuthnRegisterOptionsResponse {
  challenge_token: string
  options: PublicKeyCredentialCreationOptionsJSON
}

export interface WebAuthnRegisterVerifyPayload {
  ticket: string
  challenge_token: string
  credential: RegistrationResponseJSON
}

export interface WebAuthnCredential {
  id: number
  name: string
  credential_id: string
  transports: string[]
  device_type: string
  backed_up: boolean
  created_at: string
  last_used_at: string | null
}
