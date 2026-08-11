<script setup lang="ts">
import {
  ArrowDown,
  Expand,
  Fold,
  Key,
  Moon,
  Search,
  Sunny,
  SwitchButton,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appConfig } from '@/config/app'
import { getRoleLabel } from '@/core/permissions/roles'
import { buildMainMenu } from '@/core/router/menu-builder'
import { useAuthStore } from '@/modules/auth'
import SiteFooter from '@/shared/components/SiteFooter.vue'
import { useTheme } from '@/shared/composables/useTheme'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, toggleTheme } = useTheme()
const globalSearch = ref('')
const sidebarCollapsed = ref(false)
const compactViewport = ref(false)
let compactViewportQuery: MediaQueryList | null = null

interface MenuBurstParticle {
  id: number
  color: string
  delay: number
  translateX: number
  translateY: number
}

interface MenuBurst {
  id: number
  originX: number
  originY: number
  particles: MenuBurstParticle[]
}

const FEATURED_MENU_INDEX = '/document-generation'
const MENU_BURST_PARTICLE_COUNT = 12
const MENU_BURST_COLORS = [
  'var(--color-menu-burst-primary)',
  'var(--color-menu-burst-secondary)',
  'var(--color-menu-burst-highlight)',
  'var(--color-menu-burst-tertiary)',
]
const menuBursts = ref<Record<string, MenuBurst>>({})
const burstCleanupTimers = new Map<string, number>()
let menuBurstId = 0

const menuItems = computed(() => buildMainMenu(authStore.user?.role))
const activeMenu = computed(() => String(route.meta.activeMenu || route.path))
const currentPageTitle = computed(() => String(route.meta.title || appConfig.title))
const currentPageDescription = computed(() => {
  const description = route.meta.description
  return typeof description === 'string' ? description : ''
})
const username = computed(() => authStore.user?.real_name || authStore.user?.username || '-')
const accountName = computed(() => authStore.user?.username || '-')
const roleLabel = computed(() => (authStore.user ? getRoleLabel(authStore.user.role) : ''))
const canUseGlobalSearch = computed(() => authStore.user?.role !== 'temporary_user')
const avatarInitial = computed(() => {
  const source = authStore.user?.real_name?.trim() || authStore.user?.username?.trim() || ''
  return source.slice(0, 1).toUpperCase() || '-'
})
const isSidebarCollapsed = computed(() => sidebarCollapsed.value || compactViewport.value)
const asideWidth = computed(() =>
  isSidebarCollapsed.value ? 'var(--sidebar-width-collapsed)' : 'var(--sidebar-width)',
)
const themeToggleLabel = computed(() => (isDarkTheme.value ? '切换浅色模式' : '切换深色模式'))
const sidebarToggleLabel = computed(() => (sidebarCollapsed.value ? '展开侧边栏' : '收起侧边栏'))

onMounted(() => {
  if (typeof window.matchMedia !== 'function') {
    return
  }

  compactViewportQuery = window.matchMedia('(max-width: 900px)')
  syncCompactViewport(compactViewportQuery)
  compactViewportQuery.addEventListener('change', syncCompactViewport)
})

onBeforeUnmount(() => {
  compactViewportQuery?.removeEventListener('change', syncCompactViewport)
  burstCleanupTimers.forEach((timer) => window.clearTimeout(timer))
  burstCleanupTimers.clear()
})

function syncCompactViewport(event: MediaQueryList | MediaQueryListEvent): void {
  compactViewport.value = event.matches
}

