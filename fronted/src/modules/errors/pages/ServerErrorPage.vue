<script setup lang="ts">
import { House, RefreshRight } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import AppState from '@/shared/components/AppState.vue'

const router = useRouter()

function reloadPage(): void {
  window.location.reload()
}
</script>

<template>
  <main class="error-page">
    <AppState
      code="ERROR 500"
      description="服务暂时没有正确响应。你可以稍后重试；若问题持续，请将发生时间反馈给系统管理员。"
      title="系统暂时不可用"
      variant="error"
    >
      <template #actions>
        <el-button :icon="House" @click="router.push('/dashboard')">返回首页</el-button>
        <el-button :icon="RefreshRight" type="primary" @click="reloadPage">重新加载</el-button>
      </template>
    </AppState>
  </main>
</template>
