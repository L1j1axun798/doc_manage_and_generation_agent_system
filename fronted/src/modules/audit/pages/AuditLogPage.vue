<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { formatDateTime } from '@/shared/utils/format'
import { fetchAuditLog, fetchAuditLogs } from '../api/audit.api'
import type { AuditLog, AuditResult } from '../audit.types'
import AuditLogDetailDrawer from '../components/AuditLogDetailDrawer.vue'
import AuditResultTag from '../components/AuditResultTag.vue'

const auditLogs = ref<AuditLog[]>([])
const selectedAuditLog = ref<AuditLog | null>(null)
const total = ref(0)
const page = ref(1)
const search = ref('')
const action = ref('')
const resourceType = ref('')
const resourceId = ref('')
const result = ref<AuditResult | ''>('')
const user = ref<number>()
const loading = ref(false)
const detailVisible = ref(false)

onMounted(loadAuditLogs)

async function loadAuditLogs(): Promise<void> {
  loading.value = true
  try {
    const response = await fetchAuditLogs({
      page: page.value,
      search: search.value,
      action: action.value,
      resource_type: resourceType.value,
      resource_id: resourceId.value,
      result: result.value,
      user: user.value,
      ordering: '-created_at',
    })
    auditLogs.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function submitSearch(): void {
  page.value = 1
  void loadAuditLogs()
}

function resetFilters(): void {
  search.value = ''
  action.value = ''
  resourceType.value = ''
  resourceId.value = ''
  result.value = ''
  user.value = undefined
  submitSearch()
}

async function openDetail(auditLog: AuditLog): Promise<void> {
  selectedAuditLog.value = auditLog
  detailVisible.value = true
  try {
    selectedAuditLog.value = await fetchAuditLog(auditLog.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}
</script>

<template>
  <section class="audit-page">
    <header class="audit-page__header">
      <div>
        <h1>审计中心</h1>
        <p>查询系统关键操作、权限拒绝、下载和授权记录。</p>
      </div>
    </header>

    <section class="audit-page__filters">
      <el-input v-model="search" clearable placeholder="搜索动作、资源、错误或请求 ID" @keyup.enter="submitSearch" />
      <el-input v-model="action" clearable placeholder="动作，例如 document.download" />
      <el-input v-model="resourceType" clearable placeholder="资源类型" />
      <el-input v-model="resourceId" clearable placeholder="资源 ID" />
      <el-input-number v-model="user" :min="1" clearable controls-position="right" placeholder="用户 ID" />
      <el-select v-model="result" clearable placeholder="结果">
        <el-option label="成功" value="success" />
        <el-option label="失败" value="failure" />
        <el-option label="拒绝" value="denied" />
      </el-select>
      <el-button :loading="loading" type="primary" @click="submitSearch">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <el-table :data="auditLogs" :loading="loading" row-key="id">
      <el-table-column label="动作" min-width="180" prop="action" />
      <el-table-column label="用户" min-width="140">
        <template #default="{ row }: { row: AuditLog }">
          {{ row.user_real_name || row.user_username || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="资源" min-width="170">
        <template #default="{ row }: { row: AuditLog }">
          {{ row.resource_type || '-' }} / {{ row.resource_id || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="结果" width="90">
        <template #default="{ row }: { row: AuditLog }">
          <AuditResultTag :result="row.result" />
        </template>
      </el-table-column>
      <el-table-column label="IP" width="130">
        <template #default="{ row }: { row: AuditLog }">{{ row.ip_address || '-' }}</template>
      </el-table-column>
      <el-table-column label="时间" width="170">
        <template #default="{ row }: { row: AuditLog }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="80">
        <template #default="{ row }: { row: AuditLog }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <footer class="audit-page__pagination">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="20"
        :total="total"
        @current-change="(nextPage: number) => { page = nextPage; void loadAuditLogs() }"
      />
    </footer>

    <AuditLogDetailDrawer v-model="detailVisible" :audit-log="selectedAuditLog" />
  </section>
</template>
