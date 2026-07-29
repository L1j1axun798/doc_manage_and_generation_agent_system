import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import DocumentGenerationPage from '@/modules/document-generation/pages/DocumentGenerationPage.vue'

const mocks = vi.hoisted(() => ({
  fetchProjects: vi.fn(),
  fetchKnowledgeCorpusUploads: vi.fn(),
}))

vi.mock('@/modules/projects/api/projects.api', () => ({
  fetchProjects: mocks.fetchProjects,
}))

vi.mock('@/modules/document-generation/api/document-generation.api', () => ({
  fetchKnowledgeCorpusUploads: mocks.fetchKnowledgeCorpusUploads,
  retryKnowledgeCorpusUpload: vi.fn(),
  uploadKnowledgeCorpus: vi.fn(),
}))

const baseUser: AuthUser = {
  id: 1,
  username: 'admin',
  real_name: '系统管理员',
  employee_no: 'A001',
  role: 'system_admin',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
  created_at: '2026-07-29T08:00:00+08:00',
}

function mountPage(user: AuthUser) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.user = user
  authStore.status = 'authenticated'
  authStore.initialized = true
  return mount(DocumentGenerationPage, {
    global: {
      plugins: [pinia, ElementPlus],
      stubs: {
        DocumentGenerationPanel: true,
      },
    },
  })
}

describe('document generation RAG corpus upload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchProjects.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchKnowledgeCorpusUploads.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
  })

  it('shows the upload entry to system administrators and opens the status dialog', async () => {
    const wrapper = mountPage(baseUser)
    await flushPromises()

    const uploadButton = wrapper.findAll('button').find((button) =>
      button.text().includes('上传 RAG 资料'),
    )
    expect(uploadButton).toBeDefined()
    await uploadButton!.trigger('click')
    await flushPromises()

    expect(mocks.fetchKnowledgeCorpusUploads).toHaveBeenCalled()
    expect(document.body.textContent).toContain('工程概况与编制依据')
    const selectAll = wrapper.findComponent({ name: 'ElCheckbox' })
    expect(selectAll.exists()).toBe(true)
    expect(selectAll.text()).toBe('全选')
    expect(selectAll.props('modelValue')).toBe(true)
    expect(document.body.textContent).not.toContain('甲方编码')
    expect(document.body.textContent).not.toContain('部件标签')
    expect(document.body.textContent).not.toContain('检测方法标签')
    expect(document.body.textContent).not.toContain('风险标签')
    wrapper.unmount()
  })

  it('does not expose the upload entry to non-admin users', async () => {
    const wrapper = mountPage({
      ...baseUser,
      id: 2,
      username: 'manager',
      role: 'project_manager',
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('上传 RAG 资料')
    expect(mocks.fetchKnowledgeCorpusUploads).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
