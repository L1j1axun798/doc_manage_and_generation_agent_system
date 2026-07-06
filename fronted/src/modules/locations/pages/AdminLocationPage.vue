<script setup lang="ts">
import AMapLoader from '@amap/amap-jsapi-loader'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { env } from '@/config/env'
import { getErrorMessage } from '@/core/http/error-normalizer'
import { formatDateTime } from '@/shared/utils/format'
import { fetchAdminLatestLocations } from '../api/locations.api'
import type { LocationSnapshot, LocationStatus } from '../locations.types'
import {
  getAttentionLocations,
  getLocationDisplayAddress,
  getLocationStatusLabel,
  getLocationStatusTagType,
  hasAmapConfig,
  hasUsableCoordinates,
} from '../utils/location-status'

type MapPosition = [number, number]

interface AMapMarker {
  on(event: 'click', handler: () => void): void
  getPosition(): unknown
}

interface AMapInfoWindow {
  setContent(content: string): void
  open(map: AMapMap, position: unknown): void
}

interface AMapMap {
  add(markers: AMapMarker[]): void
  addControl(control: unknown): void
  clearMap(): void
  destroy(): void
  setFitView(
    markers: AMapMarker[],
    immediately?: boolean,
    avoid?: number[],
    maxZoom?: number,
  ): void
  setStatus(status: {
    doubleClickZoom: boolean
    dragEnable: boolean
    keyboardEnable: boolean
    scrollWheel: boolean
    touchZoom: boolean
    zoomEnable: boolean
  }): void
  setZoomAndCenter(zoom: number, position: MapPosition): void
}

interface AMapNamespace {
  Map: new (
    container: HTMLElement,
    options: {
      center: MapPosition
      doubleClickZoom: boolean
      dragEnable: boolean
      jogEnable: boolean
      keyboardEnable: boolean
      resizeEnable: boolean
      rotateEnable: boolean
      scrollWheel: boolean
      touchZoom: boolean
      zoom: number
      zoomEnable: boolean
      zooms: [number, number]
    },
  ) => AMapMap
  Marker: new (options: {
    anchor: 'bottom-center'
    bubble: boolean
    clickable: boolean
    content: string
    cursor: string
    draggable: boolean
    position: MapPosition
    title: string
    topWhenClick: boolean
  }) => AMapMarker
  InfoWindow: new (options: { offset: unknown }) => AMapInfoWindow
  Pixel: new (x: number, y: number) => unknown
  Scale: new () => unknown
  ToolBar: new (options?: { position?: { top?: string; right?: string } }) => unknown
}

const CHINA_CENTER: MapPosition = [104.195397, 35.86166]
const CHINA_OVERVIEW_ZOOM = 4
const MAX_FIT_VIEW_ZOOM = 14
const SELECTED_EMPLOYEE_ZOOM = 15
const MAP_ZOOM_RANGE: [number, number] = [3, 18]

const snapshots = ref<LocationSnapshot[]>([])
const loading = ref(false)
const mapContainer = ref<HTMLElement | null>(null)
const mapMessage = ref('')
const amapReady = computed(() => hasAmapConfig(env.amapKey))
const attentionLocations = computed(() => getAttentionLocations(snapshots.value))
const markerSnapshots = computed(() => snapshots.value.filter(hasUsableCoordinates))

const statusCounts = computed<Record<LocationStatus | 'total', number>>(() => {
  const counts: Record<LocationStatus | 'total', number> = {
    total: snapshots.value.length,
    normal: 0,
    expired: 0,
    today_unreported: 0,
    locate_failed: 0,
  }
  snapshots.value.forEach((snapshot) => {
    counts[snapshot.location_status] += 1
  })
  return counts
})

let amap: AMapNamespace | null = null
let map: AMapMap | null = null
let infoWindow: AMapInfoWindow | null = null
let markers: AMapMarker[] = []
let mapControlsInstalled = false

onMounted(async () => {
  await loadLocations()
})

onBeforeUnmount(() => {
  if (map) {
    map.destroy()
  }
})

