<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { Project } from '../projects.types'
import ProjectStatusTag from './ProjectStatusTag.vue'

withDefaults(
  defineProps<{
    projects: Project[]
    loading?: boolean
    showDelete?: boolean
  }>(),
  {
    showDelete: false,
  },
)

const emit = defineEmits<{
  view: [project: Project]
  edit: [project: Project]
  delete: [project: Project]
}>()
</script>

<template>
  <el-table :data="projects" :loading="loading" row-key="id">
    <el-table-column label="项目" min-width="220">
      <template #default="{ row }: { row: Project }">
        <button class="document-table__title" type="button" @click="emit('view', row)">
          {{ row.name }}
        </button>
        <p class="document-table__filename">{{ row.code }}</p>
      </template>
    </el-table-column>
    <el-table-column label="负责人" width="140" prop="manager_name" />
    <el-table-column label="状态" width="110">
      <template #default="{ row }: { row: Project }">
        <ProjectStatusTag :status="row.status" />
      </template>
    </el-table-column>
    <el-table-column label="更新时间" width="180">
      <template #default="{ row }: { row: Project }">{{ formatDateTime(row.updated_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="180" fixed="right">
      <template #default="{ row }: { row: Project }">
        <el-button link type="primary" @click="emit('view', row)">详情</el-button>
        <el-button link @click="emit('edit', row)">修改</el-button>
        <el-button v-if="showDelete" link type="danger" @click="emit('delete', row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
