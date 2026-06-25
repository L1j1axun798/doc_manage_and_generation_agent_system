import type { Router } from 'vue-router'

import { appConfig } from '@/config/app'

export function installRouterGuards(router: Router): void {
  router.beforeEach((to) => {
    const title = typeof to.meta.title === 'string' ? to.meta.title : ''
    document.title = title ? `${title} - ${appConfig.title}` : appConfig.title
    return true
  })
}
