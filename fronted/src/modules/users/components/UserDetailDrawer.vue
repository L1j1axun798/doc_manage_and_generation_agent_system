<script setup lang="ts">
import { computed } from 'vue'

import { getRoleLabel } from '@/core/permissions/roles'
import { formatDateTime } from '@/shared/utils/format'
import type { SystemUser } from '../users.types'
import UserStatusTag from './UserStatusTag.vue'

const props = defineProps<{
  modelValue: boolean
  user: SystemUser | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
</script>

<template>
  <el-drawer v-model="drawerVisible" size="460px" title="用户详情">
    <el-descriptions v-if="user" border :column="1">
      <el-descriptions-item label="用户名">{{ user.username }}</el-descriptions-item>
      <el-descriptions-item label="真实姓名">{{ user.real_name }}</el-descriptions-item>
      <el-descriptions-item label="员工编号">{{ user.employee_no || '-' }}</el-descriptions-item>
      <el-descriptions-item label="角色">{{ getRoleLabel(user.role) }}</el-descriptions-item>
      <el-descriptions-item label="手机号">{{ user.phone || '-' }}</el-descriptions-item>
      <el-descriptions-item label="邮箱">{{ user.email || '-' }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <UserStatusTag :active="user.is_active" />
      </el-descriptions-item>
      <el-descriptions-item label="下次登录改密">
        {{ user.must_change_password ? '是' : '否' }}
      </el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ formatDateTime(user.created_at) }}</el-descriptions-item>
    </el-descriptions>
  </el-drawer>
</template>
