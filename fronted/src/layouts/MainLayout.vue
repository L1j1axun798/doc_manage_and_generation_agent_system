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
import { useTheme } from '@/shared/composables/useTheme'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { isDarkTheme, toggleTheme } = useTheme()
const globalSearch = ref('')
const sidebarCollapsed = ref(false)
const compactViewport = ref(false)
let compactViewportQuery: MediaQueryList | null = null

const menuItems = computed(() => buildMainMenu(authStore.user?.role))
const activeMenu = computed(() => String(route.meta.activeMenu || route.path))
const currentPageTitle = computed(() => String(route.meta.title || appConfig.title))
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
      <div class="main-layout__brand">
        <span class="main-layout__brand-mark" aria-hidden="true">
          <span>W</span>
        </span>
        <span v-show="!isSidebarCollapsed" class="main-layout__brand-copy">
          <strong class="main-layout__brand-title">{{ appConfig.title }}</strong>
          <small>企业资料工作台</small>
        </span>
      </div>

      <nav class="main-layout__navigation" aria-label="主导航">
        <p v-show="!isSidebarCollapsed" class="main-layout__menu-label">工作台</p>
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
          >
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
            <template #title>{{ item.title }}</template>
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
            <span>WIND DOC · 工作台</span>
            <strong>{{ currentPageTitle }}</strong>
          </div>
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
    </el-container>
  </el-container>
</template>
