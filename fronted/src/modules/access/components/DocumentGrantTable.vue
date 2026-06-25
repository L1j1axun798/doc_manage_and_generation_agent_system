<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { DocumentGrant } from '../access.types'
import GrantStatusTag from './GrantStatusTag.vue'

defineProps<{
  grants: DocumentGrant[]
  loading?: boolean
}>()

const emit = defineEmits<{
  edit: [grant: DocumentGrant]
  revoke: [grant: DocumentGrant]
}>()

const permissionLabels: Array<[keyof DocumentGrant, string]> = [
  ['can_view', '查看'],
  ['can_download', '下载'],
  ['can_update', '更新'],
  ['can_delete', '删除'],
  ['can_restore', '恢复'],
  ['can_manage', '管理授权'],
]

function readablePermissions(grant: DocumentGrant): string {
  return permissionLabels
    .filter(([field]) => grant[field])
    .map(([, label]) => label)
    .join('、') || '-'
}
</script>

<template>
  <el-table :data="grants" :loading="loading" row-key="id">
    <el-table-column label="用户" min-width="150">
      <template #default="{ row }: { row: DocumentGrant }">
        <strong>{{ row.user_real_name || row.user_username }}</strong>
        <p class="access-table__subtext">{{ row.user_username || `ID ${row.user}` }}</p>
      </template>
    </el-table-column>

    <el-table-column label="权限" min-width="180">
      <template #default="{ row }: { row: DocumentGrant }">
        {{ readablePermissions(row) }}
      </template>
    </el-table-column>

    <el-table-column label="状态" width="100">
      <template #default="{ row }: { row: DocumentGrant }">
        <GrantStatusTag
          :active="row.is_active"
          :expired="row.is_expired"
          :revoked-at="row.revoked_at"
        />
      </template>
    </el-table-column>

    <el-table-column label="过期时间" width="170">
      <template #default="{ row }: { row: DocumentGrant }">
        {{ row.expires_at ? formatDateTime(row.expires_at) : '长期有效' }}
      </template>
    </el-table-column>

    <el-table-column label="操作" fixed="right" width="120">
      <template #default="{ row }: { row: DocumentGrant }">
        <el-button :disabled="!row.is_active" link type="primary" @click="emit('edit', row)">
          修改
        </el-button>
        <el-button :disabled="!row.is_active" link type="danger" @click="emit('revoke', row)">
          撤销
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
