<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { UploadUserFile } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import { fetchProjects } from '@/modules/projects/api/projects.api'
import type { Project } from '@/modules/projects/projects.types'
import { formatDateTime } from '@/shared/utils/format'
import {
  fetchKnowledgeCorpusUploads,
  retryKnowledgeCorpusUpload,
  uploadKnowledgeCorpus,
} from '../api/document-generation.api'
import DocumentGenerationPanel from '../components/DocumentGenerationPanel.vue'
import type {
  KnowledgeCorpusUpload,
  KnowledgeCorpusUploadStatus,
  KnowledgeSectionCode,
} from '../document-generation.types'

const authStore = useAuthStore()
const projects = ref<Project[]>([])
const selectedProjectId = ref<number | null>(null)
const loading = ref(false)
const uploadDialogVisible = ref(false)
const uploadSubmitting = ref(false)
const uploadHistoryLoading = ref(false)
const uploadFiles = ref<UploadUserFile[]>([])
const knowledgeUploads = ref<KnowledgeCorpusUpload[]>([])
const allSectionCodes: KnowledgeSectionCode[] = [
  'overview',
  'organization_measures',
  'construction_plan',
  'technical_measures',
  'safety_measures',
  'risk_identification',
  'emergency_plan',
  'environmental_measures',
]
const uploadForm = reactive({
  sectionCodes: [...allSectionCodes],
})
let corpusPollTimer: number | undefined

const activeProjects = computed(() => projects.value.filter((project) => project.status === 'active'))
const selectedProject = computed(
  () => activeProjects.value.find((project) => project.id === selectedProjectId.value) || null,
)
const isSystemAdmin = computed(() => authStore.isSystemAdmin)
const hasProcessingUploads = computed(() =>
  knowledgeUploads.value.some((item) => ['queued', 'processing'].includes(item.status)),
)
const allSectionsSelected = computed(
  () => uploadForm.sectionCodes.length === allSectionCodes.length,
)
const sectionSelectionIndeterminate = computed(
  () => uploadForm.sectionCodes.length > 0 && !allSectionsSelected.value,
)
const sectionOptions: Array<{ value: KnowledgeSectionCode, label: string }> = [
  { value: 'overview', label: '工程概况与编制依据' },
  { value: 'organization_measures', label: '组织措施' },
  { value: 'construction_plan', label: '施工方案' },
  { value: 'technical_measures', label: '技术措施' },
  { value: 'safety_measures', label: '安全措施' },
  { value: 'risk_identification', label: '风险辨识与预控' },
  { value: 'emergency_plan', label: '应急预案' },
  { value: 'environmental_measures', label: '环境保护与文明施工' },
]
const uploadStatusLabels: Record<KnowledgeCorpusUploadStatus, string> = {
  queued: '等待处理',
  processing: '正在解析并生成向量',
  succeeded: '已入库',
  failed: '处理失败',
}

onMounted(loadProjects)
onBeforeUnmount(stopCorpusPolling)

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

async function openKnowledgeUploadDialog(): Promise<void> {
  uploadDialogVisible.value = true
  await loadKnowledgeUploads()
}

async function loadKnowledgeUploads(): Promise<void> {
  if (!isSystemAdmin.value) {
    return
  }
  uploadHistoryLoading.value = true
  try {
    const response = await fetchKnowledgeCorpusUploads()
    knowledgeUploads.value = response.results
    configureCorpusPolling()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    uploadHistoryLoading.value = false
  }
}

async function submitKnowledgeUpload(): Promise<void> {
  const file = uploadFiles.value[0]?.raw
  if (!file) {
    ElMessage.warning('请选择一个 DOCX 或文本型 PDF 文件')
    return
  }
  uploadSubmitting.value = true
  try {
    const payload = new FormData()
    payload.append('file', file)
    for (const sectionCode of uploadForm.sectionCodes) {
      payload.append('section_codes', sectionCode)
    }
    if (!uploadForm.sectionCodes.length) {
      ElMessage.warning('请至少选择一个适用章节')
      return
    }
    const upload = await uploadKnowledgeCorpus(payload)
    knowledgeUploads.value = [
      upload,
      ...knowledgeUploads.value.filter((item) => item.id !== upload.id),
    ]
    uploadFiles.value = []
    ElMessage.success('资料已上传，正在后台解析、切块并生成 Embedding')
    configureCorpusPolling()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    uploadSubmitting.value = false
  }
}

async function retryKnowledgeUpload(upload: KnowledgeCorpusUpload): Promise<void> {
  try {
    const retried = await retryKnowledgeCorpusUpload(upload.id)
    knowledgeUploads.value = knowledgeUploads.value.map((item) =>
      item.id === retried.id ? retried : item,
    )
    ElMessage.success('已重新提交处理')
    configureCorpusPolling()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function toggleAllSections(value: boolean | string | number): void {
  uploadForm.sectionCodes = value ? [...allSectionCodes] : []
}

function knowledgeStatusType(status: KnowledgeCorpusUploadStatus): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'processing') {
    return 'warning'
  }
  return 'info'
}

function knowledgeStatusLabel(status: KnowledgeCorpusUploadStatus): string {
  return uploadStatusLabels[status]
}

