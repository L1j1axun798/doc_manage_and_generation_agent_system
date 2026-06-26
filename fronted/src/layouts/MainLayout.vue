<script setup lang="ts">
import { Moon, Search, Sunny } from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appConfig } from '@/config/app'
import { getRoleLabel } from '@/core/permissions/roles'
import { buildMainMenu } from '@/core/router/menu-builder'
import { useAuthStore } from '@/modules/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const menuItems = computed(() => buildMainMenu(authStore.user?.role))
const globalSearch = ref('')
const THEME_STORAGE_KEY = 'wind-doc-system.theme'

const activeMenu = computed(() => route.meta.activeMenu || route.path)
const username = computed(() => authStore.user?.username || '-')
const roleLabel = computed(() => (authStore.user ? getRoleLabel(authStore.user.role) : ''))
const canUseGlobalSearch = computed(() => authStore.user?.role !== 'temporary_user')
const avatarInitial = computed(() => {
  const source = authStore.user?.real_name?.trim() || authStore.user?.username?.trim() || ''
  return source.slice(0, 1).toUpperCase() || '-'
})
const themeMode = ref<ThemeMode>(resolveInitialTheme())
const isDarkTheme = computed(() => themeMode.value === 'dark')
const themeToggleLabel = computed(() => (isDarkTheme.value ? '切换浅色模式' : '切换深色模式'))

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
    await authStore.logout()
    await router.replace('/login')
  }
}

type ThemeMode = 'light' | 'dark'

function resolveInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (storedTheme === 'light' || storedTheme === 'dark') {
      return storedTheme
    }
  } catch {
    // Ignore unavailable storage and use the default light theme.
  }

  return 'light'
}

function applyTheme(mode: ThemeMode): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = mode
    document.documentElement.style.colorScheme = mode
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // Theme switching should still work even if persistence is unavailable.
  }
}

function toggleTheme(): void {
  themeMode.value = isDarkTheme.value ? 'light' : 'dark'
  applyTheme(themeMode.value)
}

applyTheme(themeMode.value)
</script>

<template>
  <el-container class="main-layout">
    <el-aside class="main-layout__aside" width="224px">
      <div class="main-layout__brand">
        <span class="main-layout__brand-mark" aria-hidden="true">W</span>
        <span class="main-layout__brand-title">{{ appConfig.title }}</span>
      </div>

      <el-menu
        class="main-layout__menu"
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
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="main-layout__header" height="56px">
        <div v-if="canUseGlobalSearch" class="main-layout__global-search" role="search">
          <el-input
            v-model="globalSearch"
            clearable
            placeholder="全局搜索资料"
            @keyup.enter="submitGlobalSearch"
          >
            <template #prefix>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="submitGlobalSearch">全局搜索</el-button>
        </div>

        <el-tooltip :content="themeToggleLabel" placement="bottom">
          <el-button
            :aria-label="themeToggleLabel"
            circle
            class="main-layout__theme-toggle"
            :title="themeToggleLabel"
            @click="toggleTheme"
          >
            <el-icon>
              <component :is="isDarkTheme ? Sunny : Moon" />
            </el-icon>
          </el-button>
        </el-tooltip>

        <el-dropdown class="main-layout__user" trigger="click" @command="handleCommand">
          <button class="main-layout__user-button" type="button">
            <span class="main-layout__user-avatar" aria-hidden="true">{{ avatarInitial }}</span>
            <span class="main-layout__user-meta">
              <span class="main-layout__user-name">{{ username }}</span>
              <small>{{ roleLabel }}</small>
            </span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="change-password">修改密码</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main-layout__content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
