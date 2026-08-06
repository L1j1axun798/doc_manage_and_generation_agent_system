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
          meta: {
            title: '四措两案 Agent V1.0',
            description: '在一个会话内完成模板、人员、资料、生成、修改与审核。',
          },
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
    expect(wrapper.find('.main-layout__brand-mark').attributes('src')).toBe('/brand-logo.png')
    expect(wrapper.find('.main-layout__sidebar-toggle').attributes('aria-pressed')).toBe('false')
    expect(wrapper.find('.main-layout__page-context strong').text()).toBe('四措两案 Agent V1.0')
    expect(wrapper.find('.main-layout__page-description').text()).toBe(
      '在一个会话内完成模板、人员、资料、生成、修改与审核。',
    )

    await wrapper.find('.main-layout__sidebar-toggle').trigger('click')

    expect(wrapper.find('.main-layout__aside').classes()).toContain('is-collapsed')
    wrapper.unmount()
  })

  it('highlights the document agent and replaces repeated click bursts', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/document-generation', component: { template: '<div />' } },
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
    const agentItem = wrapper.find('.el-menu-item.is-featured-agent')

    expect(agentItem.text()).toContain('四措两案Agent V1.0')
    expect(agentItem.find('.main-layout__featured-badge').text()).toBe('🎉')

    const hitTarget = agentItem.find('.main-layout__menu-hit-target')
    hitTarget.element.dispatchEvent(
      new MouseEvent('click', { bubbles: true, clientX: 40, clientY: 24, detail: 1 }),
    )
    await wrapper.vm.$nextTick()
    const firstBurstId = agentItem.find('.main-layout__menu-burst').attributes('data-burst-id')
    expect(agentItem.findAll('.main-layout__menu-burst')).toHaveLength(1)
    expect(agentItem.findAll('.main-layout__menu-burst-particle')).toHaveLength(12)

    hitTarget.element.dispatchEvent(
      new MouseEvent('click', { bubbles: true, clientX: 64, clientY: 28, detail: 1 }),
    )
    await wrapper.vm.$nextTick()
    expect(agentItem.findAll('.main-layout__menu-burst')).toHaveLength(1)
    expect(agentItem.findAll('.main-layout__menu-burst-particle')).toHaveLength(12)
    expect(agentItem.find('.main-layout__menu-burst').attributes('data-burst-id')).not.toBe(firstBurstId)

    wrapper.unmount()
  })
})
