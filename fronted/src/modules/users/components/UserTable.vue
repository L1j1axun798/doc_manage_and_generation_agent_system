<script setup lang="ts">
import { getRoleLabel } from '@/core/permissions/roles'
import { formatDateTime } from '@/shared/utils/format'
import type { SystemUser } from '../users.types'
import UserStatusTag from './UserStatusTag.vue'

defineProps<{
  users: SystemUser[]
  loading?: boolean
}>()

const emit = defineEmits<{
  view: [user: SystemUser]
  edit: [user: SystemUser]
  disable: [user: SystemUser]
  resetPassword: [user: SystemUser]
}>()

function getUserRowClassName({ row }: { row: SystemUser }): string {
  return row.is_active ? '' : 'user-table-row--inactive'
}
</script>

<template>
  <el-table :data="users" :loading="loading" :row-class-name="getUserRowClassName" row-key="id">
    <el-table-column label="用户" min-width="170">
      <template #default="{ row }: { row: SystemUser }">
        <button class="user-table__name" type="button" @click="emit('view', row)">
          {{ row.real_name }}
        </button>
        <p class="user-table__subtext">{{ row.username }}</p>
      </template>
    </el-table-column>

    <el-table-column label="角色" width="130">
      <template #default="{ row }: { row: SystemUser }">{{ getRoleLabel(row.role) }}</template>
    </el-table-column>

    <el-table-column label="员工编号" width="130">
      <template #default="{ row }: { row: SystemUser }">{{ row.employee_no || '-' }}</template>
    </el-table-column>

    <el-table-column label="手机号" width="140">
      <template #default="{ row }: { row: SystemUser }">{{ row.phone || '-' }}</template>
    </el-table-column>

    <el-table-column label="状态" width="90">
      <template #default="{ row }: { row: SystemUser }">
        <UserStatusTag :active="row.is_active" />
      </template>
    </el-table-column>

    <el-table-column label="改密" width="90">
      <template #default="{ row }: { row: SystemUser }">
        <el-tag :type="row.must_change_password ? 'warning' : 'info'" effect="light">
          {{ row.must_change_password ? '需要' : '否' }}
        </el-tag>
      </template>
    </el-table-column>

    <el-table-column label="创建时间" width="170">
      <template #default="{ row }: { row: SystemUser }">{{ formatDateTime(row.created_at) }}</template>
    </el-table-column>

    <el-table-column label="操作" fixed="right" width="230">
      <template #default="{ row }: { row: SystemUser }">
        <el-button link type="primary" @click="emit('view', row)">详情</el-button>
        <el-button link @click="emit('edit', row)">编辑</el-button>
        <el-button link @click="emit('resetPassword', row)">重置密码</el-button>
        <el-button :disabled="!row.is_active" link type="danger" @click="emit('disable', row)">
          停用
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
