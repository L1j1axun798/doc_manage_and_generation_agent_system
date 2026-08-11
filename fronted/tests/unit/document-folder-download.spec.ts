import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'

import DocumentExplorer from '@/modules/documents/components/DocumentExplorer.vue'
import type { FolderTreeNode } from '@/modules/documents/documents.types'

const documentApi = vi.hoisted(() => ({
  cancelArchiveDownload: vi.fn(),
  deleteDocument: vi.fn(),
  downloadDocument: vi.fn(),
  downloadDocumentCenter: vi.fn(),
  downloadFolder: vi.fn(),
  fetchDocument: vi.fn(),
  fetchDocuments: vi.fn(),
  fetchTrashDocuments: vi.fn(),
  moveDocument: vi.fn(),
  restoreDocument: vi.fn(),
  updateDocument: vi.fn(),
  uploadDocument: vi.fn(),
  uploadDocumentVersion: vi.fn(),
}))

const folderApi = vi.hoisted(() => ({
  createFolder: vi.fn(),
  disableFolder: vi.fn(),
  fetchFolderTree: vi.fn(),
}))

vi.mock('@/modules/documents/api/documents.api', () => documentApi)
vi.mock('@/modules/documents/api/folders.api', () => folderApi)

afterEach(() => {
  vi.restoreAllMocks()
  vi.clearAllMocks()
})

it('keeps both download scopes in one click-or-hover dropdown without duplicate commands', async () => {
  const root: FolderTreeNode = {
    id: 7,
    project: null,
    parent: null,
    name: '工器具及年检资质',
    code: 'PUBLIC-TOOLS',
    sort_order: 1,
    is_active: true,
    is_system_root: true,
    children: [],
  }
  folderApi.fetchFolderTree.mockResolvedValue([root])
  documentApi.fetchDocuments.mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  })
  let resolveDownload: (() => void) | undefined
  let resolveCenterDownload: (() => void) | undefined
  let reportFolderProgress: ((percentage: number | null) => void) | undefined
  let reportCenterProgress: ((percentage: number | null) => void) | undefined
  let folderSignal: AbortSignal | undefined
  let centerSignal: AbortSignal | undefined
  let folderDownloadId: string | undefined
  let centerDownloadId: string | undefined
  documentApi.downloadFolder.mockImplementation(
    (
      _folderId: number,
      onProgress?: (percentage: number | null) => void,
      signal?: AbortSignal,
      downloadId?: string,
    ) => new Promise<void>((resolve) => {
      resolveDownload = resolve
      reportFolderProgress = onProgress
      folderSignal = signal
      folderDownloadId = downloadId
      onProgress?.(24)
    }),
  )
  documentApi.downloadDocumentCenter.mockImplementation(
    (
      onProgress?: (percentage: number | null) => void,
      signal?: AbortSignal,
      downloadId?: string,
    ) => new Promise<void>((resolve) => {
      resolveCenterDownload = resolve
      reportCenterProgress = onProgress
      centerSignal = signal
      centerDownloadId = downloadId
      onProgress?.(null)
    }),
  )

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: {
          components: { DocumentExplorer },
          template: '<DocumentExplorer folder-layout="top" scope="public" />',
        },
      },
      { path: '/documents', component: { template: '<div />' } },
      { path: '/documents/recycle-bin', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [createPinia(), router, ElementPlus],
      },
    },
  )
  await flushPromises()

  const dropdown = wrapper.findComponent({ name: 'ElDropdown' })
  const downloadItems = wrapper.findAllComponents({ name: 'ElDropdownItem' })
  const mainButton = wrapper.findAll('button').find((button) => button.text() === '下载全部资料')

  expect(mainButton).toBeDefined()
  expect(dropdown.props('trigger')).toEqual(['click', 'hover'])
  expect(downloadItems.map((item) => item.text())).toEqual([
    '一键下载当前页资料',
    '一键下载中心全部资料',
  ])

  dropdown.vm.$emit('command', 'folder')
  await flushPromises()

  expect(documentApi.downloadFolder).toHaveBeenCalledTimes(1)
  expect(documentApi.downloadFolder).toHaveBeenCalledWith(
    7,
    expect.any(Function),
    expect.any(AbortSignal),
    expect.any(String),
  )
  expect(folderSignal?.aborted).toBe(false)
  expect(folderDownloadId).toMatch(/^[0-9a-f-]{36}$/)
  expect(wrapper.findComponent({ name: 'ElDropdown' }).exists()).toBe(false)
  expect(wrapper.findComponent({ name: 'ElProgress' }).props('percentage')).toBe(24)
  expect(wrapper.text()).toContain('正在下载当前页资料')
  expect(wrapper.text()).toContain('24%')

  reportFolderProgress?.(68)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ElProgress' }).props('percentage')).toBe(68)
  expect(wrapper.text()).toContain('68%')

  resolveDownload?.()
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ElDropdown' }).exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'ElProgress' }).exists()).toBe(false)

  wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'center')
  await flushPromises()
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledTimes(1)
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledWith(
    expect.any(Function),
    expect.any(AbortSignal),
    expect.any(String),
  )
  expect(centerSignal?.aborted).toBe(false)
  expect(centerDownloadId).toMatch(/^[0-9a-f-]{36}$/)
  expect(wrapper.findComponent({ name: 'ElDropdown' }).exists()).toBe(false)
  expect(wrapper.findComponent({ name: 'ElProgress' }).props('indeterminate')).toBe(true)
  expect(wrapper.text()).toContain('正在下载中心全部资料')
  expect(wrapper.text()).toContain('正在准备压缩包')

  reportCenterProgress?.(51)
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ElProgress' }).props('indeterminate')).toBe(false)
  expect(wrapper.findComponent({ name: 'ElProgress' }).props('percentage')).toBe(51)
  expect(wrapper.text()).toContain('51%')

  resolveCenterDownload?.()
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ElDropdown' }).exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'ElProgress' }).exists()).toBe(false)
  wrapper.unmount()
})

