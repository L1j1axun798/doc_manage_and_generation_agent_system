import { apiClient } from '@/core/http/client'
import type {
  AuthUser,
  ChangePasswordPayload,
  CsrfResponse,
  LoginChallengeResponse,
  LoginPayload,
  WebAuthnCredential,
  WebAuthnEnrollmentTicket,
  WebAuthnLoginVerifyPayload,
  WebAuthnRegisterOptionsPayload,
  WebAuthnRegisterOptionsResponse,
  WebAuthnRegisterVerifyPayload,
} from '../auth.types'

export async function fetchCsrfToken(): Promise<CsrfResponse> {
  const response = await apiClient.get<CsrfResponse>('/auth/csrf/')
  return response.data
}

export async function login(payload: LoginPayload): Promise<LoginChallengeResponse> {
  const response = await apiClient.post<LoginChallengeResponse>('/auth/login/', payload)
  return response.data
}

export async function verifyWebAuthnLogin(
  payload: WebAuthnLoginVerifyPayload,
): Promise<AuthUser> {
  const response = await apiClient.post<AuthUser>('/auth/webauthn/login/verify/', payload)
  return response.data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout/')
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const response = await apiClient.get<AuthUser>('/auth/me/')
  return response.data
}

export async function changePassword(payload: ChangePasswordPayload): Promise<void> {
  await apiClient.post('/auth/change-password/', payload)
}

export async function createWebAuthnEnrollmentTicket(
  userId: number,
): Promise<WebAuthnEnrollmentTicket> {
  const response = await apiClient.post<WebAuthnEnrollmentTicket>(
    '/auth/webauthn/enrollment-tickets/',
    { user: userId },
  )
  return response.data
}

export async function beginWebAuthnRegistration(
  payload: WebAuthnRegisterOptionsPayload,
): Promise<WebAuthnRegisterOptionsResponse> {
  const response = await apiClient.post<WebAuthnRegisterOptionsResponse>(
    '/auth/webauthn/register/options/',
    payload,
  )
  return response.data
}

export async function verifyWebAuthnRegistration(
  payload: WebAuthnRegisterVerifyPayload,
): Promise<WebAuthnCredential> {
  const response = await apiClient.post<WebAuthnCredential>(
    '/auth/webauthn/register/verify/',
    payload,
  )
  return response.data
}

export async function fetchWebAuthnCredentials(): Promise<WebAuthnCredential[]> {
  const response = await apiClient.get<WebAuthnCredential[]>('/auth/webauthn/credentials/')
  return response.data
}

export async function revokeWebAuthnCredential(credentialId: number): Promise<void> {
  await apiClient.delete(`/auth/webauthn/credentials/${credentialId}/`)
}