function toggleSidebar(): void {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function handleMenuSelect(index: string): void {
  void router.push(index)
}

function clearMenuBurst(index: string): void {
  const cleanupTimer = burstCleanupTimers.get(index)
  if (cleanupTimer !== undefined) {
    window.clearTimeout(cleanupTimer)
    burstCleanupTimers.delete(index)
  }

  if (menuBursts.value[index]) {
    const remainingBursts = { ...menuBursts.value }
    delete remainingBursts[index]
    menuBursts.value = remainingBursts
  }
}

function createMenuParticles(): MenuBurstParticle[] {
  return Array.from({ length: MENU_BURST_PARTICLE_COUNT }, (_, index) => {
    const angle = (index * Math.PI * 2) / MENU_BURST_PARTICLE_COUNT + (Math.random() * 0.4 - 0.2)
    const distance = 22 + Math.random() * 20

    return {
      id: index,
      color: MENU_BURST_COLORS[index % MENU_BURST_COLORS.length],
      delay: Math.random() * 0.05,
      translateX: Math.cos(angle) * distance,
      translateY: Math.sin(angle) * distance,
    }
  })
}

function handleMenuClick(
  event: MouseEvent | KeyboardEvent,
  index: string,
  disabled = false,
): void {
  const menuItem = event.currentTarget as HTMLElement | null
  if (!menuItem || disabled) {
    return
  }

  clearMenuBurst(index)

  const bounds = menuItem.getBoundingClientRect()
  const isPointerActivation = event instanceof MouseEvent && event.detail !== 0
  const originX = isPointerActivation ? event.clientX - bounds.left : bounds.width / 2
  const originY = isPointerActivation ? event.clientY - bounds.top : bounds.height / 2
  const burst: MenuBurst = {
    id: ++menuBurstId,
    originX,
    originY,
    particles: createMenuParticles(),
  }

  menuBursts.value = {
    ...menuBursts.value,
    [index]: burst,
  }
  burstCleanupTimers.set(
    index,
    window.setTimeout(() => {
      clearMenuBurst(index)
    }, 700),
  )
}

function submitGlobalSearch(): void {
  const keyword = globalSearch.value.trim()
  if (!keyword) {
    return
  }

  void router.push({
    path: '/documents',
    query: {
      search: keyword,
    },
  })
}

async function handleCommand(command: string): Promise<void> {
  if (command === 'change-password') {
    await router.push('/change-password')
    return
  }

  if (command === 'logout') {
    try {
      await authStore.logout()
    } finally {
      await router.replace('/login')
    }
  }
}
</script>

<template>
  <el-container class="main-layout">
    <el-aside
      class="main-layout__aside"
      :class="{ 'is-collapsed': isSidebarCollapsed }"
      :width="asideWidth"
    >
      <svg
        class="main-layout__menu-filter"
        width="0"
        height="0"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <filter
            id="sidebar-menu-gooey"
            x="-30%"
            y="-70%"
            width="160%"
            height="240%"
            color-interpolation-filters="sRGB"
          >
            <feGaussianBlur in="SourceGraphic" stdDeviation="7" result="blur" />
            <feColorMatrix
              in="blur"
              mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9"
              result="goo"
            />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
        </defs>
      </svg>

      <div class="main-layout__brand">
        <img
          class="main-layout__brand-mark"
          :src="appConfig.logoUrl"
          alt=""
          aria-hidden="true"
        />
        <span v-show="!isSidebarCollapsed" class="main-layout__brand-copy">
          <strong class="main-layout__brand-title">{{ appConfig.title }}</strong>
          <small>企业资料工作台</small>
        </span>
      </div>

      <nav class="main-layout__navigation" aria-label="主导航">
        <!-- <p v-show="!isSidebarCollapsed" class="main-layout__menu-label">工作台</p> -->
        <el-menu
          class="main-layout__menu"
          :collapse="isSidebarCollapsed"
          :collapse-transition="false"
          :default-active="activeMenu"
          @select="handleMenuSelect"
        >
          <el-menu-item
            v-for="item in menuItems"
            :key="item.index"
            :index="item.index"
            :disabled="item.disabled"
            :class="{ 'is-featured-agent': item.index === FEATURED_MENU_INDEX }"
            @keydown.enter.space="handleMenuClick($event, item.index, item.disabled)"
          >
            <span
              class="main-layout__menu-hit-target"
              aria-hidden="true"
              @click="handleMenuClick($event, item.index, item.disabled)"
            ></span>
            <span class="main-layout__menu-liquid" aria-hidden="true">
              <span class="main-layout__menu-liquid-bg"></span>
              <span class="main-layout__menu-droplet is-first"></span>
              <span class="main-layout__menu-droplet is-second"></span>
              <span class="main-layout__menu-droplet is-third"></span>
            </span>

            <el-icon class="main-layout__menu-icon">
              <component :is="item.icon" />
            </el-icon>
            <template #title>
              <span class="main-layout__menu-title">
                <span>{{ item.title }}</span>
                <span
                  v-if="item.index === FEATURED_MENU_INDEX"
                  class="main-layout__featured-badge"
                  aria-label="重点功能"
                  >🎉</span
                >
              </span>
            </template>

            <span
              v-if="menuBursts[item.index]"
              :key="menuBursts[item.index].id"
              class="main-layout__menu-burst"
              :data-burst-id="menuBursts[item.index].id"
              :style="{
                '--burst-origin-x': `${menuBursts[item.index].originX}px`,
                '--burst-origin-y': `${menuBursts[item.index].originY}px`,
              }"
              aria-hidden="true"
            >
              <span class="main-layout__menu-burst-ring"></span>
              <span
                v-for="particle in menuBursts[item.index].particles"
                :key="particle.id"
                class="main-layout__menu-burst-particle"
                :style="{
                  '--particle-color': particle.color,
                  '--particle-delay': `${particle.delay}s`,
                  '--particle-x': `${particle.translateX}px`,
                  '--particle-y': `${particle.translateY}px`,
                }"
              ></span>
            </span>
          </el-menu-item>
        </el-menu>
      </nav>

      <div class="main-layout__aside-footer" :class="{ 'is-collapsed': isSidebarCollapsed }">
        <span class="main-layout__security-indicator" aria-hidden="true"></span>
        <span v-show="!isSidebarCollapsed">
          <strong>安全连接</strong>
          <small>操作全程留痕</small>
        </span>
      </div>
    </el-aside>

    <el-container class="main-layout__workspace">
      <el-header class="main-layout__header" height="var(--header-height)">
        <div class="main-layout__header-context">
          <el-tooltip :content="sidebarToggleLabel" placement="bottom">
            <el-button
              :aria-label="sidebarToggleLabel"
              :aria-pressed="sidebarCollapsed"
              class="main-layout__icon-button main-layout__sidebar-toggle"
              @click="toggleSidebar"
            >
              <el-icon>
                <component :is="sidebarCollapsed ? Expand : Fold" />
              </el-icon>
            </el-button>
          </el-tooltip>

          <div class="main-layout__page-context">
            <span>绿能信盾检测技术服务(保定)有限公司</span>
            <span>www.greenenergyinsp.cn</span>
            <strong class="main-layout__visually-hidden">{{ currentPageTitle }}</strong>
          </div>
          <p v-if="currentPageDescription" class="main-layout__page-description">
            {{ currentPageDescription }}
          </p>
        </div>

        <div class="main-layout__header-actions">
          <form
            v-if="canUseGlobalSearch"
            class="main-layout__global-search"
            role="search"
            @submit.prevent="submitGlobalSearch"
          >
            <el-input
              v-model="globalSearch"
              aria-label="全局搜索资料"
              clearable
              placeholder="搜索资料、项目或编号"
            >
              <template #prefix>
                <el-icon>
                  <Search />
                </el-icon>
              </template>
            </el-input>
            <el-button
              aria-label="提交全局搜索"
              class="main-layout__search-submit"
              native-type="submit"
            >
              <el-icon><Search /></el-icon>
            </el-button>
          </form>

          <el-tooltip :content="themeToggleLabel" placement="bottom">
            <el-button
              :aria-label="themeToggleLabel"
              class="main-layout__icon-button main-layout__theme-toggle"
              :title="themeToggleLabel"
              @click="toggleTheme"
            >
              <el-icon>
                <component :is="isDarkTheme ? Sunny : Moon" />
              </el-icon>
            </el-button>
          </el-tooltip>

          <span class="main-layout__header-divider" aria-hidden="true"></span>

          <el-dropdown class="main-layout__user" trigger="click" @command="handleCommand">
            <button class="main-layout__user-button" type="button">
              <span class="main-layout__user-avatar" aria-hidden="true">
                {{ avatarInitial }}
                <i></i>
              </span>
              <span class="main-layout__user-meta">
                <span class="main-layout__user-name">{{ username }}</span>
                <small>{{ roleLabel }} · {{ accountName }}</small>
              </span>
              <el-icon class="main-layout__user-arrow"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu class="main-layout__user-menu">
                <el-dropdown-item command="change-password">
                  <el-icon><Key /></el-icon>
                  修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-layout__content">
        <div class="main-layout__content-inner">
          <RouterView />
        </div>
      </el-main>
      <SiteFooter class="main-layout__site-footer" />
    </el-container>
  </el-container>
</template>
