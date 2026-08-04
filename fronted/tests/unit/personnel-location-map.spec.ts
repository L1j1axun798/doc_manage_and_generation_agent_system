import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PersonnelLocationMap from '@/modules/locations/components/PersonnelLocationMap.vue'
import type { LocationSnapshot } from '@/modules/locations/locations.types'

const mocks = vi.hoisted(() => ({
  load: vi.fn(),
  mapOptions: [] as Array<Record<string, unknown>>,
  markerOptions: [] as Array<Record<string, unknown>>,
  markerClickHandlers: [] as Array<() => void>,
  add: vi.fn(),
  addControl: vi.fn(),
  clearMap: vi.fn(),
  destroy: vi.fn(),
  setFitView: vi.fn(),
  setMapStyle: vi.fn(),
  setStatus: vi.fn(),
  setZoomAndCenter: vi.fn(),
}))

vi.mock('@amap/amap-jsapi-loader', () => ({
  default: {
    load: mocks.load,
  },
}))

vi.mock('@/config/env', () => ({
  env: {
    amapKey: 'test-amap-key',
    amapSecurityJsCode: 'test-security-code',
  },
}))

function makeSnapshot(): LocationSnapshot {
  return {
    user: {
      id: 1,
      username: 'operator',
      real_name: '资料员',
      employee_no: null,
      role: 'data_operator',
      phone: '',
    },
    latest_report: {
      id: 1,
      longitude: '116.397128',
      latitude: '39.916527',
      accuracy: '20.00',
      address: '北京市东城区',
      report_status: 'success',
      failure_reason: '',
      reported_at: '2026-07-30T10:00:00+08:00',
      created_at: '2026-07-30T10:00:00+08:00',
    },
    location_status: 'normal',
    should_report: false,
  }
}

describe('personnel location map', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.mapOptions.length = 0
    mocks.markerOptions.length = 0
    mocks.markerClickHandlers.length = 0

    class FakeMap {
      add = mocks.add
      addControl = mocks.addControl
      clearMap = mocks.clearMap
      destroy = mocks.destroy
      setFitView = mocks.setFitView
      setMapStyle = mocks.setMapStyle
      setStatus = mocks.setStatus
      setZoomAndCenter = mocks.setZoomAndCenter

      constructor(_container: HTMLElement, options: Record<string, unknown>) {
        mocks.mapOptions.push(options)
      }
    }

    class FakeMarker {
      constructor(options: Record<string, unknown>) {
        mocks.markerOptions.push(options)
      }

      on(_event: 'click', handler: () => void) {
        mocks.markerClickHandlers.push(handler)
      }

      getPosition() {
        return [116.397128, 39.916527]
      }
    }

    mocks.load.mockResolvedValue({
      Map: FakeMap,
      Marker: FakeMarker,
      InfoWindow: class {
        setContent() {}
        open() {}
      },
      Pixel: class {},
      Scale: class {},
      ToolBar: class {},
    })
  })

  it('renders a compact non-interactive overview map', async () => {
    const wrapper = mount(PersonnelLocationMap, {
      props: {
        snapshots: [makeSnapshot()],
        variant: 'overview',
      },
      global: {
        plugins: [ElementPlus],
      },
    })
    await flushPromises()

    expect(mocks.mapOptions[0]).toMatchObject({
      dragEnable: false,
      scrollWheel: false,
      touchZoom: false,
      zoomEnable: false,
    })
    expect(mocks.markerOptions[0]?.clickable).toBe(false)
    expect(String(mocks.markerOptions[0]?.content)).toContain('personnel-location-map-marker')
    expect(mocks.markerClickHandlers).toHaveLength(0)
    expect(mocks.setFitView).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('preserves full-map interaction and external row focusing', async () => {
    const snapshot = makeSnapshot()
    const wrapper = mount(PersonnelLocationMap, {
      props: {
        snapshots: [snapshot],
      },
      global: {
        plugins: [ElementPlus],
      },
    })
    await flushPromises()

    expect(mocks.mapOptions[0]).toMatchObject({
      dragEnable: true,
      scrollWheel: true,
      touchZoom: true,
      zoomEnable: true,
    })
    expect(mocks.markerOptions[0]?.clickable).toBe(true)
    expect(mocks.markerClickHandlers).toHaveLength(1)

    ;(wrapper.vm as unknown as { focusSnapshot: (value: LocationSnapshot) => void })
      .focusSnapshot(snapshot)
    expect(mocks.setZoomAndCenter).toHaveBeenCalledWith(
      15,
      [116.397128, 39.916527],
    )
    wrapper.unmount()
  })

  it('renders after an asynchronous location request finishes loading', async () => {
    const wrapper = mount(PersonnelLocationMap, {
      props: {
        loading: true,
        snapshots: [],
        variant: 'overview',
      },
      global: {
        plugins: [ElementPlus],
      },
    })
    await flushPromises()
    expect(mocks.load).not.toHaveBeenCalled()

    await wrapper.setProps({
      loading: true,
      snapshots: [makeSnapshot()],
    })
    await flushPromises()
    expect(mocks.load).not.toHaveBeenCalled()

    await wrapper.setProps({ loading: false })
    await flushPromises()
    expect(mocks.load).toHaveBeenCalledTimes(1)
    expect(mocks.markerOptions).toHaveLength(1)
    wrapper.unmount()
  })
})
