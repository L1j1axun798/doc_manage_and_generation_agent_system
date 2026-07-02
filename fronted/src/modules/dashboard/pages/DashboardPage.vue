<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { fetchMyLatestLocation, reportLocation } from '@/modules/locations/api/locations.api'
import type { LocationSnapshot } from '@/modules/locations/locations.types'
import {
  getLocationDisplayAddress,
  getLocationStatusLabel,
  getLocationStatusTagType,
} from '@/modules/locations/utils/location-status'
import { formatDateTime } from '@/shared/utils/format'
import { fetchDashboardCounts } from '../api/dashboard.api'

interface StatusItem {
  label: string
  value: string
}

const statusItems = ref<StatusItem[]>([
  { label: '可见资料', value: '--' },
  { label: '我的项目', value: '--' },
  { label: '未读通知', value: '--' },
  { label: '活跃授权', value: '--' },
])

const loading = ref(false)
const locationLoading = ref(false)
const reportLoading = ref(false)
const myLocation = ref<LocationSnapshot | null>(null)

onMounted(async () => {
  await Promise.all([loadDashboardCounts(), loadMyLocation(true)])
})

async function loadDashboardCounts(): Promise<void> {
  loading.value = true
  try {
    const counts = await fetchDashboardCounts()
    statusItems.value = [
      { label: '可见资料', value: String(counts.visibleDocuments) },
      { label: '我的项目', value: String(counts.myProjects) },
      { label: '未读通知', value: String(counts.unreadNotifications) },
      { label: '活跃授权', value: String(counts.activeGrants) },
    ]
  } catch {
    // 请求失败时保持默认的 -- 占位
  } finally {
    loading.value = false
  }
}

async function loadMyLocation(showPrompt: boolean): Promise<void> {
  locationLoading.value = true
  try {
    myLocation.value = await fetchMyLatestLocation()
    if (showPrompt && myLocation.value.should_report) {
      void promptLocationReport()
    }
  } catch {
    // 首页概览不因位置状态接口失败阻断。
  } finally {
    locationLoading.value = false
  }
}

async function promptLocationReport(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '距离上次上报已超过 4 小时，或今天尚未成功上报当前位置。',
      '位置上报提醒',
      {
        confirmButtonText: '上报当前位置',
        cancelButtonText: '稍后处理',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  await reportCurrentLocation()
}

async function reportCurrentLocation(): Promise<void> {
  reportLoading.value = true
  try {
    if (!navigator.geolocation) {
      await reportLocation({
        report_status: 'locate_failed',
        failure_reason: '当前浏览器不支持定位',
      })
      ElMessage.warning('当前浏览器不支持定位，已记录定位失败')
      await loadMyLocation(false)
      return
    }

    const position = await getCurrentPosition().catch(async (error: unknown) => {
      await submitLocationFailure(getGeolocationErrorMessage(error))
      return null
    })
    if (!position) {
      return
    }
    await reportLocation({
      longitude: position.coords.longitude,
      latitude: position.coords.latitude,
      accuracy: position.coords.accuracy,
    })
    ElMessage.success('当前位置已上报')
    await loadMyLocation(false)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    reportLoading.value = false
  }
}

function getCurrentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 10000,
    })
  })
}

async function submitLocationFailure(reason: string): Promise<void> {
  try {
    await reportLocation({
      report_status: 'locate_failed',
      failure_reason: reason,
    })
    ElMessage.warning('定位失败，已记录本次上报结果')
    await loadMyLocation(false)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function getGeolocationErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) {
    const message = String((error as { message?: unknown }).message || '').trim()
    if (message) {
      return message
    }
  }
  return '浏览器定位失败'
}

function formatAccuracy(value: string | null | undefined): string {
  return value ? `${value} 米` : '-'
}
</script>

<template>
  <section class="dashboard-page">
    <header class="dashboard-page__header">
      <!-- <p class="dashboard-page__eyebrow">Wind Document System</p> -->
      <h1>绿能信盾资料管理系统</h1>
    </header>

    <div class="dashboard-page__metrics" aria-label="首页概览">
      <article
        v-for="item in statusItems"
        :key="item.label"
        class="dashboard-page__metric"
      >
        <span>{{ item.label }}</span>
        <strong>{{ loading ? '...' : item.value }}</strong>
      </article>
    </div>

    <section class="dashboard-location-panel">
      <header>
        <div>
          <h2>我的位置上报</h2>
          <p>每天建议上报 2～3 次，位置仅以主动上报时间为准。</p>
        </div>
        <el-button
          :loading="reportLoading"
          type="primary"
          @click="reportCurrentLocation"
        >
          上报当前位置
        </el-button>
      </header>

      <el-skeleton v-if="locationLoading && !myLocation" :rows="3" animated />

      <el-descriptions v-else-if="myLocation" border :column="1">
        <el-descriptions-item label="位置状态">
          <el-tag :type="getLocationStatusTagType(myLocation.location_status)">
            {{ getLocationStatusLabel(myLocation.location_status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最近上报位置">
          {{ getLocationDisplayAddress(myLocation) }}
        </el-descriptions-item>
        <el-descriptions-item label="上报时间">
          {{ formatDateTime(myLocation.latest_report?.reported_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="定位精度">
          {{ formatAccuracy(myLocation.latest_report?.accuracy) }}
        </el-descriptions-item>
        <el-descriptions-item label="上报结果">
          {{ myLocation.latest_report?.failure_reason || '已记录' }}
        </el-descriptions-item>
      </el-descriptions>
    </section>
  </section>
</template>
