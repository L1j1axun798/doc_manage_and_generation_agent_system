import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from '@/core/router'
import { registerElementPlus } from './register-element-plus'

export function bootstrap(selector = '#app') {
  const app = createApp(App)
  const pinia = createPinia()

  registerElementPlus(app)
  app.use(pinia)
  app.use(router)
  app.mount(selector)

  return { app, pinia, router }
}
