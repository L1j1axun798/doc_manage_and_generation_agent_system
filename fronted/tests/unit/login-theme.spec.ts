import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import LoginPage from '@/modules/auth/pages/LoginPage.vue'
import { setTheme } from '@/shared/composables/useTheme'

describe('login theme default', () => {
  afterEach(() => {
    setTheme('light')
    window.localStorage.removeItem('wind-doc-system.theme')
    document.documentElement.classList.remove('dark', 'theme-is-switching')
  })

  it('resets the login flow to the light theme', async () => {
    setTheme('dark')

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/login', component: LoginPage }],
    })
    const pinia = createPinia()
    setActivePinia(pinia)

    await router.push('/login')
    await router.isReady()

    const wrapper = mount(LoginPage, {
      global: {
        plugins: [pinia, router, ElementPlus],
      },
    })

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(window.localStorage.getItem('wind-doc-system.theme')).toBe('light')
    expect(wrapper.find('.login-page__brand-mark').attributes('src')).toBe('/brand-logo.png')
    wrapper.unmount()
  })
})
