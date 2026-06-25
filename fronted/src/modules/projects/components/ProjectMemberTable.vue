<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { ProjectMember } from '../projects.types'

defineProps<{
  members: ProjectMember[]
  loading?: boolean
}>()

const emit = defineEmits<{
  edit: [member: ProjectMember]
  delete: [member: ProjectMember]
}>()

const roleLabels = {
  manager: '负责人',
  operator: '资料整理员',
  viewer: '查看者',
}
</script>

<template>
  <el-table :data="members" :loading="loading" row-key="id">
    <el-table-column label="成员" min-width="160">
      <template #default="{ row }: { row: ProjectMember }">
        <strong>{{ row.user_real_name || row.user_username }}</strong>
        <p class="document-table__filename">ID {{ row.user }} / {{ row.user_username }}</p>
      </template>
    </el-table-column>
    <el-table-column label="角色" width="120">
      <template #default="{ row }: { row: ProjectMember }">{{ roleLabels[row.role] }}</template>
    </el-table-column>
    <el-table-column label="权限" min-width="280">
      <template #default="{ row }: { row: ProjectMember }">
        <el-space wrap>
          <el-tag v-if="row.can_upload" size="small">上传</el-tag>
          <el-tag v-if="row.can_download_restricted" size="small">受限下载</el-tag>
          <el-tag v-if="row.can_manage_folder" size="small">目录</el-tag>
          <el-tag v-if="row.can_delete" size="small">删除</el-tag>
          <el-tag v-if="row.can_restore" size="small">恢复</el-tag>
          <el-tag v-if="row.can_manage_permission" size="small">授权</el-tag>
        </el-space>
      </template>
    </el-table-column>
    <el-table-column label="加入时间" width="180">
      <template #default="{ row }: { row: ProjectMember }">{{ formatDateTime(row.joined_at) }}</template>
    </el-table-column>
    <el-table-column label="操作" width="120" fixed="right">
      <template #default="{ row }: { row: ProjectMember }">
        <el-button link @click="emit('edit', row)">修改</el-button>
        <el-button link type="danger" @click="emit('delete', row)">移除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
