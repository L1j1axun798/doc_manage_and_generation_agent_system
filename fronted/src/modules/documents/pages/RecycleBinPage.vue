<script setup lang="ts">
import DocumentExplorer from '../components/DocumentExplorer.vue'
</script>

<template>
  <section class="document-center-page">
    <header class="document-center-page__header">
      <h1>回收站</h1>
      <p>查看已删除资料，并按后端权限恢复。</p>
    </header>

    <DocumentExplorer mode="trash" />
  </section>
</template>
