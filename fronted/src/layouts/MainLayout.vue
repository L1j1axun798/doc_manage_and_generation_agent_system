<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { appConfig } from '@/config/app'
import { buildMainMenu } from '@/core/router/menu-builder'

const route = useRoute()
const router = useRouter()
const menuItems = buildMainMenu()

const activeMenu = computed(() => route.meta.activeMenu || route.path)

function handleMenuSelect(index: string): void {
  void router.push(index)
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
      </el-header>

      <el-main class="main-layout__content">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>
