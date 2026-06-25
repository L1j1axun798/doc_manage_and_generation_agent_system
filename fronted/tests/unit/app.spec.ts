import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/app/App.vue'
import { routes } from '@/core/router'

it('mounts the dashboard route', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })

  await router.push('/')
  await router.isReady()

  const wrapper = mount(App, {
    global: {
      plugins: [router, createPinia(), ElementPlus],
    },
  })

  expect(wrapper.text()).toContain('风电资料系统')
  expect(wrapper.text()).toContain('首页')
})