it('blocks navigation during a center download and aborts the request after confirmation', async () => {
  const root: FolderTreeNode = {
    id: 7,
    project: null,
    parent: null,
    name: '工器具及年检资质',
    code: 'PUBLIC-TOOLS',
    sort_order: 1,
    is_active: true,
    is_system_root: true,
    children: [],
  }
  folderApi.fetchFolderTree.mockResolvedValue([root])
  documentApi.fetchDocuments.mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  })

  let downloadSignal: AbortSignal | undefined
  let downloadId: string | undefined
  documentApi.cancelArchiveDownload.mockResolvedValue(undefined)
  documentApi.downloadDocumentCenter.mockImplementation(
    (
      _onProgress?: (percentage: number | null) => void,
      signal?: AbortSignal,
      requestDownloadId?: string,
    ) => (
      new Promise<void>((_resolve, reject) => {
        downloadSignal = signal
        downloadId = requestDownloadId
        signal?.addEventListener(
          'abort',
          () => reject({ code: 'ERR_CANCELED', detail: 'canceled' }),
          { once: true },
        )
      })
    ),
  )

  const confirm = vi.spyOn(ElMessageBox, 'confirm')
    .mockRejectedValueOnce('cancel')
    .mockResolvedValueOnce('confirm')
  const errorMessage = vi.spyOn(ElMessage, 'error')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: {
          components: { DocumentExplorer },
          template: '<DocumentExplorer folder-layout="top" scope="public" />',
        },
      },
      { path: '/other', component: { template: '<div>Other page</div>' } },
      { path: '/documents/recycle-bin', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [createPinia(), router, ElementPlus],
      },
    },
  )
  await flushPromises()

  wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'center')
  await flushPromises()
  expect(downloadSignal?.aborted).toBe(false)

  await router.push('/other')
  expect(router.currentRoute.value.path).toBe('/')
  expect(downloadSignal?.aborted).toBe(false)
  expect(confirm).toHaveBeenNthCalledWith(
    1,
    '你在下载资料中心资料，切换页面会导致中断！是否离开？',
    '下载尚未完成',
    expect.objectContaining({
      confirmButtonText: '离开并中断下载',
      cancelButtonText: '继续下载',
    }),
  )

  await router.push('/other')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/other')
  expect(downloadSignal?.aborted).toBe(true)
  expect(documentApi.cancelArchiveDownload).toHaveBeenCalledWith(downloadId)
  expect(errorMessage).not.toHaveBeenCalled()
  wrapper.unmount()
})
