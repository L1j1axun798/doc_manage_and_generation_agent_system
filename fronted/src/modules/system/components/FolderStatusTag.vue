<script setup lang="ts">
defineProps<{
  active: boolean
  systemRoot?: boolean
}>()
</script>

<template>
  <el-tag v-if="systemRoot" type="warning" effect="light">系统根</el-tag>
  <el-tag v-else :type="active ? 'success' : 'info'" effect="light">
    {{ active ? '启用' : '停用' }}
  </el-tag>
</template>
