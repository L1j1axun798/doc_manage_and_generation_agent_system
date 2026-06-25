<script setup lang="ts">
import type { DocumentAccessLevel } from '../documents.types'

defineProps<{
  value: DocumentAccessLevel
}>()

const labels: Record<DocumentAccessLevel, string> = {
  internal: '内部',
  restricted: '受限',
}

const tagTypes: Record<DocumentAccessLevel, 'success' | 'warning'> = {
  internal: 'success',
  restricted: 'warning',
}
</script>

<template>
  <el-tag :type="tagTypes[value]" effect="light">{{ labels[value] }}</el-tag>
</template>
