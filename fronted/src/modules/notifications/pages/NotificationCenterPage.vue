<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { formatDateTime } from '@/shared/utils/format'
import {
  fetchNotification,
  fetchNotifications,
  markNotificationRead,
  markNotificationUnread,
} from '../api/notifications.api'
import NotificationCategoryTag from '../components/NotificationCategoryTag.vue'
import NotificationDetailDrawer from '../components/NotificationDetailDrawer.vue'
import type { AppNotification, NotificationCategory } from '../notifications.types'

const notifications = ref<AppNotification[]>([])
const selectedNotification = ref<AppNotification | null>(null)
const total = ref(0)
const page = ref(1)
const search = ref('')
const category = ref<NotificationCategory | ''>('')
const isRead = ref<boolean | ''>('')
const loading = ref(false)
const mutationLoading = ref(false)
const detailVisible = ref(false)

onMounted(loadNotifications)

async function loadNotifications(): Promise<void> {
  loading.value = true
  try {
    const response = await fetchNotifications({
      page: page.value,
      search: search.value,
      category: category.value,
      is_read: isRead.value,
      ordering: '-created_at',
    })
    notifications.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function submitSearch(): void {
  page.value = 1
  void loadNotifications()
}

function resetFilters(): void {
  search.value = ''
  category.value = ''
  isRead.value = ''
  submitSearch()
}

async function openDetail(notification: AppNotification): Promise<void> {
  selectedNotification.value = notification
  detailVisible.value = true
  try {
    selectedNotification.value = await fetchNotification(notification.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function toggleRead(notification: AppNotification): Promise<void> {
  mutationLoading.value = true
  try {
    if (notification.is_read) {
      await markNotificationUnread(notification.id)
      ElMessage.success('已标记为未读')
    } else {
      await markNotificationRead(notification.id)
      ElMessage.success('已标记为已读')
    }
    await loadNotifications()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}
</script>

<template>
  <section class="notification-page">
    <header class="notification-page__header">
      <div>
        <h1>通知中心</h1>
        <p>查看系统、文档和授权相关通知，并维护单条通知的已读状态。</p>
      </div>
    </header>

    <section class="notification-page__filters">
      <el-input v-model="search" clearable placeholder="搜索标题或内容" @keyup.enter="submitSearch" />
      <el-select v-model="category" clearable placeholder="分类">
        <el-option label="系统" value="system" />
        <el-option label="文档" value="document" />
        <el-option label="授权" value="access" />
      </el-select>
      <el-select v-model="isRead" clearable placeholder="阅读状态">
        <el-option label="未读" :value="false" />
        <el-option label="已读" :value="true" />
      </el-select>
      <el-button :loading="loading" type="primary" @click="submitSearch">查询</el-button>
      <el-button @click="resetFilters">重置</el-button>
    </section>

    <el-table :data="notifications" :loading="loading || mutationLoading" row-key="id">
      <el-table-column label="通知" min-width="260">
        <template #default="{ row }: { row: AppNotification }">
          <button class="notification-table__title" type="button" @click="openDetail(row)">
            <span v-if="!row.is_read" class="notification-table__dot" />
            {{ row.title }}
          </button>
          <p class="notification-table__message">{{ row.message }}</p>
        </template>
      </el-table-column>

      <el-table-column label="分类" width="100">
        <template #default="{ row }: { row: AppNotification }">
          <NotificationCategoryTag :category="row.category" />
        </template>
      </el-table-column>

      <el-table-column label="资源" min-width="150">
        <template #default="{ row }: { row: AppNotification }">
          {{ row.resource_type || '-' }} / {{ row.resource_id || '-' }}
        </template>
      </el-table-column>

      <el-table-column label="状态" width="90">
        <template #default="{ row }: { row: AppNotification }">
          <el-tag :type="row.is_read ? 'info' : 'warning'" effect="light">
            {{ row.is_read ? '已读' : '未读' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="时间" width="170">
        <template #default="{ row }: { row: AppNotification }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>

      <el-table-column label="操作" fixed="right" width="130">
        <template #default="{ row }: { row: AppNotification }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link @click="toggleRead(row)">
            {{ row.is_read ? '标未读' : '标已读' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <footer class="notification-page__pagination">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="20"
        :total="total"
        @current-change="(nextPage: number) => { page = nextPage; void loadNotifications() }"
      />
    </footer>

    <NotificationDetailDrawer v-model="detailVisible" :notification="selectedNotification" />
  </section>
</template>
