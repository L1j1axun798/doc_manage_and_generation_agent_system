<script setup lang="ts">
defineProps<{
  active: boolean
}>()
</script>

<template>
  <el-tag :type="active ? 'success' : 'info'" effect="light">
    {{ active ? '启用' : '停用' }}
  </el-tag>
</template>
