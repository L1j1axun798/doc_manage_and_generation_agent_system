import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'
import { installRouterGuards } from './guards'

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/modules/dashboard/pages/DashboardPage.vue'),
        meta: {
          title: '首页',
          layout: 'main',
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
