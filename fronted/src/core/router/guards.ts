import type { Router } from 'vue-router'

import { appConfig } from '@/config/app'
import { useAuthStore } from '@/modules/auth'

export function installRouterGuards(router: Router): void {
  router.beforeEach(async (to) => {
    const title = typeof to.meta.title === 'string' ? to.meta.title : ''
    document.title = title ? `${title} - ${appConfig.title}` : appConfig.title

    const authStore = useAuthStore()

    if (to.meta.requiresAuth) {
      try {
        await authStore.initializeSession()
      } catch {
        return {
          path: '/500',
          query: {
            redirect: to.fullPath,
          },
        }
      }

      if (!authStore.isAuthenticated) {
        return {
          path: '/login',
          query: {
            redirect: to.fullPath,
          },
        }
      }

      if (
        authStore.user?.must_change_password
        && to.name !== 'change-password'
      ) {
        return {
          path: '/change-password',
          query: {
            redirect: to.fullPath,
          },
        }
      }

      const allowedRoles = to.meta.roles
      if (allowedRoles && authStore.user && !allowedRoles.includes(authStore.user.role)) {
        return {
          path: '/403',
        }
      }
    }

    if (to.name === 'login') {
      await authStore.initializeSession()

      if (authStore.isAuthenticated) {
        return authStore.user?.must_change_password ? '/change-password' : '/dashboard'
      }
    }

    return true
  })
}
