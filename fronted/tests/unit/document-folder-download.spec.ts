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
  expect(documentApi.downloadFolder).toHaveBeenCalledWith(7)
  expect(dropdown.props('disabled')).toBe(true)
  expect(downloadItems[0]?.props('disabled')).toBe(true)
  expect(downloadItems[1]?.props('disabled')).toBe(true)
  dropdown.vm.$emit('command', 'folder')
  expect(documentApi.downloadFolder).toHaveBeenCalledTimes(1)

  resolveDownload?.()
  await flushPromises()
  expect(dropdown.props('disabled')).toBe(false)
  expect(downloadItems[0]?.props('disabled')).toBe(false)
  expect(downloadItems[1]?.props('disabled')).toBe(false)

  dropdown.vm.$emit('command', 'center')
  await flushPromises()
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledTimes(1)
  expect(dropdown.props('disabled')).toBe(true)
  expect(downloadItems[0]?.props('disabled')).toBe(true)
  expect(downloadItems[1]?.props('disabled')).toBe(true)
  dropdown.vm.$emit('command', 'center')
  expect(documentApi.downloadDocumentCenter).toHaveBeenCalledTimes(1)

  resolveCenterDownload?.()
  await flushPromises()
  expect(dropdown.props('disabled')).toBe(false)
  expect(downloadItems[0]?.props('disabled')).toBe(false)
  expect(downloadItems[1]?.props('disabled')).toBe(false)
  wrapper.unmount()
})
