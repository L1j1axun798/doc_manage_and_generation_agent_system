<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import { downloadDocument, fetchDocument, fetchDocuments } from '@/modules/documents/api/documents.api'
import type { DocumentItem } from '@/modules/documents/documents.types'
import type { Project } from '@/modules/projects/projects.types'
import { formatDateTime } from '@/shared/utils/format'
import {
  addGenerationSources,
  approveGenerationTask,
  confirmGenerationFacts,
  createGenerationTask,
  exportGenerationTask,
  extractGenerationFacts,
  fetchGenerationTask,
  fetchGenerationTasks,
  fetchGenerationTemplates,
  generateEntryPlan,
  regenerateSection,
  retryGenerationTask,
  setGeneratedSectionLock,
  submitGenerationReview,
  updateGeneratedSection,
} from '../api/document-generation.api'
import {
  BUSINESS_TYPE,
  DOCUMENT_PURPOSE,
  type ConfirmedFactPayload,
  type DocumentGenerationTemplate,
  type FactProposal,
  type GeneratedSection,
  type GenerationTask,
  type GenerationTaskStatus,
  type SourceLocator,
} from '../document-generation.types'
import {
  GENERATION_POLL_INTERVAL_MS,
  isEligibleEntrySource,
  shouldPollGenerationTask,
} from '../workflow'

interface FactDraft {
  selected: boolean
  field: string
  valueText: string
  valueType: string
  sourceDocumentVersionId: number | null
  locator: SourceLocator
  textQuote: string
  confidence: number
}

const props = defineProps<{
  project: Project
}>()

const authStore = useAuthStore()
const loading = ref(false)
const actionLoading = ref(false)
const createDialogVisible = ref(false)
const templates = ref<DocumentGenerationTemplate[]>([])
const documents = ref<DocumentItem[]>([])
const tasks = ref<GenerationTask[]>([])
const selectedTask = ref<GenerationTask | null>(null)
const factDrafts = ref<FactDraft[]>([])
const sectionDrafts = reactive<Record<string, string>>({})
const createForm = reactive<{
  templateId: number | null
  sourceVersionIds: number[]
}>({
  templateId: null,
  sourceVersionIds: [],
})
let pollTimer: number | undefined

const eligibleDocuments = computed(() => documents.value.filter(isEligibleEntrySource))
const isProjectActive = computed(() => props.project.status === 'active')
const canApprove = computed(
  () =>
    authStore.user?.role === 'system_admin'
    || authStore.user?.role === 'project_manager',
)
const allSectionsLocked = computed(
  () =>
    Boolean(selectedTask.value?.sections.length)
    && selectedTask.value?.sections.every((section) => section.is_locked),
)

const statusLabels: Record<GenerationTaskStatus, string> = {
  draft: '待选择资料',
  extracting: '正在提取事实',
  needs_confirmation: '待确认事实',
  ready: '可开始生成',
  queued: '已进入生成队列',
  generating: '正在生成',
  review_required: '待人工审核',
  approved: '已批准，待导出',
  exported: '已导出',
  failed: '执行失败',
}

onMounted(loadInitialData)
onBeforeUnmount(stopPolling)

