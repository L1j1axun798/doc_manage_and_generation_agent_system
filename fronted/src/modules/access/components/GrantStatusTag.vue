<script setup lang="ts">
defineProps<{
  active: boolean
  expired?: boolean
  revokedAt?: string | null
}>()
</script>

<template>
  <el-tag v-if="active" type="success" effect="light">有效</el-tag>
  <el-tag v-else-if="revokedAt" type="info" effect="light">已撤销</el-tag>
  <el-tag v-else-if="expired" type="warning" effect="light">已过期</el-tag>
  <el-tag v-else type="info" effect="light">无效</el-tag>
</template>
