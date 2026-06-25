<script setup lang="ts">
import type { AuditResult } from '../audit.types'

defineProps<{
  result: AuditResult
}>()

const labels: Record<AuditResult, string> = {
  success: '成功',
  failure: '失败',
  denied: '拒绝',
}

const types: Record<AuditResult, 'success' | 'danger' | 'warning'> = {
  success: 'success',
  failure: 'danger',
  denied: 'warning',
}
</script>

<template>
  <el-tag :type="types[result]" effect="light">{{ labels[result] }}</el-tag>
</template>
