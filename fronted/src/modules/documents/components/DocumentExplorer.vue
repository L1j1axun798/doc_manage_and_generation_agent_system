<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import type { ApiPage } from '@/shared/types/api.types'
import {
  deleteDocument,
  downloadDocument,
  fetchDocuments,
  fetchDocument,
  fetchTrashDocuments,
  moveDocument,
  restoreDocument,
  updateDocument,
  uploadDocument,
  uploadDocumentVersion,
} from '../api/documents.api'
import { fetchFolderTree } from '../api/folders.api'
import type {
  DocumentAccessLevel,
  DocumentItem,
  DocumentMovePayload,
  DocumentUpdatePayload,
  DocumentUploadPayload,
  FolderTreeNode,
} from '../documents.types'
import DocumentDetailDrawer from './DocumentDetailDrawer.vue'
import DocumentEditDialog from './DocumentEditDialog.vue'
import DocumentMoveDialog from './DocumentMoveDialog.vue'
import DocumentSearchPanel from './DocumentSearchPanel.vue'
import DocumentTable from './DocumentTable.vue'
import DocumentUploadDialog from './DocumentUploadDialog.vue'
import DocumentVersionUploadDialog from './DocumentVersionUploadDialog.vue'
import FolderTree from './FolderTree.vue'
import { getPublicRootFolderNodes } from '../utils/public-root-folders'

const props = withDefaults(
  defineProps<{
    folderLayout?: 'side' | 'top'
    mode?: 'active' | 'trash'
    showFolders?: boolean
    showFolderNavigation?: boolean
    scope?: 'all' | 'public' | 'project'
    syncSearchQuery?: boolean
    projectId?: number
  }>(),
  {
    folderLayout: 'side',
    mode: 'active',
    showFolders: true,
    showFolderNavigation: true,
    scope: 'all',
    syncSearchQuery: false,
  },
)

const route = useRoute()

function resolveFolderTreeParam(): number | 'public' | undefined {
  if (props.scope === 'public') {
    return 'public'
  }
  if (props.scope === 'project') {
    return props.projectId
  }
  return undefined
}

