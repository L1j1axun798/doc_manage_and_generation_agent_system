<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import DocumentExplorer from '@/modules/documents/components/DocumentExplorer.vue'
import { formatDateTime } from '@/shared/utils/format'
import {
  createProjectMember,
  deleteProjectMember,
  fetchProjectMembers,
  updateProjectMember,
} from '../api/project-members.api'
import { archiveProject, deleteProject, fetchProject, unarchiveProject } from '../api/projects.api'
import ProjectArchivePanel from '../components/ProjectArchivePanel.vue'
import ProjectMemberDialog from '../components/ProjectMemberDialog.vue'
import ProjectMemberTable from '../components/ProjectMemberTable.vue'
import ProjectStatusTag from '../components/ProjectStatusTag.vue'
import type { Project, ProjectMember, ProjectMemberPayload } from '../projects.types'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const projectId = computed(() => Number(route.params.projectId))
const project = ref<Project | null>(null)
const members = ref<ProjectMember[]>([])
const loading = ref(false)
const membersLoading = ref(false)
const mutationLoading = ref(false)
const memberDialogVisible = ref(false)
const editingMember = ref<ProjectMember | null>(null)
const activeTab = ref('overview')

onMounted(loadProject)

watch(projectId, () => {
  void loadProject()
})

async function loadProject(): Promise<void> {
  if (!Number.isFinite(projectId.value)) {
    await router.replace('/404')
    return
  }

  loading.value = true
  try {
    project.value = await fetchProject(projectId.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadMembers(): Promise<void> {
  membersLoading.value = true
  try {
    members.value = await fetchProjectMembers(projectId.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    membersLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'members' && members.value.length === 0) {
    void loadMembers()
  }
})

function openCreateMember(): void {
  editingMember.value = null
  memberDialogVisible.value = true
}

function openEditMember(member: ProjectMember): void {
  editingMember.value = member
  memberDialogVisible.value = true
}

async function submitMember(payload: ProjectMemberPayload): Promise<void> {
  mutationLoading.value = true
  try {
    if (editingMember.value) {
      await updateProjectMember(projectId.value, editingMember.value.id, payload)
      ElMessage.success('成员已修改')
    } else {
      await createProjectMember(projectId.value, payload)
      ElMessage.success('成员已添加')
    }
    memberDialogVisible.value = false
    await loadMembers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function removeMember(member: ProjectMember): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认移除成员“${member.user_real_name || member.user_username}”？`, '移除成员', {
      confirmButtonText: '移除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  mutationLoading.value = true
  try {
    await deleteProjectMember(projectId.value, member.id)
    ElMessage.success('成员已移除')
    await loadMembers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function archiveCurrentProject(): Promise<void> {
  if (!project.value) {
    return
  }

  mutationLoading.value = true
  try {
    project.value = await archiveProject(project.value.id)
    ElMessage.success('项目已归档')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function unarchiveCurrentProject(): Promise<void> {
  if (!project.value) {
    return
  }

  mutationLoading.value = true
  try {
    project.value = await unarchiveProject(project.value.id)
    ElMessage.success('项目已取消归档')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}

async function deleteCurrentProject(): Promise<void> {
  if (!project.value) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除项目“${project.value.name}”？仅项目资料为空时可以删除；如有资料，请先归档或清空项目资料。`,
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

  mutationLoading.value = true
  try {
    await deleteProject(project.value.id)
    ElMessage.success('项目已删除')
    await router.push('/projects')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    mutationLoading.value = false
  }
}
</script>

<template>
  <section class="project-page">
    <header class="project-page__header">
      <div>
        <h1>{{ project?.name || '项目详情' }}</h1>
        <p>{{ project?.code || '-' }}</p>
      </div>
      <div class="project-page__header-actions">
        <el-button @click="router.push('/projects')">返回</el-button>
        <el-button
          v-if="authStore.isSystemAdmin && project"
          :loading="mutationLoading"
          type="danger"
          @click="deleteCurrentProject"
        >
          删除项目
        </el-button>
        <ProjectStatusTag v-if="project" :status="project.status" />
      </div>
    </header>

    <el-skeleton v-if="loading" :rows="6" animated />

    <el-tabs v-else-if="project" v-model="activeTab" class="project-detail-tabs">
      <el-tab-pane label="项目概况" name="overview">
        <el-descriptions border :column="1">
          <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
          <el-descriptions-item label="项目编号">{{ project.code }}</el-descriptions-item>
          <el-descriptions-item label="项目负责人">{{ project.manager_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="描述">{{ project.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(project.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(project.updated_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <el-tab-pane label="项目成员" name="members">
        <div class="project-tab-toolbar">
          <el-button v-if="authStore.isSystemAdmin" type="primary" @click="openCreateMember">
            添加成员
          </el-button>
        </div>
        <ProjectMemberTable
          :loading="membersLoading"
          :members="members"
          :show-actions="authStore.isSystemAdmin"
          @delete="removeMember"
          @edit="openEditMember"
        />
      </el-tab-pane>

      <el-tab-pane label="项目资料" name="documents">
        <DocumentExplorer :project-id="project.id" scope="project" :show-folder-navigation="false" />
      </el-tab-pane>

      <el-tab-pane label="归档信息" name="archive">
        <ProjectArchivePanel
          :loading="mutationLoading"
          :project="project"
          @archive="archiveCurrentProject"
          @unarchive="unarchiveCurrentProject"
        />
      </el-tab-pane>
    </el-tabs>

    <ProjectMemberDialog
      v-model="memberDialogVisible"
      :loading="mutationLoading"
      :member="editingMember"
      @submit="submitMember"
    />
  </section>
</template>
