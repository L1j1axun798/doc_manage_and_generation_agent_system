<script setup lang="ts">
import { computed } from 'vue'

import { formatDateTime } from '@/shared/utils/format'
import type { AppNotification } from '../notifications.types'
import NotificationCategoryTag from './NotificationCategoryTag.vue'

const props = defineProps<{
  modelValue: boolean
  notification: AppNotification | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
</script>

<template>
  <el-drawer v-model="drawerVisible" size="460px" title="通知详情">
    <section v-if="notification" class="notification-detail">
      <header>
        <NotificationCategoryTag :category="notification.category" />
        <h2>{{ notification.title }}</h2>
        <p>{{ formatDateTime(notification.created_at) }}</p>
      </header>

      <p class="notification-detail__message">{{ notification.message }}</p>

      <el-descriptions border :column="1">
        <el-descriptions-item label="资源类型">
          {{ notification.resource_type || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="资源 ID">
          {{ notification.resource_id || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="阅读状态">
          {{ notification.is_read ? '已读' : '未读' }}
        </el-descriptions-item>
        <el-descriptions-item label="阅读时间">
          {{ notification.read_at ? formatDateTime(notification.read_at) : '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </section>
  </el-drawer>
</template>
