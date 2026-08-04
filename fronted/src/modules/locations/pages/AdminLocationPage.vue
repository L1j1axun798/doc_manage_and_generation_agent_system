<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { formatDateTime } from '@/shared/utils/format'
import { fetchAdminLatestLocations } from '../api/locations.api'
import PersonnelLocationMap from '../components/PersonnelLocationMap.vue'
import type { LocationSnapshot, LocationStatus } from '../locations.types'
import {
  getAttentionLocations,
  getLocationDisplayAddress,
  getLocationStatusLabel,
  getLocationStatusTagType,
} from '../utils/location-status'

const snapshots = ref<LocationSnapshot[]>([])
const loading = ref(false)
const mapRef = ref<InstanceType<typeof PersonnelLocationMap> | null>(null)
const attentionLocations = computed(() => getAttentionLocations(snapshots.value))

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

onMounted(async () => {
  await loadLocations()
})

async function loadLocations(): Promise<void> {
  loading.value = true
  try {
    snapshots.value = await fetchAdminLatestLocations()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function focusSnapshot(snapshot: LocationSnapshot): void {
  mapRef.value?.focusSnapshot(snapshot)
}

function formatAccuracy(value: string | null | undefined): string {
  return value ? `${value} 米` : '-'
}
</script>

<template>
  <section class="location-page">
    <header class="location-page__header">
      <div>
        <h1>人员位置</h1>
        <p>查看员工最近一次上报位置，所有位置均以员工主动上报时间为准。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" type="primary" @click="loadLocations">
        刷新
      </el-button>
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
        <PersonnelLocationMap
          ref="mapRef"
          :loading="loading"
          :snapshots="snapshots"
        />
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
