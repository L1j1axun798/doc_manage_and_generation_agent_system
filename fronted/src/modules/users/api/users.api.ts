import { apiClient } from '@/core/http/client'
import type { ApiPage } from '@/shared/types/api.types'
import type {
  ResetPasswordPayload,
  ResetPasswordResponse,
  SystemUser,
  UserCreatePayload,
  UserListQuery,
  UserPayload,
  WebAuthnResetResponse,
} from '../users.types'

export async function fetchUsers(query: UserListQuery): Promise<ApiPage<SystemUser>> {
  const response = await apiClient.get<ApiPage<SystemUser>>('/users/', {
    params: cleanQuery(query),
  })
  return response.data
}

export async function fetchUser(userId: number): Promise<SystemUser> {
  const response = await apiClient.get<SystemUser>(`/users/${userId}/`)
  return response.data
}

export async function createUser(payload: UserCreatePayload): Promise<SystemUser> {
  const response = await apiClient.post<SystemUser>('/users/', payload)
  return response.data
}

export async function updateUser(userId: number, payload: Partial<UserPayload>): Promise<SystemUser> {
  const response = await apiClient.patch<SystemUser>(`/users/${userId}/`, payload)
  return response.data
}

export async function disableUser(userId: number): Promise<void> {
  await apiClient.post(`/users/${userId}/disable/`)
}

export async function resetUserPassword(
  userId: number,
  payload: ResetPasswordPayload,
): Promise<ResetPasswordResponse> {
  const response = await apiClient.post<ResetPasswordResponse>(
    `/users/${userId}/reset-password/`,
    payload,
  )
  return response.data
}

export async function resetUserWebAuthn(userId: number): Promise<WebAuthnResetResponse> {
  const response = await apiClient.post<WebAuthnResetResponse>(`/users/${userId}/webauthn-reset/`)
  return response.data
}

function cleanQuery(query: UserListQuery): UserListQuery {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  )
}