function configureCorpusPolling(): void {
  stopCorpusPolling()
  if (!uploadDialogVisible.value || !hasProcessingUploads.value) {
    return
  }
  corpusPollTimer = window.setTimeout(() => {
    void loadKnowledgeUploads()
  }, 3000)
}

function stopCorpusPolling(): void {
  if (corpusPollTimer !== undefined) {
    window.clearTimeout(corpusPollTimer)
    corpusPollTimer = undefined
  }
}

function closeKnowledgeUploadDialog(): void {
  stopCorpusPolling()
  uploadFiles.value = []
}
</script>

<template>
  <section class="document-generation-page">
    <header class="document-generation-page__header">
      <div>
        <h1>入场资料Agent V1.0</h1>
        <p>选择你有权访问的在执行项目，基于已有资料生成四措两案初稿，并完成事实确认、人工审核和 Word 导出。</p>
      </div>
      <div class="document-generation-page__header-actions">
        <el-button :loading="loading" @click="loadProjects">刷新项目</el-button>
        <el-button
          v-if="isSystemAdmin"
          type="primary"
          plain
          @click="openKnowledgeUploadDialog"
        >
          上传 RAG 资料
        </el-button>
      </div>
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
            popper-class="document-generation-project-select-dropdown"
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

    <el-dialog
      v-model="uploadDialogVisible"
      title="上传四措两案 RAG 资料"
      width="min(900px, 94vw)"
      destroy-on-close
      @closed="closeKnowledgeUploadDialog"
    >
      <el-alert
        title="成品四措两案建议全选，系统会按标题拆分到对应章节；单章资料或前置资料请选择一个最相关章节。Embedding 成功后才会启用。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-form class="knowledge-upload-form" label-position="top">
        <el-form-item label="资料文件" required>
          <el-upload
            v-model:file-list="uploadFiles"
            drag
            action="#"
            accept=".docx,.pdf"
            :auto-upload="false"
            :limit="1"
          >
            <div class="el-upload__text">
              拖放文件到这里，或<em>点击选择文件</em>
            </div>
          </el-upload>
        </el-form-item>
        <el-form-item label="适用章节" required>
          <div class="knowledge-upload-form__sections">
            <el-checkbox
              :model-value="allSectionsSelected"
              :indeterminate="sectionSelectionIndeterminate"
              @change="toggleAllSections"
            >
              全选
            </el-checkbox>
            <el-select
              v-model="uploadForm.sectionCodes"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择至少一个章节"
              style="width: 100%"
            >
              <el-option
                v-for="option in sectionOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>
        </el-form-item>
        <el-button
          type="primary"
          :loading="uploadSubmitting"
          @click="submitKnowledgeUpload"
        >
          上传并生成 Embedding
        </el-button>
      </el-form>

      <div class="knowledge-upload-history">
        <div class="knowledge-upload-history__heading">
          <h3>最近上传</h3>
          <el-button
            link
            type="primary"
            :loading="uploadHistoryLoading"
            @click="loadKnowledgeUploads"
          >
            刷新状态
          </el-button>
        </div>
        <el-table
          v-loading="uploadHistoryLoading"
          :data="knowledgeUploads"
          empty-text="暂无上传记录"
        >
          <el-table-column prop="filename" label="文件" min-width="180" show-overflow-tooltip />
          <el-table-column label="适用章节" min-width="180">
            <template #default="{ row }">{{ row.section_names.join('、') }}</template>
          </el-table-column>
          <el-table-column label="状态" min-width="150">
            <template #default="{ row }">
              <el-tag :type="knowledgeStatusType(row.status)">
                {{ knowledgeStatusLabel(row.status) }}
              </el-tag>
              <div v-if="row.status === 'succeeded'" class="knowledge-upload-history__detail">
                {{ row.chunk_count }} 个知识块 · {{ row.embedding_model_alias }} / {{ row.embedding_dimension }}维
                <div>已索引：{{ row.indexed_section_names.join('、') }}</div>
                <div v-if="row.skipped_section_names.length">
                  未识别：{{ row.skipped_section_names.join('、') }}
                </div>
              </div>
              <div v-else-if="row.status === 'failed'" class="knowledge-upload-history__error">
                {{ row.error_message }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'failed'"
                link
                type="primary"
                @click="retryKnowledgeUpload(row)"
              >
                重新处理
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
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

.document-generation-page__header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.document-generation-page__selector :deep(.el-form-item) {
  margin-bottom: 0;
}

:global(.document-generation-project-select-dropdown .el-select-dropdown__wrap) {
  max-height: 250px;
}

.knowledge-upload-form {
  margin-top: 18px;
}

.knowledge-upload-form__sections {
  display: grid;
  width: 100%;
  gap: 8px;
}

.knowledge-upload-history {
  margin-top: 24px;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 16px;
}

.knowledge-upload-history__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.knowledge-upload-history__heading h3 {
  margin: 0;
}

.knowledge-upload-history__detail,
.knowledge-upload-history__error {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
}

.knowledge-upload-history__detail {
  color: var(--el-text-color-secondary);
}

.knowledge-upload-history__error {
  color: var(--el-color-danger);
}

@media (max-width: 900px) {
  .document-generation-page__header {
    flex-direction: column;
  }

}
</style>
