<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { fetchProjects } from '@/modules/projects/api/projects.api'
import type { Project } from '@/modules/projects/projects.types'
import DocumentGenerationPanel from '../components/DocumentGenerationPanel.vue'

const projects = ref<Project[]>([])
const selectedProjectId = ref<number | null>(null)
const loading = ref(false)

const activeProjects = computed(() => projects.value.filter((project) => project.status === 'active'))
const selectedProject = computed(
  () => activeProjects.value.find((project) => project.id === selectedProjectId.value) || null,
)

onMounted(loadProjects)

async function loadProjects(): Promise<void> {
  loading.value = true
  try {
    const rows: Project[] = []
    let page = 1

    while (page <= 50) {
      const response = await fetchProjects({ page, ordering: '-updated_at' })
      rows.push(...response.results)
      if (!response.next || rows.length >= response.count) {
        break
      }
      page += 1
    }

    projects.value = rows
    if (selectedProjectId.value && !activeProjects.value.some((project) => project.id === selectedProjectId.value)) {
      selectedProjectId.value = null
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="document-generation-page">
    <header class="document-generation-page__header">
      <div>
        <h1>入场资料Agent V1.0</h1>
        <p>选择你有权访问的在执行项目，基于已有资料生成四措两案初稿，并完成事实确认、人工审核和 Word 导出。</p>
      </div>
      <el-button :loading="loading" @click="loadProjects">刷新项目</el-button>
    </header>

    <el-alert
      title="本Agent只生成入场资料（四(三)措两案）初稿，不生成检测报告、完工报告或实测结论。"
      type="warning"
      :closable="false"
      show-icon
    />

    <el-card class="document-generation-page__selector" shadow="never">
      <el-form label-position="top">
        <el-form-item label="选择项目">
          <el-select
            v-model="selectedProjectId"
            filterable
            placeholder="请选择一个在执行项目"
            :loading="loading"
            style="width: 100%"
          >
            <el-option
              v-for="project in activeProjects"
              :key="project.id"
              :label="`${project.name}（${project.code}）`"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <el-empty
        v-if="!loading && activeProjects.length === 0"
        description="当前账号没有可用于编制的在执行项目"
      />
    </el-card>

    <DocumentGenerationPanel v-if="selectedProject" :key="selectedProject.id" :project="selectedProject" />
    <el-empty v-else-if="activeProjects.length" description="请先选择项目，再开始四措两案编制" />
  </section>
</template>

<style scoped>
.document-generation-page {
  display: grid;
  gap: 18px;
}

.document-generation-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.document-generation-page__header h1,
.document-generation-page__header p {
  margin: 0;
}

.document-generation-page__header p {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
}

.document-generation-page__selector :deep(.el-form-item) {
  margin-bottom: 0;
}

@media (max-width: 900px) {
  .document-generation-page__header {
    flex-direction: column;
  }
}
</style>