async function loadInitialData(): Promise<void> {
  loading.value = true
  try {
    const [templateRows, documentRows, taskRows] = await Promise.all([
      fetchGenerationTemplates(),
      fetchAllProjectDocuments(),
      fetchGenerationTasks(props.project.id),
    ])
    templates.value = templateRows
    documents.value = documentRows
    tasks.value = taskRows.results
    if (tasks.value[0]) {
      await selectTask(tasks.value[0])
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function fetchAllProjectDocuments(): Promise<DocumentItem[]> {
  const rows: DocumentItem[] = []
  let page = 1
  while (page <= 50) {
    const response = await fetchDocuments({
      project: props.project.id,
      page,
      ordering: 'title',
    })
    rows.push(...response.results)
    if (!response.next || rows.length >= response.count) {
      break
    }
    page += 1
  }
  return rows
}

async function refreshTasks(): Promise<void> {
  const response = await fetchGenerationTasks(props.project.id)
  tasks.value = response.results
}

async function selectTask(task: GenerationTask): Promise<void> {
  selectedTask.value = await fetchGenerationTask(task.id)
  hydrateTaskDrafts()
  configurePolling()
}

async function refreshSelectedTask(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  const previousStatus = selectedTask.value.status
  selectedTask.value = await fetchGenerationTask(selectedTask.value.id)
  if (
    selectedTask.value.status !== previousStatus
    || selectedTask.value.status === 'review_required'
  ) {
    hydrateTaskDrafts()
    await refreshTasks()
  }
  configurePolling()
}

function hydrateTaskDrafts(): void {
  const task = selectedTask.value
  if (!task) {
    return
  }
  if (task.status === 'needs_confirmation') {
    factDrafts.value = (task.facts_snapshot as FactProposal[]).map((proposal) => {
      const evidence = proposal.evidence?.[0]
      return {
        selected: true,
        field: proposal.field,
        valueText: serializeFactValue(proposal.value),
        valueType: proposal.value_type,
        sourceDocumentVersionId: evidence?.source_document_version_id ?? null,
        locator: { ...(evidence?.locator || {}) },
        textQuote: evidence?.locator.text_quote || '',
        confidence: proposal.confidence ?? evidence?.confidence ?? 1,
      }
    })
  }
  if (task.status === 'review_required') {
    for (const section of task.sections) {
      sectionDrafts[section.section_code] = section.content
    }
  }
}

function configurePolling(): void {
  stopPolling()
  if (!selectedTask.value || !shouldPollGenerationTask(selectedTask.value.status)) {
    return
  }
  pollTimer = window.setInterval(() => {
    void refreshSelectedTask().catch((error) => {
      stopPolling()
      ElMessage.error(getErrorMessage(error))
    })
  }, GENERATION_POLL_INTERVAL_MS)
}

function stopPolling(): void {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

function openCreateDialog(): void {
  createForm.templateId = templates.value[0]?.id ?? null
  createForm.sourceVersionIds = []
  createDialogVisible.value = true
}

async function createAndExtract(): Promise<void> {
  if (!createForm.templateId || createForm.sourceVersionIds.length === 0) {
    ElMessage.warning('请选择模板和至少一份已有项目资料')
    return
  }
  actionLoading.value = true
  try {
    let task = await createGenerationTask({
      project_id: props.project.id,
      template_id: createForm.templateId,
      document_purpose: DOCUMENT_PURPOSE,
      business_type: BUSINESS_TYPE,
      idempotency_key: window.crypto.randomUUID(),
      facts: [
        { field: 'project_name', value: props.project.name, value_type: 'string' },
        { field: 'project_code', value: props.project.code, value_type: 'string' },
      ],
    })
    task = await addGenerationSources(task.id, createForm.sourceVersionIds)
    task = await extractGenerationFacts(task.id)
    createDialogVisible.value = false
    selectedTask.value = task
    await refreshTasks()
    configurePolling()
    ElMessage.success('已提交事实提取，页面会自动刷新进度')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}

function addManualFact(): void {
  factDrafts.value.push({
    selected: true,
    field: '',
    valueText: '',
    valueType: 'string',
    sourceDocumentVersionId: selectedTask.value?.sources[0]?.document_version_id ?? null,
    locator: {},
    textQuote: '',
    confidence: 1,
  })
}

async function confirmFacts(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  const selected = factDrafts.value.filter((fact) => fact.selected)
  if (selected.length === 0) {
    ElMessage.warning('至少确认一个事实')
    return
  }
  let payload: ConfirmedFactPayload[]
  try {
    payload = selected.map(toConfirmedFact)
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '事实格式不正确')
    return
  }
  await runAction(async () => {
    selectedTask.value = await confirmGenerationFacts(selectedTask.value!.id, payload)
    await refreshTasks()
    ElMessage.success('事实已确认，可以开始生成')
  })
}

function toConfirmedFact(draft: FactDraft): ConfirmedFactPayload {
  if (!draft.field.trim() || !draft.sourceDocumentVersionId) {
    throw new Error('事实字段和来源资料不能为空')
  }
  const locator: SourceLocator = {
    ...draft.locator,
    text_quote: draft.textQuote.trim() || undefined,
  }
  if (
    locator.paragraph_index === undefined
    && locator.page === undefined
    && locator.table_index === undefined
    && !locator.text_quote
  ) {
    throw new Error(`事实“${draft.field}”缺少来源定位`)
  }
  return {
    field: draft.field.trim(),
    value: parseFactValue(draft.valueText, draft.valueType),
    value_type: draft.valueType,
    source_document_version_id: draft.sourceDocumentVersionId,
    locator,
    confidence: draft.confidence,
  }
}

function parseFactValue(value: string, valueType: string): unknown {
  if (valueType === 'integer') {
    const parsed = Number.parseInt(value, 10)
    if (!Number.isFinite(parsed)) {
      throw new Error('整数事实填写不正确')
    }
    return parsed
  }
  if (valueType === 'number') {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) {
      throw new Error('数值事实填写不正确')
    }
    return parsed
  }
  if (['array', 'object', 'json'].includes(valueType)) {
    return JSON.parse(value)
  }
  if (valueType === 'boolean') {
    return ['true', '1', '是'].includes(value.trim().toLowerCase())
  }
  return value.trim()
}

function serializeFactValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2)
}

async function startGeneration(): Promise<void> {
  await runTaskAction(
    (taskId) => generateEntryPlan(taskId),
    '已进入生成队列',
  )
}

async function retryTask(): Promise<void> {
  await runTaskAction(
    (taskId) => retryGenerationTask(taskId),
    '已重新排队',
  )
}

async function saveSection(section: GeneratedSection): Promise<void> {
  await runAction(async () => {
    await updateGeneratedSection(
      selectedTask.value!.id,
      section.section_code,
      sectionDrafts[section.section_code] || '',
      section.revision,
    )
    await refreshSelectedTask()
    ElMessage.success('章节已保存')
  })
}

async function toggleSectionLock(section: GeneratedSection): Promise<void> {
  await runAction(async () => {
    await setGeneratedSectionLock(
      selectedTask.value!.id,
      section.section_code,
      !section.is_locked,
    )
    await refreshSelectedTask()
    ElMessage.success(section.is_locked ? '章节已解锁' : '章节已锁定')
  })
}

async function regenerate(section: GeneratedSection): Promise<void> {
  await runAction(async () => {
    selectedTask.value = await regenerateSection(
      selectedTask.value!.id,
      section.section_code,
    )
    configurePolling()
    ElMessage.success('该章节已重新排队')
  })
}

async function submitReview(): Promise<void> {
  await runTaskAction(
    (taskId) => submitGenerationReview(taskId, '已完成人工复核并提交'),
    '已提交审核记录',
  )
}

async function approveTask(): Promise<void> {
  await runTaskAction(
    (taskId) => approveGenerationTask(taskId, '技术负责人批准'),
    '已批准，可以导出Word',
  )
}

async function exportTask(): Promise<void> {
  await runTaskAction(
    (taskId) => exportGenerationTask(taskId, window.crypto.randomUUID()),
    '已导出到当前项目的“技术方案”目录',
  )
}

async function downloadOutput(): Promise<void> {
  const documentId = selectedTask.value?.output_document_id
  if (!documentId) {
    return
  }
  await runAction(async () => {
    const document = await fetchDocument(documentId)
    await downloadDocument(document)
  })
}

async function runTaskAction(
  action: (taskId: string) => Promise<GenerationTask>,
  successMessage: string,
): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  await runAction(async () => {
    selectedTask.value = await action(selectedTask.value!.id)
    await refreshTasks()
    configurePolling()
    ElMessage.success(successMessage)
  })
}

