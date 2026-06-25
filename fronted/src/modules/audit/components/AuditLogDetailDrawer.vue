<script setup lang="ts">
import { computed } from 'vue'

import { formatDateTime } from '@/shared/utils/format'
import type { AuditLog } from '../audit.types'
import AuditResultTag from './AuditResultTag.vue'

const props = defineProps<{
  modelValue: boolean
  auditLog: AuditLog | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

function stringify(value: Record<string, unknown> | null): string {
  return value ? JSON.stringify(value, null, 2) : '-'
}
</script>

<template>
  <el-drawer v-model="drawerVisible" size="620px" title="审计详情">
    <el-descriptions v-if="auditLog" border :column="1">
      <el-descriptions-item label="动作">{{ auditLog.action }}</el-descriptions-item>
      <el-descriptions-item label="结果">
        <AuditResultTag :result="auditLog.result" />
      </el-descriptions-item>
      <el-descriptions-item label="用户">
        {{ auditLog.user_real_name || auditLog.user_username || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="资源">
        {{ auditLog.resource_type || '-' }} / {{ auditLog.resource_id || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="IP">{{ auditLog.ip_address || '-' }}</el-descriptions-item>
      <el-descriptions-item label="请求 ID">{{ auditLog.request_id || '-' }}</el-descriptions-item>
      <el-descriptions-item label="错误信息">{{ auditLog.error_message || '-' }}</el-descriptions-item>
      <el-descriptions-item label="发生时间">{{ formatDateTime(auditLog.created_at) }}</el-descriptions-item>
    </el-descriptions>

    <section v-if="auditLog" class="audit-json-section">
      <h3>变更前</h3>
      <pre>{{ stringify(auditLog.before_data) }}</pre>
      <h3>变更后</h3>
      <pre>{{ stringify(auditLog.after_data) }}</pre>
      <h3>User-Agent</h3>
      <pre>{{ auditLog.user_agent || '-' }}</pre>
    </section>
  </el-drawer>
</template>
