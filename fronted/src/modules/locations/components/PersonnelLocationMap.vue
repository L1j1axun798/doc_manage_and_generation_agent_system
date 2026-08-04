<script setup lang="ts">
import AMapLoader from '@amap/amap-jsapi-loader'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { env } from '@/config/env'
import { getErrorMessage } from '@/core/http/error-normalizer'
import { useTheme } from '@/shared/composables/useTheme'
import { formatDateTime } from '@/shared/utils/format'
import type { LocationSnapshot } from '../locations.types'
import {
  getLocationDisplayAddress,
  getLocationStatusLabel,
  hasAmapConfig,
  hasUsableCoordinates,
} from '../utils/location-status'

type MapPosition = [number, number]
type MapVariant = 'full' | 'overview'

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
  setMapStyle(style: string): void
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
      mapStyle: string
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
  ToolBar: new (options?: { position?: { top?: string, right?: string } }) => unknown
}

const props = withDefaults(defineProps<{
  snapshots: LocationSnapshot[]
  loading?: boolean
  variant?: MapVariant
}>(), {
  loading: false,
  variant: 'full',
})

const CHINA_CENTER: MapPosition = [104.195397, 35.86166]
const CHINA_OVERVIEW_ZOOM = 4
const MAX_FIT_VIEW_ZOOM = 14
const SELECTED_EMPLOYEE_ZOOM = 15
const MAP_ZOOM_RANGE: [number, number] = [3, 18]

const mapContainer = ref<HTMLElement | null>(null)
const mapMessage = ref('')
const { isDarkTheme } = useTheme()
const amapReady = computed(() => hasAmapConfig(env.amapKey))
const markerSnapshots = computed(() => props.snapshots.filter(hasUsableCoordinates))
const isOverview = computed(() => props.variant === 'overview')

let amap: AMapNamespace | null = null
let map: AMapMap | null = null
let infoWindow: AMapInfoWindow | null = null
let markers: AMapMarker[] = []
let mapControlsInstalled = false

onMounted(async () => {
  await nextTick()
  await renderMap()
})

watch(
  [() => props.snapshots, () => props.loading],
  async () => {
    await nextTick()
    await renderMap()
  },
)

watch(isDarkTheme, (dark) => {
  map?.setMapStyle(dark ? 'amap://styles/darkblue' : 'amap://styles/normal')
})

onBeforeUnmount(() => {
  map?.destroy()
})

