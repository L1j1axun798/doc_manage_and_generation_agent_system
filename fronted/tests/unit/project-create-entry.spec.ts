import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import ProjectFormDialog from '@/modules/projects/components/ProjectFormDialog.vue'
import ProjectListPage from '@/modules/projects/pages/ProjectListPage.vue'

const mocks = vi.hoisted(() => ({
  createProject: vi.fn(),
  fetchProjects: vi.fn(),
  routerReplace: vi.fn(),
  routeQuery: { action: 'create' } as Record<string, string>,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mocks.routeQuery }),
  useRouter: () => ({
    push: vi.fn(),
    replace: mocks.routerReplace,
  }),
}))

vi.mock('@/modules/projects/api/projects.api', () => ({
  createProject: mocks.createProject,
  deleteProject: vi.fn(),
  fetchProjects: mocks.fetchProjects,
  updateProject: vi.fn(),
}))

const regularUser: AuthUser = {
  id: 1,
  username: 'operator',
  real_name: '资料整理员',
  employee_no: 'A001',
  role: 'data_operator',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
  created_at: '2026-08-06T08:00:00+08:00',
}

describe('project creation entry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.routeQuery.action = 'create'
    mocks.fetchProjects.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.createProject.mockResolvedValue({})
  })

  it('opens the existing form from the Agent route and uses the unified success message', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const authStore = useAuthStore()
    authStore.user = regularUser
    authStore.status = 'authenticated'
    authStore.initialized = true
    const successSpy = vi.spyOn(ElMessage, 'success')

    const wrapper = mount(ProjectListPage, {
      global: { plugins: [pinia, ElementPlus] },
    })
    await flushPromises()

    const form = wrapper.getComponent(ProjectFormDialog)
    expect(form.props('modelValue')).toBe(true)
    expect(form.props('allowManagerChange')).toBe(false)
    expect(wrapper.text()).toContain('创建项目')
    expect(mocks.routerReplace).toHaveBeenCalledWith({ name: 'projects', query: {} })

    form.vm.$emit('submit', {
      name: '新建风电项目',
      code: 'WF-NEW',
      description: '',
      manager: 1,
      status: 'active',
    })
    await flushPromises()

    expect(mocks.createProject).toHaveBeenCalledOnce()
    expect(successSpy).toHaveBeenCalledWith('创建成功🎉现在可以去生成四措两案了~')
    wrapper.unmount()
  })
})
