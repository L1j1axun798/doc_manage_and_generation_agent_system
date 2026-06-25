import { apiClient } from '@/core/http/client'
import type {
  AuthUser,
  ChangePasswordPayload,
  CsrfResponse,
  LoginPayload,
} from '../auth.types'

export async function fetchCsrfToken(): Promise<CsrfResponse> {
  const response = await apiClient.get<CsrfResponse>('/auth/csrf/')
  return response.data
}

export async function login(payload: LoginPayload): Promise<AuthUser> {
  const response = await apiClient.post<AuthUser>('/auth/login/', payload)
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
