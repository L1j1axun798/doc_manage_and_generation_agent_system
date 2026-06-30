<script setup lang="ts">
import DocumentExplorer from '../components/DocumentExplorer.vue'
</script>

<template>
  <section class="document-center-page">
    <DocumentExplorer folder-layout="top" scope="public" sync-search-query />
  </section>
</template>
