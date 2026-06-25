<script setup lang="ts">
import { formatDateTime } from '@/shared/utils/format'
import type { Project } from '../projects.types'
import ProjectStatusTag from './ProjectStatusTag.vue'

defineProps<{
  project: Project
  loading?: boolean
}>()

const emit = defineEmits<{
  archive: []
  unarchive: []
}>()
</script>

<template>
  <section class="project-archive-panel">
    <ProjectStatusTag :status="project.status" />
    <p v-if="project.archived_at">归档时间：{{ formatDateTime(project.archived_at) }}</p>
    <p v-else>项目当前处于进行中状态。</p>
    <el-button
      v-if="project.status === 'active'"
      :loading="loading"
      type="warning"
      @click="emit('archive')"
    >
      归档项目
    </el-button>
    <el-button
      v-else
      :loading="loading"
      type="primary"
      @click="emit('unarchive')"
    >
      取消归档
    </el-button>
  </section>
</template>
