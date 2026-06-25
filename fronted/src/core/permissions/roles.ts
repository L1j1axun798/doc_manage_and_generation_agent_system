import type { UserRole } from '@/modules/auth'

export const ROLE_LABELS: Record<UserRole, string> = {
  system_admin: '系统管理员',
  project_manager: '项目负责人',
  data_operator: '资料整理员',
}

export function getRoleLabel(role: UserRole): string {
  return ROLE_LABELS[role]
}
