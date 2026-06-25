<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { formatDateTime } from '@/shared/utils/format'
import { fetchDocumentGrants, revokeDocumentGrant } from '../api/document-grants.api'
import { fetchTemporaryAccessGrants, revokeTemporaryAccessGrant } from '../api/temporary-access.api'
import type { DocumentGrant, TemporaryAccessGrant } from '../access.types'
import GrantStatusTag from '../components/GrantStatusTag.vue'

const activeTab = ref('document')
const search = ref('')
const documentGrantPage = ref(1)
const documentGrantTotal = ref(0)
const temporaryPage = ref(1)
const temporaryTotal = ref(0)
const documentGrants = ref<DocumentGrant[]>([])
const temporaryGrants = ref<TemporaryAccessGrant[]>([])
const documentLoading = ref(false)
const temporaryLoading = ref(false)
const mutationLoading = ref(false)

onMounted(async () => {
  await Promise.all([loadDocumentGrants(), loadTemporaryGrants()])
})

async function loadDocumentGrants(): Promise<void> {
  documentLoading.value = true
  try {
    const response = await fetchDocumentGrants({
      page: documentGrantPage.value,
      search: search.value,
      ordering: '-created_at',
    })
    documentGrants.value = response.results
    documentGrantTotal.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    documentLoading.value = false
  }
}

async function loadTemporaryGrants(): Promise<void> {
  temporaryLoading.value = true
  try {
    const response = await fetchTemporaryAccessGrants({
      page: temporaryPage.value,
      search: search.value,
      ordering: '-created_at',
    })
    temporaryGrants.value = response.results
    temporaryTotal.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    temporaryLoading.value = false
  }
}

function submitSearch(): void {
  documentGrantPage.value = 1
  temporaryPage.value = 1
  void Promise.all([loadDocumentGrants(), loadTemporaryGrants()])
}

function resetSearch(): void {
  search.value = ''
  submitSearch()
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
    await loadDocumentGrants()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function revokeTemporary(grant: TemporaryAccessGrant): Promise<void> {
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

function readableGrantPermissions(grant: DocumentGrant): string {
  return [
    grant.can_view ? '查看' : '',
    grant.can_download ? '下载' : '',
    grant.can_update ? '更新' : '',
    grant.can_delete ? '删除' : '',
    grant.can_restore ? '恢复' : '',
    grant.can_manage ? '管理授权' : '',
  ].filter(Boolean).join('、') || '-'
}
</script>

<template>
  <section class="access-page">
    <header class="access-page__header">
      <div>
        <h1>授权管理</h1>
        <p>查询可管理范围内的文档授权和临时访问授权。</p>
      </div>
    </header>

    <div class="access-page__search">
      <el-input
        v-model="search"
        clearable
        placeholder="搜索授权对象、用户或文件名"
        @keyup.enter="submitSearch"
      />
      <el-button :loading="documentLoading || temporaryLoading" type="primary" @click="submitSearch">
        查询
      </el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-tabs v-model="activeTab" class="access-page__tabs">
      <el-tab-pane label="内部文件授权" name="document">
        <el-table :data="documentGrants" :loading="documentLoading || mutationLoading" row-key="id">
          <el-table-column label="文档" min-width="180" prop="document_title" />
          <el-table-column label="用户" min-width="150">
            <template #default="{ row }: { row: DocumentGrant }">
              <strong>{{ row.user_real_name || row.user_username }}</strong>
              <p class="access-table__subtext">{{ row.user_username || `ID ${row.user}` }}</p>
            </template>
          </el-table-column>
          <el-table-column label="权限" min-width="180">
            <template #default="{ row }: { row: DocumentGrant }">
              {{ readableGrantPermissions(row) }}
            </template>
          </el-table-column>
          <el-table-column label="创建人" width="120" prop="created_by_name" />
          <el-table-column label="到期时间" width="170">
            <template #default="{ row }: { row: DocumentGrant }">
              {{ row.expires_at ? formatDateTime(row.expires_at) : '长期有效' }}
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
          <el-table-column label="操作" fixed="right" width="80">
            <template #default="{ row }: { row: DocumentGrant }">
              <el-button :disabled="!row.is_active" link type="danger" @click="revokeGrant(row)">
                撤销
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <footer class="access-page__pagination">
          <el-pagination
            background
            layout="prev, pager, next, total"
            :current-page="documentGrantPage"
            :page-size="20"
            :total="documentGrantTotal"
            @current-change="(page: number) => { documentGrantPage = page; void loadDocumentGrants() }"
          />
        </footer>
      </el-tab-pane>

      <el-tab-pane label="临时访问授权" name="temporary">
        <el-table :data="temporaryGrants" :loading="temporaryLoading || mutationLoading" row-key="id">
          <el-table-column label="文档" min-width="180" prop="document_title" />
          <el-table-column label="文件名" min-width="170" prop="original_filename" />
          <el-table-column label="创建人" width="120" prop="created_by_name" />
          <el-table-column label="次数" width="100">
            <template #default="{ row }: { row: TemporaryAccessGrant }">
              {{ row.used_count }} / {{ row.max_downloads }}
            </template>
          </el-table-column>
          <el-table-column label="剩余" width="80" prop="remaining_downloads" />
          <el-table-column label="到期时间" width="170">
            <template #default="{ row }: { row: TemporaryAccessGrant }">
              {{ formatDateTime(row.expires_at) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }: { row: TemporaryAccessGrant }">
              <GrantStatusTag
                :active="row.is_active"
                :expired="row.is_expired"
                :revoked-at="row.revoked_at"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" width="80">
            <template #default="{ row }: { row: TemporaryAccessGrant }">
              <el-button :disabled="!row.is_active" link type="danger" @click="revokeTemporary(row)">
                撤销
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <footer class="access-page__pagination">
          <el-pagination
            background
            layout="prev, pager, next, total"
            :current-page="temporaryPage"
            :page-size="20"
            :total="temporaryTotal"
            @current-change="(page: number) => { temporaryPage = page; void loadTemporaryGrants() }"
          />
        </footer>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>
