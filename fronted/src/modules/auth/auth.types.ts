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
