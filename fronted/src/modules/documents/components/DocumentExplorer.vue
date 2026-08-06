<script setup lang="ts">
import { ArrowDown, Close, Delete, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import type { ApiPage } from '@/shared/types/api.types'
import {
  deleteDocument,
  downloadDocumentCenter,
  downloadDocument,
  downloadFolder,
  fetchDocuments,
  fetchDocument,
  fetchTrashDocuments,
  moveDocument,
  restoreDocument,
  updateDocument,
  uploadDocument,
  uploadDocumentVersion,
} from '../api/documents.api'
import { createFolder, disableFolder, fetchFolderTree } from '../api/folders.api'
import type {
  DocumentItem,
  DocumentMovePayload,
  DocumentUpdatePayload,
  DocumentUploadPayload,
  DocumentSourceType,
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
import {
  getPublicRootFolderNodes,
  type PublicRootFolderNode,
} from '../utils/public-root-folders'

const props = withDefaults(
  defineProps<{
    folderLayout?: 'side' | 'top'
    mode?: 'active' | 'trash'
    showFolders?: boolean
    showFolderNavigation?: boolean
    scope?: 'all' | 'public' | 'project'
    syncSearchQuery?: boolean
    projectId?: number
    fixedFolderCode?: string
    sourceType?: DocumentSourceType
    excludedMutationFolderCodes?: string[]
  }>(),
  {
    folderLayout: 'side',
    mode: 'active',
    showFolders: true,
    showFolderNavigation: true,
    scope: 'all',
    syncSearchQuery: false,
    excludedMutationFolderCodes: () => [],
  },
)

const route = useRoute()
const authStore = useAuthStore()

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
const folderDownloadLoading = ref(false)
const centerDownloadLoading = ref(false)
const suppressNextFolderReload = ref(false)
const hiddenDocumentResultsFolderId = ref<number>()

const isEmpty = computed(() => !listLoading.value && documents.value.length === 0)
const isTrashMode = computed(() => props.mode === 'trash')
const shouldShowFolderNavigation = computed(() => props.showFolders && props.showFolderNavigation)
const isTopPublicFolderMode = computed(
  () => shouldShowFolderNavigation.value && props.folderLayout === 'top' && props.scope === 'public',
)
const shouldMoveToPublicRootsOnly = computed(
  () => props.folderLayout === 'top' && props.scope === 'public',
)
const publicRootNodes = computed(() =>
  isTopPublicFolderMode.value ? getPublicRootFolderNodes(folderTree.value) : [],
)
const fixedFolderNode = computed(() =>
  props.fixedFolderCode ? findFolderByCode(folderTree.value, props.fixedFolderCode) : undefined,
)
const effectiveFolderId = computed(() => fixedFolderNode.value?.id ?? selectedFolderId.value)
const mutationFolderTree = computed(() => {
  if (fixedFolderNode.value) {
    return [fixedFolderNode.value]
  }
  return excludeFolderCodes(folderTree.value, new Set(props.excludedMutationFolderCodes))
})
const selectedPublicRootNode = computed<PublicRootFolderNode | undefined>(() => {
  const folderId = selectedFolderId.value
  if (!isTopPublicFolderMode.value || folderId === undefined) {
    return undefined
  }

  return publicRootNodes.value.find(
    (node) => node.id === folderId || hasDescendant(node, folderId),
  )
})
const isEntryPreparationSelection = computed(
  () => selectedPublicRootNode.value?.publicRootKey === 'entryPreparation',
)
const isTechnicalSolutionSelection = computed(
  () => selectedPublicRootNode.value?.publicRootKey === 'technicalSolution',
)
const subfolderPanelRoot = computed(() => {
  const root = selectedPublicRootNode.value
  if (!root || !['company', 'staff'].includes(root.publicRootKey)) {
    return undefined
  }
  return root
})
const subfolderItems = computed(() => subfolderPanelRoot.value?.children ?? [])
const selectedSubfolderItem = computed(() => {
  const folderId = selectedFolderId.value
  if (!subfolderPanelRoot.value || folderId === undefined || isSubfolderPanelRootLanding.value) {
    return undefined
  }

  return subfolderItems.value.find((item) => item.id === folderId || hasDescendant(item, folderId))
})
const isSubfolderDetailMode = computed(() => selectedSubfolderItem.value !== undefined)
const visibleSubfolderItems = computed(() =>
  selectedSubfolderItem.value ? [selectedSubfolderItem.value] : subfolderItems.value,
)
const isCompanyRoot = computed(() => selectedPublicRootNode.value?.publicRootKey === 'company')
const isStaffRoot = computed(() => selectedPublicRootNode.value?.publicRootKey === 'staff')
const isSubfolderPanelRootLanding = computed(
  () =>
    Boolean(subfolderPanelRoot.value) &&
    selectedFolderId.value === selectedPublicRootNode.value?.id,
)
const isArchiveSelection = computed(() => selectedPublicRootNode.value?.publicRootKey === 'archive')
const isArchiveRootLanding = computed(
  () => isArchiveSelection.value && selectedFolderId.value === selectedPublicRootNode.value?.id,
)
const isArchiveYearSelected = computed(
  () =>
    isArchiveSelection.value &&
    selectedFolderId.value !== undefined &&
    selectedFolderId.value !== selectedPublicRootNode.value?.id,
)
const canCloseDocumentResults = computed(
  () =>
    Boolean(selectedFolderId.value) &&
    ['company', 'staff'].includes(selectedPublicRootNode.value?.publicRootKey ?? '') &&
    !isSubfolderPanelRootLanding.value,
)
const isDocumentResultsHidden = computed(
  () =>
    canCloseDocumentResults.value &&
    selectedFolderId.value === hiddenDocumentResultsFolderId.value,
)
const shouldShowDocumentResults = computed(
  () =>
    !isSubfolderPanelRootLanding.value &&
    !isDocumentResultsHidden.value &&
    !isArchiveRootLanding.value,
)
const subfolderPanelTitle = computed(() =>
  selectedSubfolderItem.value?.name ?? (isStaffRoot.value ? '人员名单' : '公司名单'),
)
const subfolderPanelCountText = computed(() =>
  isStaffRoot.value
    ? `人员数：${subfolderItems.value.length}`
    : `公司数：${subfolderItems.value.length}`,
)
const subfolderPanelEmptyText = computed(() =>
  isStaffRoot.value ? '暂无人员' : '暂无公司',
)
const canUpload = computed(
  () => !isTrashMode.value && !isSubfolderPanelRootLanding.value && !isArchiveSelection.value,
)
const showDocumentCenterDownloads = computed(
  () => isTopPublicFolderMode.value && !isTrashMode.value,
)
const canCreateSubfolder = computed(
  () => authStore.isSystemAdmin && (isCompanyRoot.value || isStaffRoot.value),
)
const canDeleteSubfolder = computed(() => canCreateSubfolder.value)
const subfolderCreateButtonText = computed(() => (isStaffRoot.value ? '添加用户' : '添加公司'))

onMounted(async () => {
  applyRouteSearch(false)
  await reloadExplorer()
})

watch(
  () => [
    props.showFolders,
    props.scope,
    props.projectId,
    props.fixedFolderCode,
    props.sourceType,
  ] as const,
  () => {
    selectedFolderId.value = undefined
    page.value = 1
    folderTree.value = []
    void reloadExplorer()
  },
)

watch(selectedFolderId, () => {
  if (suppressNextFolderReload.value) {
    suppressNextFolderReload.value = false
    return
  }

  page.value = 1
  hiddenDocumentResultsFolderId.value = undefined
  void loadDocuments()
})

watch(
  () => (props.syncSearchQuery ? route.query.search : undefined),
  () => {
    applyRouteSearch(true)
  },
)

watch(
  () => (isTopPublicFolderMode.value ? route.query.folder : undefined),
  () => {
    if (applyRouteFolderSelection()) {
      page.value = 1
    }
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

function getRouteFolderId(): number | undefined {
  const value = route.query.folder
  const rawValue = Array.isArray(value) ? value[0] : value
  if (typeof rawValue !== 'string' || !/^\d+$/.test(rawValue)) {
    return undefined
  }

  const folderId = Number(rawValue)
  return Number.isSafeInteger(folderId) && folderId > 0 ? folderId : undefined
}

function applyRouteFolderSelection(): boolean {
  if (!isTopPublicFolderMode.value || (props.syncSearchQuery && search.value.trim())) {
    return false
  }

  const folderId = getRouteFolderId()
  const folderExists = publicRootNodes.value.some(
    (node) => folderId !== undefined && (node.id === folderId || hasDescendant(node, folderId)),
  )
  if (!folderExists || selectedFolderId.value === folderId) {
    return false
  }

  selectedFolderId.value = folderId
  return true
}

async function loadFolderTree(): Promise<void> {
  if (!props.showFolders) {
    folderTree.value = []
    return
  }

  treeLoading.value = true

  try {
    folderTree.value = await fetchFolderTree(resolveFolderTreeParam())
    if (fixedFolderNode.value) {
      selectedFolderId.value = fixedFolderNode.value.id
    }
    applyRouteFolderSelection()
    syncTopFolderSelection()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    treeLoading.value = false
  }
}

async function reloadExplorer(): Promise<void> {
  if (props.showFolders) {
    await loadFolderTree()
  }
  await loadDocuments()
}

function syncTopFolderSelection(): void {
  if (!isTopPublicFolderMode.value) {
    return
  }

  if (props.syncSearchQuery && search.value.trim()) {
    selectedFolderId.value = undefined
    return
  }

  if (publicRootNodes.value.length === 0) {
    selectedFolderId.value = undefined
    return
  }

  const folderId = selectedFolderId.value
  const selectedFolderExists = publicRootNodes.value.some(
    (node) => folderId !== undefined && (node.id === folderId || hasDescendant(node, folderId)),
  )
  if (!selectedFolderExists) {
    selectedFolderId.value = publicRootNodes.value[0].id
  }
}

function findFolderByCode(nodes: FolderTreeNode[], code: string): FolderTreeNode | undefined {
  for (const node of nodes) {
    if (node.code === code) {
      return node
    }
    const child = findFolderByCode(node.children, code)
    if (child) {
      return child
    }
  }
  return undefined
}

function excludeFolderCodes(nodes: FolderTreeNode[], excludedCodes: Set<string>): FolderTreeNode[] {
  return nodes
    .filter((node) => !excludedCodes.has(node.code))
    .map((node) => ({
      ...node,
      children: excludeFolderCodes(node.children, excludedCodes),
    }))
}

function hasDescendant(node: FolderTreeNode, folderId: number): boolean {
  return node.children.some((child) => child.id === folderId || hasDescendant(child, folderId))
}

function selectSubfolderItem(item: FolderTreeNode): void {
  if (!canSelectSubfolder(item)) {
    return
  }

  hiddenDocumentResultsFolderId.value = undefined
  selectedFolderId.value = item.id
}

function returnToSubfolderList(): void {
  const root = subfolderPanelRoot.value
  if (!root) {
    return
  }

  hiddenDocumentResultsFolderId.value = undefined
  selectedFolderId.value = root.id
}

function canSelectSubfolder(item: FolderTreeNode): boolean {
  if (!isStaffRoot.value || authStore.isSystemAdmin) {
    return true
  }

  return item.name.trim() === (authStore.user?.real_name ?? '').trim()
}

function closeDocumentResults(): void {
  if (!canCloseDocumentResults.value) {
    return
  }
  returnToSubfolderList()
}

async function createSubfolder(): Promise<void> {
  const root = selectedPublicRootNode.value
  if (!root || !['company', 'staff'].includes(root.publicRootKey)) {
    return
  }

  const isStaff = root.publicRootKey === 'staff'
  const promptTitle = isStaff ? '添加用户' : '添加公司'
  const promptMessage = isStaff ? '请输入人员姓名' : '请输入公司名称'
  const inputPlaceholder = isStaff ? '例如：张三' : '例如：华能新能源有限公司'
  const inputValidatorMessage = isStaff ? '请填写人员姓名' : '请填写公司名称'
  const successMessage = isStaff ? '用户已添加' : '公司已添加'
  let result: { value?: string }
  try {
    result = await ElMessageBox.prompt(promptMessage, promptTitle, {
      confirmButtonText: '添加',
      cancelButtonText: '取消',
      inputPlaceholder,
      inputValidator: (value) => Boolean(value.trim()) || inputValidatorMessage,
    })
  } catch {
    return
  }

  const name = result.value?.trim()
  if (!name) {
    return
  }

  mutationLoading.value = true
  try {
    await createFolder({
      project: null,
      parent: root.id,
      name,
      code: '',
      sort_order: subfolderItems.value.length + 1,
    })
    ElMessage.success(successMessage)
    await loadFolderTree()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function deleteSubfolder(item: FolderTreeNode): Promise<void> {
  const root = selectedPublicRootNode.value
  if (!root || !canDeleteSubfolder.value) {
    return
  }

  const itemType = root.publicRootKey === 'staff' ? '人员' : '公司'
  try {
    await ElMessageBox.confirm(
      `确认删除“${item.name}”？删除后该${itemType}将不再显示。`,
      `删除${itemType}`,
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await disableFolder(item.id)
    ElMessage.success(`${itemType}已删除`)
    if (selectedFolderId.value === item.id || hasDescendant(item, selectedFolderId.value ?? -1)) {
      hiddenDocumentResultsFolderId.value = undefined
      selectedFolderId.value = root.id
    }
    await loadFolderTree()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function loadDocuments(): Promise<void> {
  if (props.fixedFolderCode && !fixedFolderNode.value) {
    documents.value = []
    total.value = 0
    listLoading.value = false
    return
  }

  if (isTopPublicFolderMode.value && selectedFolderId.value === undefined && !search.value.trim()) {
    documents.value = []
    total.value = 0
    listLoading.value = false
    return
  }

  if (isSubfolderPanelRootLanding.value || isArchiveRootLanding.value) {
    documents.value = []
    total.value = 0
    listLoading.value = false
    return
  }

  if (
    selectedPublicRootNode.value?.publicRootKey === 'entryPreparation'
    && selectedFolderId.value === selectedPublicRootNode.value.id
  ) {
    documents.value = []
    total.value = 0
    listLoading.value = false
    return
  }

  listLoading.value = true

  try {
    const query = {
      page: page.value,
      search: search.value,
      ordering: ordering.value,
      project: props.scope === 'project' ? props.projectId : undefined,
      folder: props.fixedFolderCode
        ? effectiveFolderId.value
        : shouldShowFolderNavigation.value
          ? selectedFolderId.value
          : undefined,
      source_type: props.sourceType,
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

  let successCount = 0
  let firstError: unknown
  try {
    for (const file of payload.files) {
      try {
        await uploadDocument({
          folder: payload.folder,
          file,
          title: payload.files.length === 1 ? payload.title : '',
          description: payload.description,
          access_level: payload.access_level,
          source_type: props.sourceType,
        })
        successCount += 1
      } catch (error) {
        firstError ??= error
      }
    }

    if (successCount > 0) {
      await loadDocuments()
    }

    const failedCount = payload.files.length - successCount
    if (failedCount === 0) {
      uploadVisible.value = false
      ElMessage.success(successCount > 1 ? `已上传 ${successCount} 个文件` : '上传成功')
    } else {
      ElMessage.error(
        successCount > 0
          ? `已上传 ${successCount} 个，${failedCount} 个失败：${getErrorMessage(firstError)}`
          : getErrorMessage(firstError),
      )
    }
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

async function handleFolderDownload(): Promise<void> {
  const folderId = effectiveFolderId.value
  if (folderId === undefined || folderDownloadLoading.value || centerDownloadLoading.value) {
    return
  }

  folderDownloadLoading.value = true
  try {
    await downloadFolder(folderId)
    ElMessage.success('当前页资料压缩包已下载')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    folderDownloadLoading.value = false
  }
}

async function handleCenterDownload(): Promise<void> {
  if (folderDownloadLoading.value || centerDownloadLoading.value) {
    return
  }

  centerDownloadLoading.value = true
  try {
    await downloadDocumentCenter()
    ElMessage.success('资料中心全部资料压缩包已下载')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    centerDownloadLoading.value = false
  }
}

function handleDocumentCenterDownloadCommand(command: string | number | object): void {
  if (command === 'folder') {
    void handleFolderDownload()
    return
  }

  if (command === 'center') {
    void handleCenterDownload()
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

async function handleVersionUpload(files: File[]): Promise<void> {
  if (!actionDocument.value) {
    return
  }

  mutationLoading.value = true

  let successCount = 0
  let firstError: unknown
  try {
    for (const file of files) {
      try {
        await uploadDocumentVersion(actionDocument.value.id, file)
        successCount += 1
      } catch (error) {
        firstError ??= error
      }
    }

    if (successCount > 0) {
      await loadDocuments()
    }

    const failedCount = files.length - successCount
    if (failedCount === 0) {
      versionVisible.value = false
      ElMessage.success(successCount > 1 ? `已上传 ${successCount} 个新版本` : '新版本已上传')
    } else {
      ElMessage.error(
        successCount > 0
          ? `已上传 ${successCount} 个，${failedCount} 个失败：${getErrorMessage(firstError)}`
          : getErrorMessage(firstError),
      )
    }
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
      <div
        v-if="showDocumentCenterDownloads"
        class="document-explorer__folder-download"
      >
        <el-dropdown
          :disabled="folderDownloadLoading || centerDownloadLoading"
          :trigger="['click', 'hover']"
          @command="handleDocumentCenterDownloadCommand"
        >
          <el-button
            :icon="Download"
            :loading="folderDownloadLoading || centerDownloadLoading"
            type="primary"
          >
            下载全部资料
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                command="folder"
                :disabled="
                  effectiveFolderId === undefined ||
                  folderDownloadLoading ||
                  centerDownloadLoading
                "
                :icon="Download"
              >
                一键下载当前页资料
              </el-dropdown-item>
              <el-dropdown-item
                command="center"
                :disabled="folderDownloadLoading || centerDownloadLoading"
                :icon="Download"
              >
                一键下载中心全部资料
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <slot v-if="isEntryPreparationSelection" name="entry-preparation" />

      <section
        v-if="!isEntryPreparationSelection && subfolderPanelRoot"
        class="document-subfolder-panel"
        :class="{
          'document-subfolder-panel--company': subfolderPanelRoot?.publicRootKey === 'company',
          'document-subfolder-panel--staff': subfolderPanelRoot?.publicRootKey === 'staff',
        }"
        :aria-label="subfolderPanelTitle"
      >
        <header class="document-subfolder-panel__header">
          <h2>{{ subfolderPanelTitle }}</h2>
          <div class="document-subfolder-panel__meta">
            <span v-if="!isSubfolderDetailMode">{{ subfolderPanelCountText }}</span>
            <el-button v-else size="small" @click="returnToSubfolderList">返回名单</el-button>
            <el-button
              v-if="canCreateSubfolder && !isSubfolderDetailMode"
              :loading="mutationLoading"
              size="small"
              type="primary"
              @click="createSubfolder"
            >
              {{ subfolderCreateButtonText }}
            </el-button>
          </div>
        </header>

        <div
          v-if="visibleSubfolderItems.length > 0"
          class="document-subfolder-panel__grid"
          :class="{ 'document-subfolder-panel__grid--detail': isSubfolderDetailMode }"
        >
          <div
            v-for="item in visibleSubfolderItems"
            :key="item.id"
            class="document-subfolder-panel__item"
            :class="{
              'is-active': selectedFolderId === item.id,
              'is-disabled': !canSelectSubfolder(item),
            }"
          >
            <button
              class="document-subfolder-panel__select"
              :disabled="!canSelectSubfolder(item)"
              type="button"
              @click="selectSubfolderItem(item)"
            >
              {{ item.name }}
            </button>
            <el-button
              v-if="canDeleteSubfolder"
              :icon="Delete"
              aria-label="删除子项"
              circle
              class="document-subfolder-panel__delete"
              text
              title="删除"
              @click="deleteSubfolder(item)"
            />
          </div>
        </div>

        <el-empty
          v-else
          :description="subfolderPanelEmptyText"
          :image-size="72"
        />
      </section>

      <div
        v-if="!isEntryPreparationSelection && shouldShowDocumentResults"
        class="document-explorer__actions"
      >
        <DocumentSearchPanel
          v-model:ordering="ordering"
          v-model:search="search"
          :loading="listLoading"
          @reset="resetFilters"
          @submit="submitSearch"
        />

        <div class="document-explorer__toolbar">
          <el-button
            v-if="canUpload"
            type="primary"
            @click="uploadVisible = true"
          >
            上传资料
          </el-button>
          <RouterLink v-if="!isTrashMode" to="/documents/recycle-bin">回收站</RouterLink>
          <RouterLink v-else to="/documents">返回资料中心</RouterLink>
          <el-button
            v-if="canCloseDocumentResults"
            :icon="Close"
            aria-label="关闭模块"
            class="document-explorer__close-results"
            circle
            text
            title="关闭"
            @click="closeDocumentResults"
          />
        </div>
      </div>

      <DocumentTable
        v-if="!isEntryPreparationSelection && shouldShowDocumentResults"
        :documents="documents"
        :fixed-actions="folderLayout !== 'top'"
        :height="folderLayout === 'top' ? 480 : undefined"
        :loading="listLoading"
        :mode="props.mode"
        :read-only="isArchiveYearSelected"
        :show-project="isArchiveYearSelected || isTechnicalSolutionSelection"
        @delete="handleDelete"
        @download="handleDownload"
        @edit="openEditDialog"
        @move="openMoveDialog"
        @restore="handleRestore"
        @version="openVersionDialog"
        @view="openDocumentDetail"
      />

      <el-empty
        v-if="
          !isEntryPreparationSelection
          && shouldShowDocumentResults
          && isEmpty
          && folderLayout !== 'top'
        "
        description="暂无资料"
      />

      <footer
        v-if="!isEntryPreparationSelection && shouldShowDocumentResults"
        class="document-explorer__pagination"
      >
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
      :folders="mutationFolderTree"
      :initial-folder-id="effectiveFolderId"
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
      :folders="mutationFolderTree"
      :loading="mutationLoading"
      :public-root-only="shouldMoveToPublicRootsOnly"
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
