import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import type { App } from 'vue'

export function registerElementPlus(app: App) {
  app.use(ElementPlus, {
    locale: zhCn,
  })
}
