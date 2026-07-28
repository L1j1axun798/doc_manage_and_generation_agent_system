<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { fetchProjects } from '@/modules/projects/api/projects.api'
import type { Project } from '@/modules/projects/projects.types'
import DocumentExplorer from './DocumentExplorer.vue'

const projects = ref<Project[]>([])
const selectedProject = ref<Project | null>(null)
const loading = ref(false)

onMounted(loadVisibleProjects)

async function loadVisibleProjects(): Promise<void> {
  loading.value = true
  try {
    const items: Project[] = []
    let page = 1
    let total = 0
    do {
      const response = await fetchProjects({ page, ordering: '-updated_at' })
      items.push(...response.results)
      total = response.count
      page += 1
    } while (items.length < total)

    projects.value = items.filter((project) => project.status === 'active')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="entry-preparation">
    <section
      class="document-subfolder-panel entry-preparation__project-panel"
      aria-label="项目列表"
    >
      <header class="document-subfolder-panel__header">
        <h2>{{ selectedProject?.name || '项目列表' }}</h2>
        <div class="document-subfolder-panel__meta">
          <span v-if="!selectedProject">项目数：{{ projects.length }}</span>
          <el-button v-else size="small" @click="selectedProject = null">
            返回项目列表
          </el-button>
          <el-button
            v-if="!selectedProject"
            :loading="loading"
            size="small"
            @click="loadVisibleProjects"
          >
            刷新
          </el-button>
        </div>
      </header>

      <el-skeleton v-if="loading" :rows="4" animated />
      <div
        v-else-if="projects.length > 0"
        class="document-subfolder-panel__grid"
        :class="{ 'document-subfolder-panel__grid--detail': selectedProject }"
      >
        <div
          v-for="project in selectedProject ? [selectedProject] : projects"
          :key="project.id"
          class="document-subfolder-panel__item"
          :class="{ 'is-active': selectedProject?.id === project.id }"
        >
          <button
            class="document-subfolder-panel__select"
            type="button"
            @click="selectedProject = project"
          >
            {{ project.name }}（{{ project.code }}）
          </button>
        </div>
      </div>

      <el-empty
        v-else
        description="暂无可访问的进行中项目"
        :image-size="72"
      />
    </section>

    <template v-if="selectedProject">
      <el-alert
        title="在这里上传的资料会同时出现在该项目的“项目资料”中；从“项目资料”普通上传的文件不会进入这里。"
        type="info"
        :closable="false"
        show-icon
      />
      <div class="entry-preparation__documents">
        <DocumentExplorer
          :key="selectedProject.id"
          :project-id="selectedProject.id"
          folder-layout="top"
          scope="project"
          fixed-folder-code="PUBLIC-COMPLETION"
          source-type="entrance_material"
          :show-folder-navigation="false"
        />
      </div>
    </template>
  </section>
</template>

<style scoped>
.entry-preparation {
  display: grid;
  gap: 14px;
}

.entry-preparation__project-panel .document-subfolder-panel__grid {
  grid-template-columns: minmax(0, 1fr);
}

.entry-preparation__documents :deep(.document-explorer--top) {
  margin: 0;
}

.entry-preparation__documents :deep(.document-explorer--top .document-explorer__workspace) {
  width: 100%;
}

</style>
