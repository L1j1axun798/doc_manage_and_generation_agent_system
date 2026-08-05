<script setup lang="ts">
import DocumentExplorer from '../components/DocumentExplorer.vue'
</script>

<template>
  <section class="document-center-page">
    <DocumentExplorer mode="trash" :show-folders="false" />
  </section>
</template>