async function loadLocations(): Promise<void> {
  loading.value = true
  try {
    snapshots.value = await fetchAdminLatestLocations()
    await nextTick()
    await renderMap()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function renderMap(): Promise<void> {
  if (!amapReady.value) {
    mapMessage.value = '未配置高德地图 Key，当前仅显示人员列表和坐标信息'
    return
  }

  if (!mapContainer.value) {
    return
  }

  if (markerSnapshots.value.length === 0) {
    mapMessage.value = '暂无可展示在地图上的上报坐标'
    return
  }

  try {
    if (!amap) {
      if (env.amapSecurityJsCode) {
        window._AMapSecurityConfig = {
          securityJsCode: env.amapSecurityJsCode,
        }
      }
      amap = await AMapLoader.load({
        key: env.amapKey,
        version: '2.0',
        plugins: ['AMap.ToolBar', 'AMap.Scale'],
      }) as AMapNamespace
    }

    if (!map) {
      map = new amap.Map(mapContainer.value, {
        center: CHINA_CENTER,
        doubleClickZoom: true,
        dragEnable: true,
        jogEnable: true,
        keyboardEnable: true,
        resizeEnable: true,
        rotateEnable: false,
        scrollWheel: true,
        touchZoom: true,
        zoom: CHINA_OVERVIEW_ZOOM,
        zoomEnable: true,
        zooms: MAP_ZOOM_RANGE,
      })
      enableMapInteraction()
      installMapControls()
      infoWindow = new amap.InfoWindow({ offset: new amap.Pixel(0, -58) })
    }

    if (!map || !infoWindow) {
      return
    }

    map.clearMap()
    markers = markerSnapshots.value.map((snapshot) => createMarker(snapshot))
    if (markers.length > 0) {
      map.add(markers)
      map.setFitView(markers, false, [90, 90, 90, 90], MAX_FIT_VIEW_ZOOM)
    }
    mapMessage.value = ''
  } catch (error) {
    mapMessage.value = getErrorMessage(error) || '地图加载失败'
  }
}

function installMapControls(): void {
  if (!amap || !map || mapControlsInstalled) {
    return
  }

  map.addControl(new amap.ToolBar({ position: { top: '16px', right: '16px' } }))
  map.addControl(new amap.Scale())
  mapControlsInstalled = true
}

function enableMapInteraction(): void {
  if (!map) {
    return
  }

  map.setStatus({
    doubleClickZoom: true,
    dragEnable: true,
    keyboardEnable: true,
    scrollWheel: true,
    touchZoom: true,
    zoomEnable: true,
  })
}

function createMarker(snapshot: LocationSnapshot): AMapMarker {
  if (!amap || !map || !infoWindow) {
    throw new Error('地图尚未初始化')
  }
  const report = snapshot.latest_report
  const currentMap = map
  const currentInfoWindow = infoWindow
  const marker = new amap.Marker({
    anchor: 'bottom-center',
    bubble: true,
    clickable: true,
    content: buildMarkerContent(snapshot),
    cursor: 'pointer',
    draggable: false,
    position: [Number(report?.longitude), Number(report?.latitude)],
    title: getUserDisplayName(snapshot),
    topWhenClick: true,
  })
  marker.on('click', () => {
    currentInfoWindow.setContent(buildInfoWindowContent(snapshot))
    currentInfoWindow.open(currentMap, marker.getPosition())
  })
  return marker
}

function buildMarkerContent(snapshot: LocationSnapshot): string {
  const displayName = getUserDisplayName(snapshot)
  return `
    <div
      class="location-map-marker location-map-marker--${snapshot.location_status}"
      aria-label="${escapeHtml(displayName)} 的位置标记"
    >
      <span class="location-map-marker__avatar">${escapeHtml(getUserInitial(displayName))}</span>
      <span class="location-map-marker__body">
        <strong>${escapeHtml(displayName)}</strong>
        <small>${escapeHtml(getLocationStatusLabel(snapshot.location_status))}</small>
      </span>
      <span class="location-map-marker__pin" aria-hidden="true"></span>
    </div>
  `
}

function buildInfoWindowContent(snapshot: LocationSnapshot): string {
  const report = snapshot.latest_report
  const displayName = getUserDisplayName(snapshot)
  return `
    <div class="location-map-info">
      <strong>${escapeHtml(displayName)}</strong>
      <span>${escapeHtml(getLocationStatusLabel(snapshot.location_status))}</span>
      <p>用户名：${escapeHtml(snapshot.user.username)}</p>
      <p>手机号：${escapeHtml(snapshot.user.phone || '-')}</p>
      <p>${escapeHtml(getLocationDisplayAddress(snapshot))}</p>
      <p>上报时间：${escapeHtml(formatDateTime(report?.reported_at))}</p>
      <p>定位精度：${escapeHtml(formatAccuracy(report?.accuracy))}</p>
    </div>
  `
}

function focusSnapshot(snapshot: LocationSnapshot): void {
  if (!map || !hasUsableCoordinates(snapshot)) {
    return
  }
  const report = snapshot.latest_report
  const position: MapPosition = [Number(report?.longitude), Number(report?.latitude)]
  map.setZoomAndCenter(SELECTED_EMPLOYEE_ZOOM, position)
}

function formatAccuracy(value: string | null | undefined): string {
  return value ? `${value} 米` : '-'
}

function getUserDisplayName(snapshot: LocationSnapshot): string {
  return snapshot.user.real_name || snapshot.user.username || '未知人员'
}

function getUserInitial(displayName: string): string {
  return displayName.trim().slice(0, 1).toUpperCase() || '?'
}

function escapeHtml(value: string | undefined | null): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}
</script>

<template>
  <section class="location-page">
    <header class="location-page__header">
      <div>
        <h1>人员位置</h1>
        <p>查看员工最近一次上报位置，所有位置均以员工主动上报时间为准。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" type="primary" @click="loadLocations">刷新</el-button>
    </header>

    <section class="location-page__metrics" aria-label="人员位置概览">
      <article class="location-page__metric">
        <span>员工总数</span>
        <strong>{{ statusCounts.total }}</strong>
      </article>
      <article class="location-page__metric">
        <span>正常</span>
        <strong>{{ statusCounts.normal }}</strong>
      </article>
      <article class="location-page__metric">
        <span>已过期</span>
        <strong>{{ statusCounts.expired }}</strong>
      </article>
      <article class="location-page__metric">
        <span>需关注</span>
        <strong>{{ attentionLocations.length }}</strong>
      </article>
    </section>

    <section class="location-page__workspace">
      <div class="location-map-panel">
        <div ref="mapContainer" class="location-map-panel__canvas">
          <el-empty
            v-if="mapMessage"
            :description="mapMessage"
          />
        </div>
      </div>

      <aside class="location-attention">
        <header>
          <h2>未上报或位置已过期</h2>
          <el-tag type="warning">{{ attentionLocations.length }}</el-tag>
        </header>

        <el-empty
          v-if="attentionLocations.length === 0"
          description="暂无需关注人员"
        />

        <button
          v-for="snapshot in attentionLocations"
          v-else
          :key="snapshot.user.id"
          class="location-attention__item"
          type="button"
          @click="focusSnapshot(snapshot)"
        >
          <span>
            <strong>{{ snapshot.user.real_name }}</strong>
            <small>{{ getLocationDisplayAddress(snapshot) }}</small>
          </span>
          <el-tag :type="getLocationStatusTagType(snapshot.location_status)">
            {{ getLocationStatusLabel(snapshot.location_status) }}
          </el-tag>
        </button>
      </aside>
    </section>

    <section class="location-table-panel">
      <el-table
        v-loading="loading"
        :data="snapshots"
        row-key="user.id"
        @row-click="focusSnapshot"
      >
        <el-table-column label="员工" min-width="150">
          <template #default="{ row }: { row: LocationSnapshot }">
            <strong>{{ row.user.real_name }}</strong>
            <p class="location-table-panel__subtext">{{ row.user.username }}</p>
          </template>
        </el-table-column>
        <el-table-column label="位置状态" width="120">
          <template #default="{ row }: { row: LocationSnapshot }">
            <el-tag :type="getLocationStatusTagType(row.location_status)">
              {{ getLocationStatusLabel(row.location_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近上报位置" min-width="220">
          <template #default="{ row }: { row: LocationSnapshot }">
            {{ getLocationDisplayAddress(row) }}
          </template>
        </el-table-column>
        <el-table-column label="上报时间" min-width="160">
          <template #default="{ row }: { row: LocationSnapshot }">
            {{ formatDateTime(row.latest_report?.reported_at) }}
          </template>
        </el-table-column>
        <el-table-column label="定位精度" width="120">
          <template #default="{ row }: { row: LocationSnapshot }">
            {{ formatAccuracy(row.latest_report?.accuracy) }}
          </template>
        </el-table-column>
      </el-table>
    </section>
  </section>
</template>
