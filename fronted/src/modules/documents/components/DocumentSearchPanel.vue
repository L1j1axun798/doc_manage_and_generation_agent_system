<script setup lang="ts">
import type { DocumentAccessLevel } from '../documents.types'

defineProps<{
  search: string
  accessLevel: DocumentAccessLevel | ''
  ordering: string
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:search': [value: string]
  'update:accessLevel': [value: DocumentAccessLevel | '']
  'update:ordering': [value: string]
  submit: []
  reset: []
}>()
</script>

<template>
  <section class="document-search-panel" aria-label="文档搜索筛选">
    <el-input
      class="document-search-panel__search"
      clearable
      :model-value="search"
      placeholder="搜索标题、描述、文件名或 SHA-256"
      @keyup.enter="emit('submit')"
      @update:model-value="emit('update:search', String($event))"
    />

    <el-select
      clearable
      :model-value="accessLevel"
      placeholder="访问级别"
      @update:model-value="emit('update:accessLevel', ($event || '') as DocumentAccessLevel | '')"
    >
      <el-option label="内部" value="internal" />
      <el-option label="受限" value="restricted" />
    </el-select>

    <el-select
      :model-value="ordering"
      placeholder="排序"
      @update:model-value="emit('update:ordering', String($event))"
    >
      <el-option label="最近更新" value="-updated_at" />
      <el-option label="最早更新" value="updated_at" />
      <el-option label="标题升序" value="title" />
      <el-option label="标题降序" value="-title" />
    </el-select>

    <el-button :loading="loading" type="primary" @click="emit('submit')">查询</el-button>
    <el-button @click="emit('reset')">重置</el-button>
  </section>
</template>
