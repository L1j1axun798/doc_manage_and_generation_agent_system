import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it, vi } from 'vitest'

import DashboardPage from '@/modules/dashboard/pages/DashboardPage.vue'

const mocks = vi.hoisted(() => ({
  fetchDashboardCounts: vi.fn(),
  fetchMyLatestLocation: vi.fn(),
  createLocationReportChallenge: vi.fn(),
  authenticateWithWebAuthn: vi.fn(),
  locateCurrentUser: vi.fn(),
  reportLocation: vi.fn(),
}))

vi.mock('@/modules/dashboard/api/dashboard.api', () => ({
  fetchDashboardCounts: mocks.fetchDashboardCounts,
}))

vi.mock('@/modules/locations/api/locations.api', () => ({
  createLocationReportChallenge: mocks.createLocationReportChallenge,
  fetchMyLatestLocation: mocks.fetchMyLatestLocation,
  reportLocation: mocks.reportLocation,
}))

vi.mock('@/modules/auth/services/webauthn', () => ({
  authenticateWithWebAuthn: mocks.authenticateWithWebAuthn,
}))

vi.mock('@/modules/locations/services/location-provider', () => ({
  locateCurrentUser: mocks.locateCurrentUser,
}))

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
    location_status: 'today_unreported',
    should_report: false,
  }
}

describe('dashboard location reporting', () => {
  it('does not submit a failed report for environment precheck failures', async () => {
    mocks.fetchDashboardCounts.mockResolvedValue({
      visibleDocuments: 0,
      myProjects: 0,
      unreadNotifications: 0,
      activeGrants: 0,
    })
    mocks.fetchMyLatestLocation.mockResolvedValue(makeLocationSnapshot())
    mocks.locateCurrentUser.mockResolvedValue({
      ok: false,
      code: 'insecure_origin',
      message: '当前访问地址不是安全源',
      shouldReportFailure: false,
    })

    const wrapper = mount(DashboardPage, {
      global: {
        plugins: [ElementPlus],
      },
    })
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mocks.locateCurrentUser).toHaveBeenCalledTimes(1)
    expect(mocks.createLocationReportChallenge).not.toHaveBeenCalled()
    expect(mocks.authenticateWithWebAuthn).not.toHaveBeenCalled()
    expect(mocks.reportLocation).not.toHaveBeenCalled()
  })
})