async function runAction(action: () => Promise<void>): Promise<void> {
  actionLoading.value = true
  try {
    await action()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
}
</script>

<template>
  <section class="doc-agent" v-loading="loading">
    <el-alert
      class="doc-agent__notice"
      title="本功能只生成入场资料（四措两案）初稿，不生成检测报告、实测结论或完工报告。"
      type="warning"
      :closable="false"
      show-icon
    />

    <div class="doc-agent__toolbar">
      <div>
        <h2>入场资料编制（四措两案）</h2>
        <p>选择系统中已有的项目资料，Agent提取事实；你确认后再生成、审核和导出。</p>
      </div>
      <div>
        <el-button :loading="loading" @click="loadInitialData">刷新</el-button>
        <el-button
          type="primary"
          :disabled="!isProjectActive || templates.length === 0"
          @click="openCreateDialog"
        >
          新建编制任务
        </el-button>
      </div>
    </div>

    <el-empty v-if="!tasks.length && !loading" description="暂无四措两案编制任务" />
    <el-table
      v-else
      :data="tasks"
      highlight-current-row
      row-key="id"
      @current-change="(row: GenerationTask | undefined) => row && selectTask(row)"
    >
      <el-table-column prop="template_name" label="模板" min-width="150" />
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tag :type="row.status === 'failed' ? 'danger' : row.status === 'exported' ? 'success' : 'info'">
            {{ statusLabels[row.status as GenerationTaskStatus] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="进度" width="90" />
      <el-table-column label="创建时间" min-width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <el-card v-if="selectedTask" class="doc-agent__task" shadow="never">
      <template #header>
        <div class="doc-agent__task-header">
          <strong>任务 {{ selectedTask.id.slice(0, 8) }}</strong>
          <el-tag>{{ statusLabels[selectedTask.status] }}</el-tag>
        </div>
      </template>

      <el-progress :percentage="selectedTask.progress" />
      <el-descriptions :column="2" border class="doc-agent__meta">
        <el-descriptions-item label="模板">{{ selectedTask.template_name }}</el-descriptions-item>
        <el-descriptions-item label="来源资料">{{ selectedTask.sources.length }}份</el-descriptions-item>
        <el-descriptions-item label="模型">{{ selectedTask.model_alias || '尚未调用' }}</el-descriptions-item>
        <el-descriptions-item label="尝试次数">{{ selectedTask.generation_attempts }}</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="selectedTask.error_message"
        :title="`${selectedTask.error_code}: ${selectedTask.error_message}`"
        type="error"
        :closable="false"
        show-icon
      />

      <template v-if="selectedTask.status === 'needs_confirmation'">
        <h3>确认Agent提取的项目事实</h3>
        <el-alert
          v-if="selectedTask.fact_conflicts.length"
          title="存在来源冲突，请核对后只保留正确值。"
          type="warning"
          :closable="false"
        />
        <el-table :data="factDrafts" row-key="field">
          <el-table-column label="采用" width="65">
            <template #default="{ row }"><el-checkbox v-model="row.selected" /></template>
          </el-table-column>
          <el-table-column label="字段" min-width="150">
            <template #default="{ row }"><el-input v-model="row.field" /></template>
          </el-table-column>
          <el-table-column label="值" min-width="220">
            <template #default="{ row }">
              <el-input v-model="row.valueText" type="textarea" :rows="2" />
            </template>
          </el-table-column>
          <el-table-column label="来源" min-width="190">
            <template #default="{ row }">
              <el-select v-model="row.sourceDocumentVersionId" style="width: 100%">
                <el-option
                  v-for="source in selectedTask.sources"
                  :key="source.document_version_id"
                  :label="source.document_title"
                  :value="source.document_version_id"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="来源原文" min-width="240">
            <template #default="{ row }">
              <el-input v-model="row.textQuote" placeholder="Agent自动给出；人工补充时请粘贴原文" />
            </template>
          </el-table-column>
        </el-table>
        <div class="doc-agent__actions">
          <el-button @click="addManualFact">补充事实</el-button>
          <el-button type="primary" :loading="actionLoading" @click="confirmFacts">
            确认事实
          </el-button>
        </div>
      </template>

      <div v-if="selectedTask.status === 'ready'" class="doc-agent__actions">
        <el-button
          type="primary"
          :loading="actionLoading"
          :disabled="!isProjectActive"
          @click="startGeneration"
        >
          生成四措两案初稿
        </el-button>
      </div>

      <div v-if="selectedTask.status === 'failed'" class="doc-agent__actions">
        <el-button
          type="primary"
          :loading="actionLoading"
          :disabled="!isProjectActive"
          @click="retryTask"
        >
          重试当前步骤
        </el-button>
      </div>

      <template v-if="selectedTask.status === 'review_required'">
        <h3>逐章人工审核</h3>
        <el-collapse>
          <el-collapse-item
            v-for="section in selectedTask.sections"
            :key="section.section_code"
            :name="section.section_code"
          >
            <template #title>
              <span>{{ section.title }}</span>
              <el-tag class="doc-agent__lock-tag" :type="section.is_locked ? 'success' : 'warning'">
                {{ section.is_locked ? '已锁定' : `修订 ${section.revision}` }}
              </el-tag>
            </template>
            <el-input
              v-model="sectionDrafts[section.section_code]"
              type="textarea"
              :rows="12"
              :disabled="section.is_locked"
            />
            <div v-if="section.validation_issues.length" class="doc-agent__issues">
              <el-alert
                v-for="issue in section.validation_issues"
                :key="issue.code + issue.message"
                :title="`${issue.code}: ${issue.message}`"
                :type="issue.severity === 'error' ? 'error' : 'warning'"
                :closable="false"
              />
            </div>
            <details v-if="section.citations.length">
              <summary>查看来源引用（{{ section.citations.length }}）</summary>
              <pre>{{ JSON.stringify(section.citations, null, 2) }}</pre>
            </details>
            <div class="doc-agent__actions">
              <el-button
                :disabled="section.is_locked"
                :loading="actionLoading"
                @click="saveSection(section)"
              >
                保存修改
              </el-button>
              <el-button :loading="actionLoading" @click="toggleSectionLock(section)">
                {{ section.is_locked ? '解锁' : '确认并锁定' }}
              </el-button>
              <el-button
                :disabled="section.is_locked"
                :loading="actionLoading"
                @click="regenerate(section)"
              >
                重新生成本章
              </el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
        <div class="doc-agent__actions">
          <el-button :loading="actionLoading" @click="submitReview">记录提交审核</el-button>
          <el-button
            v-if="canApprove"
            type="primary"
            :disabled="!allSectionsLocked || !isProjectActive"
            :loading="actionLoading"
            @click="approveTask"
          >
            技术负责人批准
          </el-button>
        </div>
      </template>

      <div v-if="selectedTask.status === 'approved'" class="doc-agent__actions">
        <el-button
          v-if="canApprove"
          type="primary"
          :loading="actionLoading"
          :disabled="!isProjectActive"
          @click="exportTask"
        >
          导出Word到“技术方案”
        </el-button>
      </div>

      <div v-if="selectedTask.status === 'exported'" class="doc-agent__actions">
        <el-button
          type="success"
          :loading="actionLoading"
          :disabled="!selectedTask.output_document_id"
          @click="downloadOutput"
        >
          下载已批准Word
        </el-button>
      </div>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新建四措两案编制任务" width="680px">
      <el-form label-position="top">
        <el-form-item label="四措两案模板">
          <el-select v-model="createForm.templateId" style="width: 100%">
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="`${template.client_name || '通用'} / ${template.code} ${template.version}`"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="已有项目资料（可多选）">
          <el-select
            v-model="createForm.sourceVersionIds"
            multiple
            filterable
            style="width: 100%"
            placeholder="选择任务通知、技术要求等已有资料"
          >
            <el-option
              v-for="document in eligibleDocuments"
              :key="document.current_version!.id"
              :label="`${document.folder_name} / ${document.title}`"
              :value="document.current_version!.id"
            />
          </el-select>
        </el-form-item>
        <el-alert
          title="这里不会新增合同上传入口；只读取你本来就有权查看的项目资料。"
          type="info"
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionLoading" @click="createAndExtract">
          创建并自动提取事实
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.doc-agent {
  display: grid;
  gap: 18px;
}

.doc-agent__notice {
  margin-bottom: 4px;
}

.doc-agent__toolbar,
.doc-agent__task-header,
.doc-agent__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.doc-agent__toolbar h2,
.doc-agent__toolbar p {
  margin: 0;
}

.doc-agent__toolbar p {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
}

.doc-agent__task {
  margin-top: 6px;
}

.doc-agent__meta {
  margin: 18px 0;
}

.doc-agent__actions {
  justify-content: flex-end;
  margin-top: 16px;
}

.doc-agent__lock-tag {
  margin-left: 12px;
}

.doc-agent__issues {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

details {
  margin-top: 12px;
}

pre {
  max-height: 260px;
  overflow: auto;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .doc-agent__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
