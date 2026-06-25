import {
  Bell,
  Files,
  FolderOpened,
  House,
  Lock,
  Management,
  Setting,
  User,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'

import type { UserRole } from '@/modules/auth'

export interface AppMenuItem {
  index: string
  title: string
  icon: Component
  disabled?: boolean
  roles: UserRole[]
}

const ALL_ROLES: UserRole[] = ['system_admin', 'project_manager', 'data_operator']

const MENU_ITEMS: AppMenuItem[] = [
  { index: '/dashboard', title: '首页', icon: House, roles: ALL_ROLES },
  { index: '/documents', title: '资料中心', icon: Files, roles: ALL_ROLES },
  {
    index: '/projects',
    title: '项目管理',
    icon: FolderOpened,
    roles: ALL_ROLES,
  },
  {
    index: '/access/internal',
    title: '授权管理',
    icon: Lock,
    roles: ['system_admin', 'project_manager'],
  },
  { index: '/users', title: '用户管理', icon: User, roles: ['system_admin'] },
  { index: '/audit', title: '审计中心', icon: Management, roles: ['system_admin'] },
  { index: '/system/status', title: '系统管理', icon: Setting, roles: ['system_admin'] },
  { index: '/notifications', title: '通知中心', icon: Bell, roles: ALL_ROLES },
]

export function buildMainMenu(role: UserRole | undefined): AppMenuItem[] {
  if (!role) {
    return []
  }

  return MENU_ITEMS.filter((item) => item.roles.includes(role))
}
