<script setup lang="ts">
import DocumentExplorer from '../components/DocumentExplorer.vue'
import EntryPreparationDocumentsPanel from '../components/EntryPreparationDocumentsPanel.vue'
</script>

<template>
  <section class="document-center-page">
    <DocumentExplorer
      folder-layout="top"
      scope="public"
      sync-search-query
    >
      <template #entry-preparation>
        <EntryPreparationDocumentsPanel />
      </template>
    </DocumentExplorer>
  </section>
</template>
