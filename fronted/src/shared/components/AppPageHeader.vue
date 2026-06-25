<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<template>
  <header class="app-page-header">
    <h1>{{ title }}</h1>
  </header>
</template>
