import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import DashboardPage from '@/modules/dashboard/pages/DashboardPage.vue'

const mocks = vi.hoisted(() => ({
  fetchDashboardCounts: vi.fn(),
  fetchRagOverview: vi.fn(),
  fetchAdminLatestLocations: vi.fn(),
  fetchMyLatestLocation: vi.fn(),
  createLocationReportChallenge: vi.fn(),
  authenticateWithWebAuthn: vi.fn(),
  locateCurrentUser: vi.fn(),
  reportLocation: vi.fn(),
}))

vi.mock('@/modules/dashboard/api/dashboard.api', () => ({
  fetchDashboardCounts: mocks.fetchDashboardCounts,
}))

vi.mock('@/modules/document-generation/api/document-generation.api', () => ({
  fetchRagOverview: mocks.fetchRagOverview,
}))

vi.mock('@/modules/locations/api/locations.api', () => ({
  createLocationReportChallenge: mocks.createLocationReportChallenge,
  fetchAdminLatestLocations: mocks.fetchAdminLatestLocations,
  fetchMyLatestLocation: mocks.fetchMyLatestLocation,
  reportLocation: mocks.reportLocation,
}))

vi.mock('@/modules/auth/services/webauthn', () => ({
  authenticateWithWebAuthn: mocks.authenticateWithWebAuthn,
}))

vi.mock('@/modules/locations/services/location-provider', () => ({
  locateCurrentUser: mocks.locateCurrentUser,
}))

const baseUser: AuthUser = {
  id: 1,
  username: 'operator',
  real_name: '资料员',
  employee_no: null,
  role: 'data_operator',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
  created_at: '2026-07-30T08:00:00+08:00',
}

function makeLocationSnapshot() {
  return {
    user: {
      id: 1,
      username: 'operator',
      real_name: '资料员',
      employee_no: null,
      role: 'data_operator',
      phone: '',
    },
    latest_report: null,
    location_status: 'today_unreported' as const,
    should_report: false,
  }
}

function makeRagOverview(withOperations: boolean) {
  return {
    knowledge_status: 'ready' as const,
    knowledge_chunks: 948,
    source_documents: 27,
    covered_section_count: 8,
    total_section_count: 8,
    section_coverage: [
      { code: 'overview' as const, name: '工程概况与编制依据', chunk_count: 82 },
      { code: 'technical_measures' as const, name: '技术措施', chunk_count: 81 },
    ],
    last_indexed_at: '2026-07-30T11:11:26+08:00',
    embedding_model_alias: 'text-embedding-v4',
    embedding_dimension: 1024,
    operations: withOperations
      ? {
          status: 'healthy' as const,
          redis_status: 'ok' as const,
          worker_status: 'idle' as const,
          queue_depth: 0,
          processing_uploads: 0,
          failed_uploads: 0,
          latest_upload_status: 'succeeded' as const,
          latest_upload_at: '2026-07-30T11:11:26+08:00',
        }
      : null,
  }
}

function mountDashboard(user: AuthUser) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.user = user
  authStore.status = 'authenticated'
  authStore.initialized = true
  return mount(DashboardPage, {
    global: {
      plugins: [pinia, ElementPlus],
      stubs: {
        PersonnelLocationMap: {
          template: '<div data-test="personnel-map" />',
        },
        RouterLink: {
          template: '<a><slot /></a>',
        },
      },
    },
  })
}

describe('dashboard location and RAG overview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchDashboardCounts.mockResolvedValue({
      visibleDocuments: 0,
      myProjects: 0,
      unreadNotifications: 0,
      activeGrants: 0,
    })
    mocks.fetchMyLatestLocation.mockResolvedValue(makeLocationSnapshot())
    mocks.fetchAdminLatestLocations.mockResolvedValue([makeLocationSnapshot()])
    mocks.fetchRagOverview.mockResolvedValue(makeRagOverview(false))
  })

  it('does not submit a failed report for environment precheck failures', async () => {
    mocks.locateCurrentUser.mockResolvedValue({
      ok: false,
      code: 'insecure_origin',
      message: '当前访问地址不是安全源',
      shouldReportFailure: false,
    })

    const wrapper = mountDashboard(baseUser)
    await flushPromises()

    const reportButton = wrapper.findAll('button').find((button) =>
      button.text().includes('上报当前位置'),
    )
    await reportButton!.trigger('click')
    await flushPromises()

    expect(mocks.locateCurrentUser).toHaveBeenCalledTimes(1)
    expect(mocks.createLocationReportChallenge).not.toHaveBeenCalled()
    expect(mocks.authenticateWithWebAuthn).not.toHaveBeenCalled()
    expect(mocks.reportLocation).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('shows the personnel map and runtime operations only to system administrators', async () => {
    mocks.fetchRagOverview.mockResolvedValue(makeRagOverview(true))
    const wrapper = mountDashboard({
      ...baseUser,
      username: 'admin',
      real_name: '系统管理员',
      role: 'system_admin',
    })
    await flushPromises()

    expect(mocks.fetchAdminLatestLocations).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-test="personnel-map"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('人员位置概览')
    expect(wrapper.text()).toContain('运行状态')
    expect(wrapper.text()).toContain('Worker')
    expect(wrapper.text()).toContain('948')
    wrapper.unmount()
  })

  it('keeps personnel data private while showing the business RAG summary to ordinary users', async () => {
    const wrapper = mountDashboard(baseUser)
    await flushPromises()

    expect(mocks.fetchAdminLatestLocations).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="personnel-map"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('人员位置概览')
    expect(wrapper.text()).not.toContain('运行状态')
    expect(wrapper.text()).toContain('RAG 知识库概览')
    expect(wrapper.text()).toContain('27')
    wrapper.unmount()
  })
})
