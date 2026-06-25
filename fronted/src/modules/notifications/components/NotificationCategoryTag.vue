<script setup lang="ts">
import type { NotificationCategory } from '../notifications.types'

defineProps<{
  category: NotificationCategory
}>()

const labels: Record<NotificationCategory, string> = {
  system: '系统',
  document: '文档',
  access: '授权',
}

const types: Record<NotificationCategory, 'info' | 'success' | 'warning'> = {
  system: 'info',
  document: 'success',
  access: 'warning',
}
</script>

<template>
  <el-tag :type="types[category]" effect="light">{{ labels[category] }}</el-tag>
</template>
