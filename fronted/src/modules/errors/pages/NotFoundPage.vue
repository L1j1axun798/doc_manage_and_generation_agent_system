<script setup lang="ts">
import { ArrowLeft, House } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import AppState from '@/shared/components/AppState.vue'

const router = useRouter()
</script>

<template>
  <main class="not-found-page">
    <AppState
      code="ERROR 404"
      description="你访问的页面可能已移动、被删除，或链接地址不完整。"
      title="页面不存在"
      variant="not-found"
    >
      <template #actions>
        <el-button :icon="ArrowLeft" @click="router.back()">返回上一页</el-button>
        <el-button :icon="House" type="primary" @click="router.push('/dashboard')">
          返回首页
        </el-button>
      </template>
    </AppState>
  </main>
</template>
