<script setup lang="ts">
import type { ProjectStatus } from '../projects.types'

defineProps<{
  status: ProjectStatus
}>()

const labels: Record<ProjectStatus, string> = {
  active: '进行中',
  archived: '已归档',
}

const types: Record<ProjectStatus, 'success' | 'info'> = {
  active: 'success',
  archived: 'info',
}
</script>

<template>
  <el-tag :type="types[status]">{{ labels[status] }}</el-tag>
</template>
