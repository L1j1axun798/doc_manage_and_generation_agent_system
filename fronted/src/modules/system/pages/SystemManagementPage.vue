<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import type { ApiPage } from '@/shared/types/api.types'
import { formatDateTime, formatFileSize } from '@/shared/utils/format'
import { createFolder, disableFolder, fetchFolders, moveFolder, updateFolder } from '../api/folders.api'
import { fetchHealthStatus, fetchLatestSystemBackup } from '../api/system.api'
import FolderFormDialog from '../components/FolderFormDialog.vue'
import FolderMoveDialog from '../components/FolderMoveDialog.vue'
import FolderTable from '../components/FolderTable.vue'
import type {
  FolderCreatePayload,
  FolderMovePayload,
  FolderUpdatePayload,
  HealthStatus,
  SystemBackupRun,
  SystemBackupStatus,
  SystemBackupTrigger,
  SystemFolder,
} from '../system.types'

const activeTab = ref('directories')
const folders = ref<SystemFolder[]>([])
const health = ref<HealthStatus | null>(null)
const backup = ref<SystemBackupRun | null>(null)
const total = ref(0)
const page = ref(1)
const search = ref('')
const folderLoading = ref(false)
const healthLoading = ref(false)
const backupLoading = ref(false)
const mutationLoading = ref(false)
const formVisible = ref(false)
const moveVisible = ref(false)
const editingFolder = ref<SystemFolder | null>(null)
const movingFolder = ref<SystemFolder | null>(null)

const statusType = computed(() => (health.value?.status === 'ok' ? 'success' : 'danger'))

onMounted(async () => {
  await Promise.all([loadFolders(), loadHealth(), loadBackup()])
})

async function loadFolders(): Promise<void> {
  folderLoading.value = true
  try {
    const response: ApiPage<SystemFolder> = await fetchFolders({
      page: page.value,
      search: search.value,
      ordering: 'sort_order',
    })
    folders.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    folderLoading.value = false
  }
}

async function loadHealth(): Promise<void> {
  healthLoading.value = true
  try {
    health.value = await fetchHealthStatus()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    healthLoading.value = false
  }
}

async function loadBackup(): Promise<void> {
  backupLoading.value = true
  try {
    backup.value = await fetchLatestSystemBackup()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    backupLoading.value = false
  }
}

function backupStatusText(status: SystemBackupStatus): string {
  const labels: Record<SystemBackupStatus, string> = {
    running: '执行中',
    success: '成功',
    failure: '失败',
  }
  return labels[status]
}

function backupStatusType(status: SystemBackupStatus): 'success' | 'warning' | 'danger' {
  if (status === 'success') {
    return 'success'
  }
  if (status === 'running') {
    return 'warning'
  }
  return 'danger'
}

function backupTriggerText(trigger: SystemBackupTrigger): string {
  const labels: Record<SystemBackupTrigger, string> = {
    scheduled: '计划任务',
    manual: '手动',
  }
  return labels[trigger]
}

function submitSearch(): void {
  page.value = 1
  void loadFolders()
}

function resetSearch(): void {
  search.value = ''
  submitSearch()
}

function openCreate(): void {
  editingFolder.value = null
  formVisible.value = true
}

function openEdit(folder: SystemFolder): void {
  editingFolder.value = folder
  formVisible.value = true
}

function openMove(folder: SystemFolder): void {
  movingFolder.value = folder
  moveVisible.value = true
}

