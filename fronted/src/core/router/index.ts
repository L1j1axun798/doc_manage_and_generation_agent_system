import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'
import PublicLayout from '@/layouts/PublicLayout.vue'
import { installRouterGuards } from './guards'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/modules/auth/pages/LoginPage.vue'),
    meta: {
      title: '登录',
      layout: 'blank',
    },
  },
  {
    path: '/webauthn/register',
    name: 'webauthn-register',
    component: () => import('@/modules/auth/pages/WebAuthnRegisterPage.vue'),
    meta: {
      title: '绑定本人验证设备',
      layout: 'blank',
    },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    meta: {
      title: '主框架',
      requiresAuth: true,
      layout: 'main',
    },
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/modules/dashboard/pages/DashboardPage.vue'),
        meta: {
          title: '首页',
          requiresAuth: true,
          layout: 'main',
        },
      },
      {
        path: 'documents',
        name: 'documents',
        component: () => import('@/modules/documents/pages/DocumentCenterPage.vue'),
        meta: {
          title: '资料中心',
          requiresAuth: true,
          layout: 'main',
        },
      },
      {
        path: 'documents/recycle-bin',
        name: 'documents-recycle-bin',
        component: () => import('@/modules/documents/pages/RecycleBinPage.vue'),
        meta: {
          title: '回收站',
          description: '查看已删除资料，并按后端权限恢复。',
          requiresAuth: true,
          activeMenu: '/documents',
          layout: 'main',
        },
      },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('@/modules/projects/pages/ProjectListPage.vue'),
        meta: {
          title: '项目管理',
          description: '查询当前账号可见项目，并进入项目详情维护成员和资料。',
          requiresAuth: true,
          layout: 'main',
        },
      },
      {
        path: 'projects/:projectId',
        name: 'project-detail',
        component: () => import('@/modules/projects/pages/ProjectDetailPage.vue'),
        meta: {
          title: '项目详情',
          requiresAuth: true,
          activeMenu: '/projects',
          layout: 'main',
        },
      },
      {
        path: 'document-generation',
        name: 'document-generation',
        component: () => import('@/modules/document-generation/pages/DocumentGenerationPage.vue'),
        meta: {
          title: '入场资料Agent V1.0',
          description: '在一个会话内完成模板、人员、资料、生成、修改与审核。',
          requiresAuth: true,
          layout: 'main',
        },
      },
      {
        path: 'access/internal',
        name: 'access-management',
        component: () => import('@/modules/access/pages/AccessManagementPage.vue'),
        meta: {
          title: '授权管理',
          description: '查询可管理范围内的文档授权和临时访问授权。',
          requiresAuth: true,
          layout: 'main',
          roles: ['system_admin', 'project_manager'],
        },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/modules/users/pages/UserManagementPage.vue'),
        meta: {
          title: '用户管理',
          description: '维护系统账号、角色、状态和首次登录改密要求。',
          requiresAuth: true,
          layout: 'main',
          roles: ['system_admin'],
        },
      },
      {
        path: 'audit',
        name: 'audit',
        component: () => import('@/modules/audit/pages/AuditLogPage.vue'),
        meta: {
          title: '审计中心',
          description: '查询系统关键操作、权限拒绝、下载和授权记录。',
          requiresAuth: true,
          layout: 'main',
          roles: ['system_admin'],
        },
      },
      {
        path: 'locations/admin',
        name: 'admin-locations',
        component: () => import('@/modules/locations/pages/AdminLocationPage.vue'),
        meta: {
          title: '人员位置',
          description: '查看员工最近一次上报位置，所有位置均以员工主动上报时间为准。',
          requiresAuth: true,
          layout: 'main',
          roles: ['system_admin'],
        },
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: () => import('@/modules/notifications/pages/NotificationCenterPage.vue'),
        meta: {
          title: '通知中心',
          description: '查看系统、文档和授权相关通知，并维护单条通知的已读状态。',
          requiresAuth: true,
          layout: 'main',
        },
      },
      {
        path: 'system/status',
        name: 'system-management',
        component: () => import('@/modules/system/pages/SystemManagementPage.vue'),
        meta: {
          title: '系统管理',
          description: '维护资料目录，查看后端健康状态；未开放的系统能力保持只读提示。',
          requiresAuth: true,
          layout: 'main',
          roles: ['system_admin'],
        },
      },
      {
        path: 'change-password',
        name: 'change-password',
        component: () => import('@/modules/auth/pages/ChangePasswordPage.vue'),
        meta: {
          title: '修改密码',
          description: '首次登录或重置密码后，需要先更新密码。',
          requiresAuth: true,
          hideInMenu: true,
          layout: 'main',
        },
      },
    ],
  },
  {
    path: '/',
    component: PublicLayout,
    children: [
      {
        path: 'share',
        name: 'temporary-download',
        component: () => import('@/modules/access/pages/TemporaryDownloadPage.vue'),
        meta: {
          title: '临时文件下载',
          layout: 'public',
        },
      },
      {
        path: '403',
        name: 'access-denied',
        component: () => import('@/modules/errors/pages/AccessDeniedPage.vue'),
        meta: {
          title: '无权限',
          layout: 'public',
        },
      },
      {
        path: '500',
        name: 'server-error',
        component: () => import('@/modules/errors/pages/ServerErrorPage.vue'),
        meta: {
          title: '系统异常',
          layout: 'public',
        },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/modules/errors/pages/NotFoundPage.vue'),
    meta: {
      title: '页面不存在',
      layout: 'public',
    },
  },
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

installRouterGuards(router)
