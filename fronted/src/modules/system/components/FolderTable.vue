<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { SystemFolder } from '../system.types'
import FolderStatusTag from './FolderStatusTag.vue'

defineProps<{
  folders: SystemFolder[]
  loading?: boolean
}>()

const emit = defineEmits<{
  edit: [folder: SystemFolder]
  move: [folder: SystemFolder]
  disable: [folder: SystemFolder]
}>()
</script>

<template>
  <el-table :data="folders" :loading="loading" row-key="id">
    <el-table-column label="目录" min-width="200">
      <template #default="{ row }: { row: SystemFolder }">
        <strong>{{ row.name }}</strong>
        <p class="system-table__subtext">{{ row.code || '-' }}</p>
      </template>
    </el-table-column>

    <el-table-column label="范围" min-width="150">
      <template #default="{ row }: { row: SystemFolder }">
        {{ row.project_name || '公共目录' }}
      </template>
    </el-table-column>

    <el-table-column label="父级" width="90">
      <template #default="{ row }: { row: SystemFolder }">{{ row.parent || '-' }}</template>
    </el-table-column>

    <el-table-column label="排序" width="80" prop="sort_order" />

    <el-table-column label="状态" width="100">
      <template #default="{ row }: { row: SystemFolder }">
        <FolderStatusTag :active="row.is_active" :system-root="row.is_system_root" />
      </template>
    </el-table-column>

    <el-table-column label="创建人" width="120" prop="created_by_name" />

    <el-table-column label="更新时间" width="170">
      <template #default="{ row }: { row: SystemFolder }">{{ formatDateTime(row.updated_at) }}</template>
    </el-table-column>

    <el-table-column label="操作" fixed="right" width="160">
      <template #default="{ row }: { row: SystemFolder }">
        <el-button :disabled="row.is_system_root" link type="primary" @click="emit('edit', row)">
          编辑
        </el-button>
        <el-button :disabled="row.is_system_root" link @click="emit('move', row)">移动</el-button>
        <el-button
          :disabled="row.is_system_root || !row.is_active"
          link
          type="danger"
          @click="emit('disable', row)"
        >
          停用
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
