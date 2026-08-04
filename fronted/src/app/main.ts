import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@/styles/index.scss'

import { initializeTheme } from '@/shared/composables/useTheme'
import { bootstrap } from './bootstrap'

initializeTheme()
bootstrap()
