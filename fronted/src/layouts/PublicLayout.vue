<script setup lang="ts">
import SiteFooter from '@/shared/components/SiteFooter.vue'
</script>

<template>
  <main class="public-layout">
    <div class="public-layout__content">
      <RouterView />
    </div>
    <SiteFooter />
  </main>
</template>
