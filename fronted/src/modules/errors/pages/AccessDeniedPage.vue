<script setup lang="ts">
import { ArrowLeft, House } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import AppState from '@/shared/components/AppState.vue'

const router = useRouter()
</script>

<template>
  <main class="error-page">
    <AppState
      code="ERROR 403"
      description="当前账号没有访问此页面的权限。如需使用，请联系系统管理员为你开通相应角色。"
      title="无权限访问"
      variant="forbidden"
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
