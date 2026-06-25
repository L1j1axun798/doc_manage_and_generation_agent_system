<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { TemporaryAccessGrant } from '../access.types'
import GrantStatusTag from './GrantStatusTag.vue'

defineProps<{
  grants: TemporaryAccessGrant[]
  loading?: boolean
}>()

const emit = defineEmits<{
  revoke: [grant: TemporaryAccessGrant]
}>()
</script>

<template>
  <el-table :data="grants" :loading="loading" row-key="id">
    <el-table-column label="文件" min-width="170" prop="original_filename" />

    <el-table-column label="次数" width="100">
      <template #default="{ row }: { row: TemporaryAccessGrant }">
        {{ row.used_count }} / {{ row.max_downloads }}
      </template>
    </el-table-column>

    <el-table-column label="剩余" width="80" prop="remaining_downloads" />

    <el-table-column label="状态" width="100">
      <template #default="{ row }: { row: TemporaryAccessGrant }">
        <GrantStatusTag
          :active="row.is_active"
          :expired="row.is_expired"
          :revoked-at="row.revoked_at"
        />
      </template>
    </el-table-column>

    <el-table-column label="过期时间" width="170">
      <template #default="{ row }: { row: TemporaryAccessGrant }">
        {{ formatDateTime(row.expires_at) }}
      </template>
    </el-table-column>

    <el-table-column label="操作" fixed="right" width="80">
      <template #default="{ row }: { row: TemporaryAccessGrant }">
        <el-button :disabled="!row.is_active" link type="danger" @click="emit('revoke', row)">
          撤销
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>
