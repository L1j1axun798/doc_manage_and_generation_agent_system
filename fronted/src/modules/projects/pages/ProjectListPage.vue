<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import type { ApiPage } from '@/shared/types/api.types'
import { createProject, deleteProject, fetchProjects, updateProject } from '../api/projects.api'
import ProjectFormDialog from '../components/ProjectFormDialog.vue'
import ProjectTable from '../components/ProjectTable.vue'
import type { Project, ProjectPayload } from '../projects.types'

const router = useRouter()
const authStore = useAuthStore()
const projects = ref<Project[]>([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const loading = ref(false)
const formLoading = ref(false)
const formVisible = ref(false)
const editingProject = ref<Project | null>(null)

onMounted(loadProjects)

async function loadProjects(): Promise<void> {
  loading.value = true
  try {
    const response: ApiPage<Project> = await fetchProjects({
      page: page.value,
      search: search.value,
      ordering: '-updated_at',
    })
    projects.value = response.results
    total.value = response.count
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function submitSearch(): void {
  page.value = 1
  void loadProjects()
}

function openCreate(): void {
  editingProject.value = null
  formVisible.value = true
}

function openEdit(project: Project): void {
  editingProject.value = project
  formVisible.value = true
}

async function submitProject(payload: ProjectPayload): Promise<void> {
  formLoading.value = true
  try {
    if (editingProject.value) {
      await updateProject(editingProject.value.id, payload)
      ElMessage.success('项目已修改')
    } else {
      await createProject(payload)
      ElMessage.success('项目已创建')
    }
    formVisible.value = false
    await loadProjects()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    formLoading.value = false
  }
}

async function removeProject(project: Project): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除项目“${project.name}”？仅项目资料为空时可以删除；如有资料，请先归档或清空项目资料。`,
      '删除项目',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  loading.value = true
  try {
    await deleteProject(project.id)
    ElMessage.success('项目已删除')
    await loadProjects()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="project-page">
    <header class="project-page__header">
      <div>
        <h1>项目管理</h1>
        <p>查询当前账号可见项目，并进入项目详情维护成员和资料。</p>
      </div>
      <el-button type="primary" @click="openCreate">创建项目</el-button>
    </header>

    <section class="document-search-panel">
      <el-input v-model="search" clearable placeholder="搜索项目名称或编号" @keyup.enter="submitSearch" />
      <el-button :loading="loading" type="primary" @click="submitSearch">查询</el-button>
    </section>

    <ProjectTable
      :loading="loading"
      :projects="projects"
      :show-delete="authStore.isSystemAdmin"
      @delete="removeProject"
      @edit="openEdit"
      @view="router.push(`/projects/${$event.id}`)"
    />

    <footer class="document-explorer__pagination">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="20"
        :total="total"
        @current-change="(nextPage: number) => { page = nextPage; void loadProjects() }"
      />
    </footer>

    <ProjectFormDialog
      v-model="formVisible"
      :loading="formLoading"
      :project="editingProject"
      @submit="submitProject"
    />
  </section>
</template>
