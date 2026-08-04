import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import MainLayout from '@/layouts/MainLayout.vue'
import { useAuthStore } from '@/modules/auth'

describe('main layout defaults', () => {
  afterEach(() => {
    window.localStorage.removeItem('wind-doc-system.sidebar-collapsed')
  })

  it('starts with an expanded sidebar even when an old collapsed state exists', async () => {
    window.localStorage.setItem('wind-doc-system.sidebar-collapsed', 'true')

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          component: { template: '<div />' },
          meta: { title: '首页' },
        },
      ],
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.$patch({
      user: {
        id: 1,
        username: 'admin',
        real_name: '管理员',
        employee_no: 'A001',
        role: 'system_admin',
        phone: '',
        email: 'admin@example.com',
        is_active: true,
        must_change_password: false,
        webauthn_enabled: true,
        webauthn_credentials_count: 1,
        created_at: '2026-07-30T00:00:00+08:00',
      },
      status: 'authenticated',
      initialized: true,
    })

    await router.push('/')
    await router.isReady()

    const wrapper = mount(MainLayout, {
      global: {
        plugins: [pinia, router, ElementPlus],
      },
    })

    expect(wrapper.find('.main-layout__aside').classes()).not.toContain('is-collapsed')
    expect(wrapper.find('.main-layout__sidebar-toggle').attributes('aria-pressed')).toBe('false')

    await wrapper.find('.main-layout__sidebar-toggle').trigger('click')

    expect(wrapper.find('.main-layout__aside').classes()).toContain('is-collapsed')
    wrapper.unmount()
  })
})
