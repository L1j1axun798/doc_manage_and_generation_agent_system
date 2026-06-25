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

export interface AppMenuItem {
  index: string
  title: string
  icon: Component
  disabled?: boolean
}

export function buildMainMenu(): AppMenuItem[] {
  return [
    { index: '/dashboard', title: '首页', icon: House },
    { index: '/documents', title: '资料中心', icon: Files, disabled: true },
    { index: '/projects', title: '项目管理', icon: FolderOpened, disabled: true },
    { index: '/access/internal', title: '授权管理', icon: Lock, disabled: true },
    { index: '/users', title: '用户管理', icon: User, disabled: true },
    { index: '/audit', title: '审计中心', icon: Management, disabled: true },
    { index: '/system/status', title: '系统管理', icon: Setting, disabled: true },
    { index: '/notifications', title: '通知中心', icon: Bell, disabled: true },
  ]
}
