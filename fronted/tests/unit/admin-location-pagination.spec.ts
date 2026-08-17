import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, expect, it, vi } from 'vitest'

import AdminLocationPage from '@/modules/locations/pages/AdminLocationPage.vue'
import type { LocationSnapshot } from '@/modules/locations/locations.types'

const mocks = vi.hoisted(() => ({
  fetchAdminLatestLocations: vi.fn(),
}))

vi.mock('@/modules/locations/api/locations.api', () => ({
  fetchAdminLatestLocations: mocks.fetchAdminLatestLocations,
}))

function makeSnapshot(index: number): LocationSnapshot {
  return {
    user: {
      id: index,
      username: `user-${index}`,
      real_name: `员工${index}`,
      employee_no: null,
      role: 'data_operator',
      phone: '',
    },
    latest_report: null,
    location_status: 'today_unreported',
    should_report: true,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.fetchAdminLatestLocations.mockResolvedValue(
    Array.from({ length: 21 }, (_, index) => makeSnapshot(index + 1)),
  )
})

it('paginates attention rows by 9 and location rows by 10', async () => {
  const wrapper = mount(AdminLocationPage, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        PersonnelLocationMap: {
          template: '<div class="map-stub" />',
          methods: { focusSnapshot: vi.fn() },
        },
      },
    },
  })
  await flushPromises()

  const paginations = wrapper.findAllComponents({ name: 'ElPagination' })
  const table = wrapper.findComponent({ name: 'ElTable' })

  expect(wrapper.findAll('.location-attention__item')).toHaveLength(9)
  expect(wrapper.find('.location-attention__item').text()).toContain('员工1')
  expect(paginations).toHaveLength(2)
  expect(paginations[0]?.props()).toMatchObject({ pageSize: 9, total: 21 })
  expect(table.props('data')).toHaveLength(10)
  expect(table.props('data')[0].user.id).toBe(1)
  expect(paginations[1]?.props()).toMatchObject({ pageSize: 10, total: 21 })

  paginations[0]?.vm.$emit('update:current-page', 2)
  paginations[1]?.vm.$emit('update:current-page', 2)
  await flushPromises()

  expect(wrapper.findAll('.location-attention__item')).toHaveLength(9)
  expect(wrapper.find('.location-attention__item').text()).toContain('员工10')
  expect(table.props('data')).toHaveLength(10)
  expect(table.props('data')[0].user.id).toBe(11)

  paginations[0]?.vm.$emit('update:current-page', 3)
  paginations[1]?.vm.$emit('update:current-page', 3)
  await flushPromises()

  expect(wrapper.findAll('.location-attention__item')).toHaveLength(3)
  expect(table.props('data')).toHaveLength(1)
  wrapper.unmount()
})
