import type { UserRole } from '@/modules/auth'

export interface SystemUser {
  id: number
  username: string
  real_name: string
  employee_no: string | null
  role: UserRole
  phone: string
  email: string
  is_active: boolean
  must_change_password: boolean
  created_at: string
}

export interface UserListQuery {
  page?: number
  search?: string
  ordering?: string
}

export interface UserPayload {
  username: string
  real_name: string
  employee_no: string | null
  role: UserRole
  phone: string
  email: string
  is_active: boolean
  must_change_password: boolean
}

export interface UserCreatePayload extends UserPayload {
  password: string
}

export interface ResetPasswordPayload {
  new_password?: string
}

export interface ResetPasswordResponse {
  temporary_password: string
  must_change_password: boolean
}
