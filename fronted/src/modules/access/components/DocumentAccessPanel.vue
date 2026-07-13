<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import type { ApiPage } from '@/shared/types/api.types'
import type { DocumentItem } from '@/modules/documents/documents.types'
import { createDocumentGrant, fetchDocumentGrants, revokeDocumentGrant, updateDocumentGrant } from '../api/document-grants.api'
import {
  createTemporaryAccessGrant,
  fetchTemporaryAccessGrants,
  revokeTemporaryAccessGrant,
} from '../api/temporary-access.api'
import type {
  DocumentGrant,
  DocumentGrantPayload,
  TemporaryAccessGrant,
  TemporaryAccessGrantCreated,
  TemporaryAccessGrantPayload,
} from '../access.types'
import DocumentGrantDialog from './DocumentGrantDialog.vue'
import DocumentGrantTable from './DocumentGrantTable.vue'
import TemporaryAccessDialog from './TemporaryAccessDialog.vue'
import TemporaryAccessTable from './TemporaryAccessTable.vue'

const props = defineProps<{
  document: DocumentItem
}>()

const grants = ref<DocumentGrant[]>([])
const temporaryGrants = ref<TemporaryAccessGrant[]>([])
const grantsLoading = ref(false)
const temporaryLoading = ref(false)
const mutationLoading = ref(false)
const grantDialogVisible = ref(false)
const temporaryDialogVisible = ref(false)
const editingGrant = ref<DocumentGrant | null>(null)
const createdTemporaryAccess = ref<TemporaryAccessGrantCreated | null>(null)

const hasCurrentVersion = computed(() => Boolean(props.document.current_version?.id))
const frontendTemporaryUrl = computed(() => {
  if (!createdTemporaryAccess.value?.token) {
    return ''
  }
  return `${window.location.origin}/share#token=${encodeURIComponent(createdTemporaryAccess.value.token)}`
})

watch(
  () => props.document.id,
  () => {
    grants.value = []
    temporaryGrants.value = []
    createdTemporaryAccess.value = null
    void Promise.all([loadGrants(), loadTemporaryGrants()])
  },
  { immediate: true },
)

async function loadGrants(): Promise<void> {
  grantsLoading.value = true
  try {
    const response: ApiPage<DocumentGrant> = await fetchDocumentGrants({
      document: props.document.id,
      ordering: '-created_at',
    })
    grants.value = response.results
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    grantsLoading.value = false
  }
}

async function loadTemporaryGrants(): Promise<void> {
  const documentVersionId = props.document.current_version?.id
  if (!documentVersionId) {
    temporaryGrants.value = []
    return
  }

  temporaryLoading.value = true
  try {
    const response: ApiPage<TemporaryAccessGrant> = await fetchTemporaryAccessGrants({
      document_version: documentVersionId,
      ordering: '-created_at',
    })
    temporaryGrants.value = response.results
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    temporaryLoading.value = false
  }
}

function openCreateGrantDialog(): void {
  editingGrant.value = null
  grantDialogVisible.value = true
}

function openEditGrantDialog(grant: DocumentGrant): void {
  editingGrant.value = grant
  grantDialogVisible.value = true
}

async function submitGrant(payload: DocumentGrantPayload): Promise<void> {
  mutationLoading.value = true
  try {
    if (editingGrant.value) {
      await updateDocumentGrant(editingGrant.value.id, {
        can_view: payload.can_view,
        can_download: payload.can_download,
        can_update: payload.can_update,
        can_delete: payload.can_delete,
        can_restore: payload.can_restore,
        expires_at: payload.expires_at,
      })
      ElMessage.success('授权已修改')
    } else {
      await createDocumentGrant(payload)
      ElMessage.success('授权已添加')
    }
    grantDialogVisible.value = false
    await loadGrants()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function revokeGrant(grant: DocumentGrant): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认撤销“${grant.user_real_name || grant.user_username}”的文档授权？`,
      '撤销授权',
      {
        confirmButtonText: '撤销',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await revokeDocumentGrant(grant.id)
    ElMessage.success('授权已撤销')
    await loadGrants()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function submitTemporaryAccess(payload: TemporaryAccessGrantPayload): Promise<void> {
  mutationLoading.value = true
  try {
    createdTemporaryAccess.value = await createTemporaryAccessGrant(payload)
    temporaryDialogVisible.value = false
    ElMessage.success('临时链接已生成')
    await loadTemporaryGrants()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function revokeTemporaryAccess(grant: TemporaryAccessGrant): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认撤销临时访问“${grant.original_filename}”？`, '撤销临时访问', {
      confirmButtonText: '撤销',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await revokeTemporaryAccessGrant(grant.id)
    ElMessage.success('临时访问已撤销')
    await loadTemporaryGrants()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('当前浏览器不允许自动复制')
  }
}
</script>

<template>
  <div class="document-access-panel">
    <section class="document-access-panel__section">
      <header class="document-access-panel__header">
        <div>
          <h3>用户级授权</h3>
          <p>为内部用户授予指定文档的查看、下载或管理权限。</p>
        </div>
        <el-button
          type="primary"
          @click="openCreateGrantDialog"
        >
          添加授权
        </el-button>
      </header>

      <DocumentGrantTable
        :grants="grants"
        :loading="grantsLoading"
        @edit="openEditGrantDialog"
        @revoke="revokeGrant"
      />
    </section>

    <section class="document-access-panel__section">
      <header class="document-access-panel__header">
        <div>
          <h3>临时访问</h3>
          <p>临时链接面向外部下载场景，受过期时间和最大下载次数限制。</p>
        </div>
        <el-button
          :disabled="!hasCurrentVersion"
          type="primary"
          @click="temporaryDialogVisible = true"
        >
          生成临时链接
        </el-button>
      </header>

      <el-alert
        v-if="createdTemporaryAccess"
        class="temporary-access-created"
        show-icon
        title="临时链接只在创建后显示一次"
        type="success"
        :closable="false"
      >
        <div class="temporary-access-created__links">
          <label>
            <span>下载页面</span>
            <el-input :model-value="frontendTemporaryUrl" readonly>
              <template #append>
                <el-button @click="copyText(frontendTemporaryUrl)">复制</el-button>
              </template>
            </el-input>
          </label>
        </div>
      </el-alert>

      <el-alert
        v-if="!hasCurrentVersion"
        show-icon
        title="当前文档没有可下载版本，不能生成临时访问。"
        type="info"
        :closable="false"
      />

      <TemporaryAccessTable
        v-else
        :grants="temporaryGrants"
        :loading="temporaryLoading"
        @revoke="revokeTemporaryAccess"
      />
    </section>

    <DocumentGrantDialog
      v-model="grantDialogVisible"
      :document-id="document.id"
      :grant="editingGrant"
      :loading="mutationLoading"
      @submit="submitGrant"
    />

    <TemporaryAccessDialog
      v-if="document.current_version"
      v-model="temporaryDialogVisible"
      :document-version-id="document.current_version.id"
      :loading="mutationLoading"
      @submit="submitTemporaryAccess"
    />
  </div>
</template>
