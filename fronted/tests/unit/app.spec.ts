import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/app/App.vue'
import { routes } from '@/core/router'

it('mounts the dashboard route', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })
  const pinia = createPinia()
  setActivePinia(pinia)

  await router.push('/login')
  await router.isReady()

  const wrapper = mount(App, {
    global: {
      plugins: [pinia, router, ElementPlus],
    },
  })

  expect(wrapper.text()).toContain('风电资料系统')
  expect(wrapper.text()).toContain('登录')
})
