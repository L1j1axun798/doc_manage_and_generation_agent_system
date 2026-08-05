import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'

import DocumentExplorer from '@/modules/documents/components/DocumentExplorer.vue'
import type { FolderTreeNode } from '@/modules/documents/documents.types'

const documentApi = vi.hoisted(() => ({
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
  vi.clearAllMocks()
})

it('supports current-page and center-wide downloads without duplicate clicks', async () => {
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
  documentApi.downloadFolder.mockImplementation(
    () => new Promise<void>((resolve) => {
      resolveDownload = resolve
    }),
  )
  documentApi.downloadDocumentCenter.mockImplementation(
    () => new Promise<void>((resolve) => {
      resolveCenterDownload = resolve
    }),
  )

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/documents', component: { template: '<div />' } },
      { path: '/documents/recycle-bin', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()
  const wrapper = mount(DocumentExplorer, {
    props: {
      folderLayout: 'top',
      scope: 'public',
    },
    global: {
      plugins: [createPinia(), router, ElementPlus],
    },
  })
  await flushPromises()

  const downloadButton = wrapper.findAll('button').find(
    (button) => button.text().includes('一键下载当前页资料'),
  )
  const centerDownloadButton = wrapper.findAll('button').find(
    (button) => button.text().includes('一键下载中心全部资料'),
  )
  expect(downloadButton).toBeDefined()
  expect(centerDownloadButton).toBeDefined()
  await downloadButton?.trigger('click')
  await flushPromises()

  expect(documentApi.downloadFolder).toHaveBeenCalledTimes(1)
  expect(documentApi.downloadFolder).toHaveBeenCalledWith(7)
  expect(downloadButton?.attributes('disabled')).toBeDefined()
  expect(centerDownloadButton?.attributes('disabled')).toBeDefined()
  await downloadButton?.trigger('click')
  expect(documentApi.downloadFolder).toHaveBeenCalledTimes(1)

  resolveDownload?.()
  await flushPromises()
  expect(downloadButton?.attributes('disabled')).toBeUndefined()
  expect(centerDownloadButton?.attributes('disabled')).toBeUndefined()

  await centerDownloadButton?.trigger('click')
  await flushPromises()
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledTimes(1)
  expect(downloadButton?.attributes('disabled')).toBeDefined()
  expect(centerDownloadButton?.attributes('disabled')).toBeDefined()
  await centerDownloadButton?.trigger('click')
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledTimes(1)

  resolveCenterDownload?.()
  await flushPromises()
  expect(downloadButton?.attributes('disabled')).toBeUndefined()
  expect(centerDownloadButton?.attributes('disabled')).toBeUndefined()
  wrapper.unmount()
})
