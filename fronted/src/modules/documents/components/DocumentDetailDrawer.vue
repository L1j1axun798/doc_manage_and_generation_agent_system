<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import DocumentAccessPanel from '@/modules/access/components/DocumentAccessPanel.vue'
import { formatDateTime, formatFileSize } from '@/shared/utils/format'
import type { DocumentItem } from '../documents.types'
import AccessLevelTag from './AccessLevelTag.vue'

const props = defineProps<{
  modelValue: boolean
  document: DocumentItem | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const activeTab = ref('detail')

watch(
  () => props.document?.id,
  () => {
    activeTab.value = 'detail'
  },
)
</script>

<template>
  <el-drawer v-model="drawerVisible" size="720px" title="文档详情">
    <el-skeleton v-if="loading" :rows="8" animated />

    <el-tabs v-else-if="document" v-model="activeTab" class="document-detail-tabs">
      <el-tab-pane label="基础信息" name="detail">
        <el-descriptions
          border
          :column="1"
          class="document-detail"
        >
          <el-descriptions-item label="标题">{{ document.title }}</el-descriptions-item>
          <el-descriptions-item label="描述">{{ document.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目录">{{ document.folder_name }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ document.project_name || '公共资料' }}</el-descriptions-item>
          <el-descriptions-item label="访问级别">
            <AccessLevelTag :value="document.access_level" />
          </el-descriptions-item>
          <el-descriptions-item label="当前版本">
            v{{ document.current_version?.version_number || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="文件名">
            {{ document.current_version?.original_filename || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="文件大小">
            {{ formatFileSize(document.current_version?.file_size) }}
          </el-descriptions-item>
          <el-descriptions-item label="SHA-256">
            <span class="document-detail__hash">{{ document.current_version?.sha256 || '-' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ document.created_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(document.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(document.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <el-tab-pane label="授权管理" name="access">
        <DocumentAccessPanel :document="document" />
      </el-tab-pane>
    </el-tabs>
  </el-drawer>
</template>