const folderTree = ref<FolderTreeNode[]>([])
const selectedFolderId = ref<number>()
const documents = ref<DocumentItem[]>([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const accessLevel = ref<DocumentAccessLevel | ''>('')
const ordering = ref('-updated_at')
const treeLoading = ref(false)
const listLoading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const selectedDocument = ref<DocumentItem | null>(null)
const actionDocument = ref<DocumentItem | null>(null)
const uploadVisible = ref(false)
const editVisible = ref(false)
const moveVisible = ref(false)
const versionVisible = ref(false)
const mutationLoading = ref(false)
const suppressNextFolderReload = ref(false)

const isEmpty = computed(() => !listLoading.value && documents.value.length === 0)
const isTrashMode = computed(() => props.mode === 'trash')
const shouldShowFolderNavigation = computed(() => props.showFolders && props.showFolderNavigation)
const isTopPublicFolderMode = computed(
  () => shouldShowFolderNavigation.value && props.folderLayout === 'top' && props.scope === 'public',
)

onMounted(async () => {
  applyRouteSearch(false)
  await Promise.all([props.showFolders ? loadFolderTree() : Promise.resolve(), loadDocuments()])
})

watch(
  () => [props.showFolders, props.scope, props.projectId] as const,
  () => {
    selectedFolderId.value = undefined
    page.value = 1
    folderTree.value = []
    void Promise.all([props.showFolders ? loadFolderTree() : Promise.resolve(), loadDocuments()])
  },
)

watch(selectedFolderId, () => {
  if (suppressNextFolderReload.value) {
    suppressNextFolderReload.value = false
    return
  }

  page.value = 1
  void loadDocuments()
})

watch(
  () => (props.syncSearchQuery ? route.query.search : undefined),
  () => {
    applyRouteSearch(true)
  },
)

function getRouteSearch(): string {
  return typeof route.query.search === 'string' ? route.query.search : ''
}

function applyRouteSearch(reload: boolean): void {
  if (!props.syncSearchQuery) {
    return
  }

  const nextSearch = getRouteSearch()
  if (search.value === nextSearch) {
    return
  }

  search.value = nextSearch
  if (selectedFolderId.value !== undefined) {
    suppressNextFolderReload.value = true
    selectedFolderId.value = undefined
  }
  page.value = 1

  if (reload) {
    void loadDocuments()
  }
}

async function loadFolderTree(): Promise<void> {
  if (!props.showFolders) {
    folderTree.value = []
    return
  }

  treeLoading.value = true

  try {
    folderTree.value = await fetchFolderTree(resolveFolderTreeParam())
    syncTopFolderSelection()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    treeLoading.value = false
  }
}

function syncTopFolderSelection(): void {
  if (!isTopPublicFolderMode.value) {
    return
  }

  if (props.syncSearchQuery && search.value.trim()) {
    selectedFolderId.value = undefined
    return
  }

  const publicRootNodes = getPublicRootFolderNodes(folderTree.value)
  if (publicRootNodes.length === 0) {
    selectedFolderId.value = undefined
    return
  }

  const selectedFolderExists = publicRootNodes.some(
    (node) =>
      node.id === selectedFolderId.value ||
      node.children.some((child) => child.id === selectedFolderId.value),
  )
  if (!selectedFolderExists) {
    selectedFolderId.value = publicRootNodes[0].id
  }
}

async function loadDocuments(): Promise<void> {
  listLoading.value = true

  try {
    const query = {
      page: page.value,
      search: search.value,
      ordering: ordering.value,
      project: props.scope === 'project' ? props.projectId : undefined,
      folder: shouldShowFolderNavigation.value ? selectedFolderId.value : undefined,
      access_level: accessLevel.value || undefined,
    }
    const response: ApiPage<DocumentItem> = isTrashMode.value
      ? await fetchTrashDocuments(query)
      : await fetchDocuments(query)
    documents.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    listLoading.value = false
  }
}

function submitSearch(): void {
  page.value = 1
  void loadDocuments()
}

function resetFilters(): void {
  search.value = ''
  accessLevel.value = ''
  ordering.value = '-updated_at'
  page.value = 1
  void loadDocuments()
}

async function openDocumentDetail(document: DocumentItem): Promise<void> {
  detailVisible.value = true
  detailLoading.value = true
  selectedDocument.value = document

  try {
    selectedDocument.value = await fetchDocument(document.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

function handlePageChange(nextPage: number): void {
  page.value = nextPage
  void loadDocuments()
}

async function handleUpload(payload: DocumentUploadPayload): Promise<void> {
  mutationLoading.value = true

  try {
    await uploadDocument(payload)
    uploadVisible.value = false
    ElMessage.success('上传成功')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function handleDownload(document: DocumentItem): Promise<void> {
  mutationLoading.value = true

  try {
    await downloadDocument(document)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

function openEditDialog(document: DocumentItem): void {
  actionDocument.value = document
  editVisible.value = true
}

async function handleEdit(payload: DocumentUpdatePayload): Promise<void> {
  if (!actionDocument.value) {
    return
  }

  mutationLoading.value = true

  try {
    await updateDocument(actionDocument.value.id, payload)
    editVisible.value = false
    ElMessage.success('修改成功')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

function openMoveDialog(document: DocumentItem): void {
  actionDocument.value = document
  moveVisible.value = true
}

async function handleMove(payload: DocumentMovePayload): Promise<void> {
  if (!actionDocument.value) {
    return
  }

  mutationLoading.value = true

  try {
    await moveDocument(actionDocument.value.id, payload)
    moveVisible.value = false
    ElMessage.success('移动成功')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

function openVersionDialog(document: DocumentItem): void {
  actionDocument.value = document
  versionVisible.value = true
}

async function handleVersionUpload(file: File): Promise<void> {
  if (!actionDocument.value) {
    return
  }

  mutationLoading.value = true

  try {
    await uploadDocumentVersion(actionDocument.value.id, file)
    versionVisible.value = false
    ElMessage.success('新版本已上传')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function handleDelete(document: DocumentItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除“${document.title}”？删除后可在回收站恢复。`, '删除资料', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  mutationLoading.value = true

  try {
    await deleteDocument(document.id, {
      expected_updated_at: document.updated_at,
    })
    ElMessage.success('已删除')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function handleRestore(document: DocumentItem): Promise<void> {
  mutationLoading.value = true

  try {
    await restoreDocument(document.id, {
      expected_updated_at: document.updated_at,
    })
    ElMessage.success('已恢复')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}
</script>

<template>
  <section
    class="document-explorer"
    :class="[
      `document-explorer--${folderLayout}`,
      { 'document-explorer--no-folders': !shouldShowFolderNavigation },
    ]"
  >
    <FolderTree
      v-if="shouldShowFolderNavigation"
      v-model="selectedFolderId"
      :presentation="folderLayout"
      :loading="treeLoading"
      :nodes="folderTree"
    />

    <div class="document-explorer__workspace">
      <slot name="header" />

      <div class="document-explorer__actions">
        <DocumentSearchPanel
          v-model:access-level="accessLevel"
          v-model:ordering="ordering"
          v-model:search="search"
          :loading="listLoading"
          @reset="resetFilters"
          @submit="submitSearch"
        />

        <div class="document-explorer__toolbar">
          <el-button
            v-if="!isTrashMode"
            type="primary"
            @click="uploadVisible = true"
          >
            上传资料
          </el-button>
          <RouterLink v-if="!isTrashMode" to="/documents/recycle-bin">回收站</RouterLink>
          <RouterLink v-else to="/documents">返回资料中心</RouterLink>
        </div>
      </div>

      <DocumentTable
        :documents="documents"
        :fixed-actions="folderLayout !== 'top'"
        :height="folderLayout === 'top' ? 480 : undefined"
        :loading="listLoading"
        :mode="props.mode"
        @delete="handleDelete"
        @download="handleDownload"
        @edit="openEditDialog"
        @move="openMoveDialog"
        @restore="handleRestore"
        @version="openVersionDialog"
        @view="openDocumentDetail"
      />

      <el-empty v-if="isEmpty && folderLayout !== 'top'" description="暂无资料" />

      <footer class="document-explorer__pagination">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :current-page="page"
          :page-size="20"
          :total="total"
          @current-change="handlePageChange"
        />
      </footer>
    </div>

    <DocumentDetailDrawer
      v-model="detailVisible"
      :document="selectedDocument"
      :loading="detailLoading"
    />

    <DocumentUploadDialog
      v-if="!isTrashMode"
      v-model="uploadVisible"
      :folders="folderTree"
      :initial-folder-id="selectedFolderId"
      :loading="mutationLoading"
      @submit="handleUpload"
    />

    <DocumentEditDialog
      v-model="editVisible"
      :document="actionDocument"
      :loading="mutationLoading"
      @submit="handleEdit"
    />

    <DocumentMoveDialog
      v-model="moveVisible"
      :document="actionDocument"
      :folders="folderTree"
      :loading="mutationLoading"
      @submit="handleMove"
    />

    <DocumentVersionUploadDialog
      v-model="versionVisible"
      :document="actionDocument"
      :loading="mutationLoading"
      @submit="handleVersionUpload"
    />
  </section>
</template>
