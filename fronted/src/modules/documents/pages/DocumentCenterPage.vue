<script setup lang="ts">
import DocumentExplorer from '../components/DocumentExplorer.vue'
</script>

<template>
  <section class="document-center-page">
    <DocumentExplorer folder-layout="top" scope="public" sync-search-query>
      <template #header>
        <header class="document-center-page__header">
          <h1>资料中心</h1>
          <p>按目录、关键词和访问级别查询当前账号可见资料。</p>
        </header>
      </template>
    </DocumentExplorer>
  </section>
</template>
