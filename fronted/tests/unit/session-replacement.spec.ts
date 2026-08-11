import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'

import App from '@/app/App.vue'
import { notifySessionReplaced } from '@/core/http/session-events'
import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'

const user: AuthUser = {
  id: 1,
  username: 'operator',
  real_name: 'Operator',
  employee_no: null,
  role: 'data_operator',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: false,
  webauthn_credentials_count: 0,
  created_at: '2026-08-11T00:00:00+08:00',
}

afterEach(() => {
  vi.restoreAllMocks()
})

it('shows a forced logout alert and redirects when the session is replaced', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: { template: '<div>Login</div>' } },
      { path: '/dashboard', name: 'dashboard', component: { template: '<div>Dashboard</div>' } },
    ],
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.$patch({
    user,
    status: 'authenticated',
    initialized: true,
  })
  const alert = vi.spyOn(ElMessageBox, 'alert').mockResolvedValue('confirm')

  await router.push('/dashboard')
  await router.isReady()
  const wrapper = mount(App, {
    global: {
      plugins: [pinia, router, ElementPlus],
    },
  })

  notifySessionReplaced()
  await flushPromises()

  expect(alert).toHaveBeenCalledWith(
    '您的账号已在其他设备或浏览器重新登录，当前登录已下线。',
    '账号已下线',
    expect.objectContaining({
      confirmButtonText: '重新登录',
      showClose: false,
    }),
  )
  expect(authStore.isAuthenticated).toBe(false)
  expect(router.currentRoute.value.name).toBe('login')
  expect(router.currentRoute.value.query.reason).toBe('session_replaced')
  wrapper.unmount()
})
