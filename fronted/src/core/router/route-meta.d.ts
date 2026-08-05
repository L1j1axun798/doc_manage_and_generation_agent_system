import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    description?: string
    requiresAuth?: boolean
    permission?: string
    roles?: string[]
    hideInMenu?: boolean
    activeMenu?: string
    layout?: 'main' | 'public' | 'blank'
  }
}
