<script setup lang="ts">
import { onMounted, ref } from 'vue'

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

onMounted(async () => {
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
})
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
  </section>
</template>