async function renderMap(): Promise<void> {
  if (props.loading) {
    return
  }
  if (!amapReady.value) {
    mapMessage.value = '未配置地图服务'
    return
  }
  if (!mapContainer.value) {
    return
  }
  if (markerSnapshots.value.length === 0) {
    map?.clearMap()
    mapMessage.value = '暂无可展示的上报坐标'
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
      const interactive = !isOverview.value
      map = new amap.Map(mapContainer.value, {
        center: CHINA_CENTER,
        doubleClickZoom: interactive,
        dragEnable: interactive,
        jogEnable: interactive,
        keyboardEnable: interactive,
        mapStyle: isDarkTheme.value ? 'amap://styles/darkblue' : 'amap://styles/normal',
        resizeEnable: true,
        rotateEnable: false,
        scrollWheel: interactive,
        touchZoom: interactive,
        zoom: CHINA_OVERVIEW_ZOOM,
        zoomEnable: interactive,
        zooms: MAP_ZOOM_RANGE,
      })
      setMapInteraction(interactive)
      if (interactive) {
        installMapControls()
        infoWindow = new amap.InfoWindow({ offset: new amap.Pixel(0, -58) })
      }
    }

    map.clearMap()
    markers = markerSnapshots.value.map((snapshot) => createMarker(snapshot))
    map.add(markers)
    map.setFitView(
      markers,
      false,
      isOverview.value ? [52, 52, 52, 52] : [90, 90, 90, 90],
      MAX_FIT_VIEW_ZOOM,
    )
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

function setMapInteraction(interactive: boolean): void {
  map?.setStatus({
    doubleClickZoom: interactive,
    dragEnable: interactive,
    keyboardEnable: interactive,
    scrollWheel: interactive,
    touchZoom: interactive,
    zoomEnable: interactive,
  })
}

function createMarker(snapshot: LocationSnapshot): AMapMarker {
  if (!amap || !map) {
    throw new Error('地图尚未初始化')
  }
  const report = snapshot.latest_report
  const displayName = getUserDisplayName(snapshot)
  const marker = new amap.Marker({
    anchor: 'bottom-center',
    bubble: true,
    clickable: !isOverview.value,
    content: isOverview.value
      ? buildOverviewMarkerContent(snapshot)
      : buildFullMarkerContent(snapshot),
    cursor: isOverview.value ? 'default' : 'pointer',
    draggable: false,
    position: [Number(report?.longitude), Number(report?.latitude)],
    title: displayName,
    topWhenClick: true,
  })
  if (!isOverview.value && infoWindow) {
    const currentMap = map
    const currentInfoWindow = infoWindow
    marker.on('click', () => {
      currentInfoWindow.setContent(buildInfoWindowContent(snapshot))
      currentInfoWindow.open(currentMap, marker.getPosition())
    })
  }
  return marker
}

function buildOverviewMarkerContent(snapshot: LocationSnapshot): string {
  const displayName = getUserDisplayName(snapshot)
  return `
    <div
      class="personnel-location-map-marker personnel-location-map-marker--${snapshot.location_status}"
      aria-label="${escapeHtml(displayName)} 的位置"
    >
      ${escapeHtml(getUserInitial(displayName))}
    </div>
  `
}

function buildFullMarkerContent(snapshot: LocationSnapshot): string {
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
  map.setZoomAndCenter(
    SELECTED_EMPLOYEE_ZOOM,
    [Number(report?.longitude), Number(report?.latitude)],
  )
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
    .replaceAll('\'', '&#039;')
}

defineExpose({ focusSnapshot })
</script>

<template>
  <div
    class="personnel-location-map"
    :class="`personnel-location-map--${variant}`"
  >
    <div ref="mapContainer" class="personnel-location-map__canvas" />
    <div v-if="loading" class="personnel-location-map__state">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="mapMessage" class="personnel-location-map__state">
      <el-empty :description="mapMessage" :image-size="72" />
    </div>
  </div>
</template>

<style scoped>
.personnel-location-map {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--color-bg-surface-secondary);
}

.personnel-location-map--full,
.personnel-location-map--full .personnel-location-map__canvas {
  min-height: 520px;
}

.personnel-location-map--overview,
.personnel-location-map--overview .personnel-location-map__canvas {
  min-height: 320px;
}

.personnel-location-map__canvas {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.personnel-location-map--full .personnel-location-map__canvas {
  touch-action: none;
}

.personnel-location-map--overview .personnel-location-map__canvas {
  pointer-events: none;
}

.personnel-location-map__state {
  position: absolute;
  inset: 0;
  display: grid;
  padding: 24px;
  place-items: center;
  background: var(--color-bg-surface-secondary);
}

.personnel-location-map__state :deep(.el-skeleton) {
  width: min(80%, 420px);
}

:global(.personnel-location-map-marker) {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 3px solid rgb(255 255 255 / 92%);
  border-radius: 50%;
  box-shadow: 0 8px 20px rgb(20 36 55 / 24%);
  color: #fff;
  background: var(--color-brand);
  font-size: 13px;
  font-weight: 800;
}

:global(.personnel-location-map-marker--normal) {
  background: var(--color-success);
}

:global(.personnel-location-map-marker--expired) {
  background: var(--color-warning);
}

:global(.personnel-location-map-marker--today_unreported) {
  background: var(--color-text-secondary);
}

:global(.personnel-location-map-marker--locate_failed) {
  background: var(--color-danger);
}
</style>
