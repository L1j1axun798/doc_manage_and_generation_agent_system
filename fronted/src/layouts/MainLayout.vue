<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appConfig } from '@/config/app'
import { getRoleLabel } from '@/core/permissions/roles'
import { buildMainMenu } from '@/core/router/menu-builder'
import { useAuthStore } from '@/modules/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const menuItems = computed(() => buildMainMenu(authStore.user?.role))

const activeMenu = computed(() => route.meta.activeMenu || route.path)
const userDisplayName = computed(() => authStore.user?.real_name || authStore.user?.username || '')
const roleLabel = computed(() => (authStore.user ? getRoleLabel(authStore.user.role) : ''))

function handleMenuSelect(index: string): void {
  void router.push(index)
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
        <div class="main-layout__header-title">{{ route.meta.title }}</div>

        <el-dropdown class="main-layout__user" trigger="click" @command="handleCommand">
          <button class="main-layout__user-button" type="button">
            <span>{{ userDisplayName }}</span>
            <small>{{ roleLabel }}</small>
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
