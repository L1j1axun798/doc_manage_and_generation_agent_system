<script setup lang="ts">
import { formatDateTime, formatFileSize } from '@/shared/utils/format'
import type { DocumentItem } from '../documents.types'

withDefaults(
  defineProps<{
    documents: DocumentItem[]
    fixedActions?: boolean
    height?: number | string
    loading?: boolean
    mode?: 'active' | 'trash'
    readOnly?: boolean
    showProject?: boolean
  }>(),
  {
    fixedActions: true,
    readOnly: false,
    showProject: false,
  },
)

const emit = defineEmits<{
  view: [document: DocumentItem]
  download: [document: DocumentItem]
  edit: [document: DocumentItem]
  move: [document: DocumentItem]
  version: [document: DocumentItem]
  delete: [document: DocumentItem]
  restore: [document: DocumentItem]
}>()

function canDownloadDocument(document: DocumentItem): boolean {
  return document.can_download
}
</script>

<template>
  <el-table
    class="document-table"
    :data="documents"
    :height="height"
    :loading="loading"
    row-key="id"
  >
    <el-table-column label="标题" min-width="220">
      <template #default="{ row }: { row: DocumentItem }">
        <button class="document-table__title" type="button" @click="emit('view', row)">
          {{ row.title }}
        </button>
        <p class="document-table__filename">{{ row.current_version?.original_filename || '-' }}</p>
      </template>
    </el-table-column>

    <el-table-column v-if="showProject" label="项目" min-width="160" prop="project_name" />

    <el-table-column label="目录" min-width="140" prop="folder_name" />

    <el-table-column label="大小" width="110">
      <template #default="{ row }: { row: DocumentItem }">
        {{ formatFileSize(row.current_version?.file_size) }}
      </template>
    </el-table-column>

    <el-table-column label="创建人" width="120" prop="created_by_name" />

    <el-table-column label="更新时间" width="180">
      <template #default="{ row }: { row: DocumentItem }">
        {{ formatDateTime(row.updated_at) }}
      </template>
    </el-table-column>

    <el-table-column
      label="操作"
      :fixed="fixedActions ? 'right' : false"
      :width="readOnly || mode === 'trash' ? 160 : 260"
    >
      <template #default="{ row }: { row: DocumentItem }">
        <el-button link type="primary" @click="emit('view', row)">详情</el-button>
        <template v-if="mode === 'trash'">
          <el-button
            v-if="row.can_restore"
            link
            type="success"
            @click="emit('restore', row)"
          >恢复</el-button>
        </template>
        <template v-else>
          <el-button
            :disabled="!canDownloadDocument(row)"
            link
            type="primary"
            @click="emit('download', row)"
          >
            下载
          </el-button>
          <template v-if="!readOnly">
            <el-button v-if="row.can_update" link @click="emit('edit', row)">修改</el-button>
            <el-button v-if="row.can_update" link @click="emit('move', row)">移动</el-button>
            <el-button v-if="row.can_create_version" link @click="emit('version', row)">新版本</el-button>
            <el-button v-if="row.can_delete" link type="danger" @click="emit('delete', row)">删除</el-button>
          </template>
        </template>
      </template>
    </el-table-column>
  </el-table>
</template>
