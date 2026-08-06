<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { PersonnelRecord } from '../system.types'

defineProps<{
  personnel: PersonnelRecord[]
  loading?: boolean
}>()

const emit = defineEmits<{
  edit: [person: PersonnelRecord]
}>()
</script>

<template>
  <el-table v-loading="loading" :data="personnel" stripe>
    <el-table-column prop="name" label="姓名" min-width="120">
      <template #default="{ row }">
        <router-link
          class="personnel-name-link"
          :to="{ name: 'documents', query: { folder: row.folder_id } }"
        >
          {{ row.name }}
        </router-link>
      </template>
    </el-table-column>
    <el-table-column prop="gender_display" label="性别" width="90" />
    <el-table-column prop="id_card_number" label="身份证号" min-width="190">
      <template #default="{ row }">{{ row.id_card_number || '-' }}</template>
    </el-table-column>
    <el-table-column prop="phone" label="手机号" min-width="140">
      <template #default="{ row }">{{ row.phone || '-' }}</template>
    </el-table-column>
    <el-table-column label="资料状态" width="110">
      <template #default="{ row }">
        <el-tag :type="row.profile_complete ? 'success' : 'warning'" effect="light">
          {{ row.profile_complete ? '完整' : '待完善' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="更新时间" min-width="170">
      <template #default="{ row }">{{ row.updated_at ? formatDateTime(row.updated_at) : '-' }}</template>
    </el-table-column>
    <el-table-column label="操作" width="100" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="emit('edit', row)">编辑</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<style scoped>
.personnel-name-link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.personnel-name-link:hover {
  text-decoration: underline;
}
</style>
