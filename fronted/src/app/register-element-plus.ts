import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import type { App } from 'vue'

export function registerElementPlus(app: App) {
  app.use(ElementPlus, {
    locale: zhCn,
  })
}