async function submitFolder(payload: FolderCreatePayload | FolderUpdatePayload): Promise<void> {
  if (!editingFolder.value) {
    const createPayload = payload as FolderCreatePayload
    if (createPayload.project === null && createPayload.parent === null) {
      ElMessage.warning('公共目录必须选择一个系统根分类作为父级目录')
      return
    }
  }

  mutationLoading.value = true
  try {
    if (editingFolder.value) {
      await updateFolder(editingFolder.value.id, payload as FolderUpdatePayload)
      ElMessage.success('目录已修改')
    } else {
      await createFolder(payload as FolderCreatePayload)
      ElMessage.success('目录已创建')
    }
    formVisible.value = false
    await loadFolders()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function submitMove(payload: FolderMovePayload): Promise<void> {
  if (!movingFolder.value) {
    return
  }

  mutationLoading.value = true
  try {
    await moveFolder(movingFolder.value.id, payload)
    moveVisible.value = false
    ElMessage.success('目录已移动')
    await loadFolders()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function disableCurrentFolder(folder: SystemFolder): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认停用目录“${folder.name}”？`, '停用目录', {
      confirmButtonText: '停用',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await disableFolder(folder.id)
    ElMessage.success('目录已停用')
    await loadFolders()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}
</script>

<template>
  <section class="system-page">
    <el-tabs v-model="activeTab" class="system-page__tabs">
      <el-tab-pane label="资料目录配置" name="directories">
        <section class="system-page__toolbar">
          <el-input v-model="search" clearable placeholder="搜索目录名称或编码" @keyup.enter="submitSearch" />
          <el-button :loading="folderLoading" type="primary" @click="submitSearch">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="openCreate">创建目录</el-button>
        </section>

        <FolderTable
          :folders="folders"
          :loading="folderLoading || mutationLoading"
          @disable="disableCurrentFolder"
          @edit="openEdit"
          @move="openMove"
        />

        <footer class="system-page__pagination">
          <el-pagination
            background
            layout="prev, pager, next, total"
            :current-page="page"
            :page-size="20"
            :total="total"
            @current-change="(nextPage: number) => { page = nextPage; void loadFolders() }"
          />
        </footer>
      </el-tab-pane>

      <el-tab-pane label="系统状态" name="status">
        <section class="system-status-panel">
          <header>
            <h2>后端健康检查</h2>
            <el-button :loading="healthLoading" @click="loadHealth">刷新</el-button>
          </header>

          <el-skeleton v-if="healthLoading && !health" :rows="4" animated />

          <el-descriptions v-else-if="health" border :column="1">
            <el-descriptions-item label="状态">
              <el-tag :type="statusType">{{ health.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="服务">{{ health.service }}</el-descriptions-item>
            <el-descriptions-item label="Debug">{{ health.debug ? '开启' : '关闭' }}</el-descriptions-item>
            <el-descriptions-item label="请求 ID">{{ health.request_id || '-' }}</el-descriptions-item>
          </el-descriptions>
        </section>
      </el-tab-pane>

      <el-tab-pane label="系统配置" name="settings">
        <el-alert
          show-icon
          title="后端暂未开放系统配置接口"
          type="info"
          :closable="false"
        >
          当前前端不提供本地伪配置编辑，避免保存后与后端状态不一致。
        </el-alert>
      </el-tab-pane>

      <el-tab-pane label="备份恢复" name="backup">
        <section class="system-status-panel">
          <header>
            <h2>系统备份状态</h2>
            <el-button :loading="backupLoading" @click="loadBackup">刷新</el-button>
          </header>

          <el-skeleton v-if="backupLoading && !backup" :rows="6" animated />
          <el-empty v-else-if="!backup" description="暂无系统备份记录" />

          <el-descriptions v-else border :column="1">
            <el-descriptions-item label="状态">
              <el-tag :type="backupStatusType(backup.status)">
                {{ backupStatusText(backup.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="触发方式">
              {{ backupTriggerText(backup.trigger) }}
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ formatDateTime(backup.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="结束时间">
              {{ formatDateTime(backup.finished_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="服务器本机副本">
              <el-tag :type="backup.local_available ? 'success' : 'danger'" effect="light">
                {{ backup.local_available ? '已生成' : '不可用' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="可选离机副本">
              <el-tag :type="backup.offsite_available ? 'success' : 'info'" effect="light">
                {{ backup.offsite_available ? '已校验' : '待定期下载' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="备份大小">
              {{ formatFileSize(backup.size_bytes) }}
            </el-descriptions-item>
            <el-descriptions-item label="SHA-256">
              <span class="system-path">{{ backup.sha256 || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item v-if="backup.error_summary" label="失败原因">
              {{ backup.error_summary }}
            </el-descriptions-item>
          </el-descriptions>
        </section>
      </el-tab-pane>
    </el-tabs>

    <FolderFormDialog
      v-model="formVisible"
      :folder="editingFolder"
      :loading="mutationLoading"
      :parent-options="folders"
      @submit="submitFolder"
    />

    <FolderMoveDialog
      v-model="moveVisible"
      :folder="movingFolder"
      :loading="mutationLoading"
      :parent-options="folders"
      @submit="submitMove"
    />
  </section>
</template>
