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
  approveGenerationTask,
  confirmAndGenerate,
  exportGenerationTask,
  fetchGenerationEvents,
  fetchGenerationTask,
  fetchGenerationTasks,
  fetchGenerationTemplates,
  generateEntryPlan,
  lockAllGeneratedSections,
  regenerateSection,
  retryGenerationTask,
  setGeneratedSectionLock,
  startGenerationPipeline,
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
  type GenerationTraceEvent,
  type SourceLocator,
} from '../document-generation.types'
import GenerationWorkflowTrace from './GenerationWorkflowTrace.vue'
import {
  factFieldDefinition,
  GENERATION_POLL_INTERVAL_MS,
  isEligibleEntrySource,
  missingRequiredFactFields,
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
  codeValues: string[]
  riskEvidence: Record<string, string>
  isRequired: boolean
  isManual: boolean
}

const props = defineProps<{
  project: Project
}>()

const authStore = useAuthStore()
const loading = ref(false)
const actionLoading = ref(false)
const openingTaskId = ref<string | null>(null)
const createDialogVisible = ref(false)
const templates = ref<DocumentGenerationTemplate[]>([])
const documents = ref<DocumentItem[]>([])
const tasks = ref<GenerationTask[]>([])
const selectedTask = ref<GenerationTask | null>(null)
const workflowEvents = ref<GenerationTraceEvent[]>([])
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
const criticalFactDrafts = computed(() => factDrafts.value.filter((fact) => fact.isRequired))
const supplementalFactDrafts = computed(() => factDrafts.value.filter((fact) => !fact.isRequired))
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
const selectedTemplate = computed(
  () => templates.value.find((template) => template.id === selectedTask.value?.template_id) || null,
)

const statusLabels: Record<GenerationTaskStatus, string> = {
  draft: '待选择资料',
  extracting: '正在提取事实',
  needs_confirmation: '待确认事实',
  ready: '可开始生成',
  queued: '已进入生成队列',
  generating: '正在生成',
  review_required: '待人工审核',
  pending_approval: '已提交，待技术负责人批准',
  approved: '已批准，待导出',
  exported: '已导出',
  failed: '执行失败',
}

onMounted(loadInitialData)
onBeforeUnmount(stopPolling)

async function loadInitialData(): Promise<void> {
  stopPolling()
  selectedTask.value = null
  workflowEvents.value = []
  factDrafts.value = []
  loading.value = true
  try {
    const [templateRows, documentRows, taskRows] = await Promise.all([
      fetchGenerationTemplates(),
      fetchAllProjectDocuments(),
      fetchAllGenerationTasks(),
    ])
    templates.value = templateRows
    documents.value = documentRows
    tasks.value = taskRows
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function fetchAllGenerationTasks(): Promise<GenerationTask[]> {
  const rows: GenerationTask[] = []
  let page = 1
  while (page <= 50) {
    const response = await fetchGenerationTasks(props.project.id, page)
    rows.push(...response.results)
    if (!response.next || rows.length >= response.count) {
      break
    }
    page += 1
  }
  return rows
}

async function fetchAllProjectDocuments(): Promise<DocumentItem[]> {
  const rows: DocumentItem[] = []
  let page = 1
  while (page <= 50) {
    const response = await fetchDocuments({
      project: props.project.id,
      source_type: 'entrance_material',
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
  tasks.value = await fetchAllGenerationTasks()
}

async function openConversation(task: GenerationTask): Promise<void> {
  openingTaskId.value = task.id
  try {
    selectedTask.value = await fetchGenerationTask(task.id)
    workflowEvents.value = await fetchGenerationEvents(task.id)
    hydrateTaskDrafts()
    configurePolling()
  } catch (error) {
    selectedTask.value = null
    workflowEvents.value = []
    ElMessage.error(getErrorMessage(error))
  } finally {
    openingTaskId.value = null
  }
}

function returnToConversationList(): void {
  stopPolling()
  selectedTask.value = null
  workflowEvents.value = []
  factDrafts.value = []
  void refreshTasks().catch((error) => {
    ElMessage.error(getErrorMessage(error))
  })
}

function conversationTitle(task: GenerationTask): string {
  return `四措两案编制 · ${formatDateTime(task.created_at)}`
}

async function refreshCurrentConversation(): Promise<void> {
  await runAction(refreshSelectedTask)
}

async function refreshSelectedTask(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  const previousStatus = selectedTask.value.status
  const [task, newEvents] = await Promise.all([
    fetchGenerationTask(selectedTask.value.id),
    fetchGenerationEvents(
      selectedTask.value.id,
      workflowEvents.value.at(-1)?.sequence || 0,
    ),
  ])
  selectedTask.value = task
  workflowEvents.value.push(...newEvents)
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
    const proposalFields = new Set(
      (task.facts_snapshot as FactProposal[]).map((proposal) => proposal.field),
    )
    const conflictDefaults = task.fact_conflicts.flatMap((conflict) => {
      const field = typeof conflict.field === 'string' ? conflict.field : ''
      const candidates = Array.isArray(conflict.candidates)
        ? conflict.candidates as FactProposal[]
        : []
      const preferred = [...candidates].sort(
        (left, right) => Number(right.confidence || 0) - Number(left.confidence || 0),
      )[0]
      return field && preferred && !proposalFields.has(field)
        ? [{ ...preferred, field }]
        : []
    })
    const proposals = [
      ...(task.facts_snapshot as FactProposal[]),
      ...conflictDefaults,
    ]
    const requiredFields = selectedTemplate.value?.required_fact_fields || []
    const requiredSet = new Set(requiredFields)
    const drafts = proposals.map((proposal) => {
      const evidence = proposal.evidence?.[0]
      const values = Array.isArray(proposal.value) ? proposal.value : []
      const codeValues = values.filter((value): value is string => typeof value === 'string')
      const riskEvidence = Object.fromEntries(
        values
          .filter(
            (value): value is { risk_code: string, evidence: string } =>
              typeof value === 'object'
              && value !== null
              && typeof (value as Record<string, unknown>).risk_code === 'string'
              && typeof (value as Record<string, unknown>).evidence === 'string',
          )
          .map((value) => [value.risk_code, value.evidence]),
      )
      return {
        selected: true,
        field: proposal.field,
        valueText: serializeFactValue(proposal.value),
        valueType: proposal.value_type,
        sourceDocumentVersionId: evidence?.source_document_version_id ?? null,
        locator: { ...(evidence?.locator || {}) },
        textQuote: evidence?.locator.text_quote || '',
        confidence: proposal.confidence ?? evidence?.confidence ?? 1,
        codeValues: proposal.field === 'risk_evidence_items'
          ? Object.keys(riskEvidence)
          : codeValues,
        riskEvidence,
        isRequired: requiredSet.has(proposal.field),
        isManual: false,
      }
    })
    for (const field of missingRequiredFactFields(requiredFields, proposals)) {
      const definition = factFieldDefinition(field)
      drafts.push({
        selected: true,
        field,
        valueText: '',
        valueType: definition.valueType,
        sourceDocumentVersionId: task.sources[0]?.document_version_id ?? null,
        locator: {},
        textQuote: '',
        confidence: 1,
        codeValues: [],
        riskEvidence: {},
        isRequired: true,
        isManual: false,
      })
    }
    factDrafts.value = drafts
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
  createForm.sourceVersionIds = eligibleDocuments.value
    .map((document) => document.current_version?.id)
    .filter((id): id is number => typeof id === 'number')
  createDialogVisible.value = true
}

async function createAndExtract(): Promise<void> {
  if (!createForm.templateId || createForm.sourceVersionIds.length === 0) {
    ElMessage.warning('请选择模板和至少一份当前项目的入场前置资料')
    return
  }
  actionLoading.value = true
  try {
    const task = await startGenerationPipeline({
      project_id: props.project.id,
      template_id: createForm.templateId,
      document_version_ids: createForm.sourceVersionIds,
      document_purpose: DOCUMENT_PURPOSE,
      business_type: BUSINESS_TYPE,
      idempotency_key: window.crypto.randomUUID(),
      facts: [
        { field: 'project_name', value: props.project.name, value_type: 'string' },
        { field: 'project_code', value: props.project.code, value_type: 'string' },
      ],
    })
    createDialogVisible.value = false
    selectedTask.value = task
    workflowEvents.value = await fetchGenerationEvents(task.id)
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
    codeValues: [],
    riskEvidence: {},
    isRequired: false,
    isManual: true,
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
  const missingRequired = (selectedTemplate.value?.required_fact_fields || [])
    .filter((field) => !selected.some((fact) => fact.field === field))
    .map((field) => factFieldDefinition(field).label)
  if (missingRequired.length) {
    ElMessage.warning(`请先确认必填事实：${missingRequired.join('、')}`)
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
    selectedTask.value = await confirmAndGenerate(selectedTask.value!.id, payload)
    await refreshTasks()
    configurePolling()
    ElMessage.success('关键事实已确认，Agent已开始逐章编制')
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
    value: draftFactValue(draft),
    value_type: draft.valueType,
    source_document_version_id: draft.sourceDocumentVersionId,
    locator,
    confidence: draft.confidence,
  }
}

function draftFactValue(draft: FactDraft): unknown {
  if (draft.field === 'inspection_component_codes' || draft.field === 'inspection_method_codes') {
    if (draft.codeValues.length === 0) {
      throw new Error(`${factFieldDefinition(draft.field).label}至少选择一项`)
    }
    return draft.codeValues
  }
  if (draft.field === 'risk_evidence_items') {
    return draft.codeValues.map((riskCode) => {
      const evidence = draft.riskEvidence[riskCode]?.trim()
      if (!evidence) {
        throw new Error(`${riskOptionLabel(riskCode)}缺少事实依据`)
      }
      return { risk_code: riskCode, evidence }
    })
  }
  const value = parseFactValue(draft.valueText, draft.valueType)
  if (draft.isRequired && typeof value === 'string' && !value) {
    throw new Error(`${factFieldDefinition(draft.field).label}不能为空`)
  }
  return value
}

function riskOptionLabel(code: string): string {
  return factFieldDefinition('risk_evidence_items').options
    ?.find((option) => option.value === code)?.label || code
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

function templateHint(template: DocumentGenerationTemplate): string {
  const name = `${template.display_name} ${template.filename}`
  if (name.includes('扫塔') || name.includes('塔筒')) {
    return '适用于扫塔、塔筒焊缝或塔筒部件探伤的Word版式'
  }
  if (name.includes('主机')) {
    return '适用于主机设备出质保检测的Word版式'
  }
  return '适用于风电机组质保期满综合检测的Word版式'
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

async function lockAllSections(): Promise<void> {
  await runAction(async () => {
    selectedTask.value = await lockAllGeneratedSections(selectedTask.value!.id)
    await refreshSelectedTask()
    ElMessage.success('所有无阻断错误的章节已确认并锁定')
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
        <h2 v-if="selectedTask">{{ conversationTitle(selectedTask) }}</h2>
        <h2 v-else>{{ project.name }}的编制会话</h2>
        <p v-if="selectedTask">查看本次会话的编制进度，并继续完成事实确认、审核或导出。</p>
        <p v-else>历史编制按会话列出；选择一项后才会打开详细内容。</p>
      </div>
      <div class="doc-agent__toolbar-actions">
        <el-button v-if="selectedTask" @click="returnToConversationList">返回会话列表</el-button>
        <el-button
          v-if="selectedTask"
          :loading="actionLoading"
          @click="refreshCurrentConversation"
        >
          刷新当前会话
        </el-button>
        <el-button v-else :loading="loading" @click="loadInitialData">刷新列表</el-button>
        <el-button
          v-if="!selectedTask"
          type="primary"
          :disabled="!isProjectActive || templates.length === 0"
          @click="openCreateDialog"
        >
          新建会话
        </el-button>
      </div>
    </div>

    <section v-if="!selectedTask" class="doc-agent__conversation-directory">
      <div class="doc-agent__directory-heading">
        <div>
          <h3>历史会话</h3>
          <span>{{ tasks.length }} 项</span>
        </div>
        <p>此处只展示会话名称和状态，不预览会话详情。</p>
      </div>
      <el-empty v-if="!tasks.length && !loading" description="暂无四措两案编制会话" />
      <div v-else class="doc-agent__conversation-list" aria-label="历史编制会话">
        <button
          v-for="task in tasks"
          :key="task.id"
          class="doc-agent__conversation-item"
          type="button"
          :disabled="openingTaskId !== null"
          @click="openConversation(task)"
        >
          <span class="doc-agent__conversation-copy">
            <strong>{{ conversationTitle(task) }}</strong>
            <small>{{ task.template_name || '默认四措两案模板' }}</small>
          </span>
          <span class="doc-agent__conversation-state">
            <el-tag
              size="small"
              :type="task.status === 'failed' ? 'danger' : task.status === 'exported' ? 'success' : 'info'"
            >
              {{ statusLabels[task.status] }}
            </el-tag>
            <small v-if="openingTaskId === task.id">正在打开…</small>
            <small v-else>{{ task.created_by_name || '当前用户' }}</small>
          </span>
        </button>
      </div>
    </section>

    <el-card v-if="selectedTask" class="doc-agent__task" shadow="never">
      <template #header>
        <div class="doc-agent__task-header">
          <strong>{{ conversationTitle(selectedTask) }}</strong>
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

      <GenerationWorkflowTrace :task="selectedTask" :events="workflowEvents" />

      <template v-if="selectedTask.status === 'needs_confirmation'">
        <h3>快速核对5项关键事实</h3>
        <el-alert
          title="通常只需核对下列内容，然后点一次“确认并开始编制”。来源定位和其他识别信息已收进折叠项。"
          type="info"
          :closable="false"
          show-icon
        />
        <el-alert
          v-if="selectedTask.fact_conflicts.length"
          title="不同资料存在同名事实冲突。系统已预填置信度较高的候选值，请重点核对下列项目。"
          type="warning"
          :closable="false"
        />
        <el-table :data="criticalFactDrafts" row-key="field">
          <el-table-column label="关键项目事实" min-width="180">
            <template #default="{ row }">
              <div class="doc-agent__fact-name">
                <span>{{ factFieldDefinition(row.field).label }}</span>
                <el-tag size="small" type="danger">需确认</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="Agent识别结果（可直接修改）" min-width="520">
            <template #default="{ row }">
              <template
                v-if="
                  row.field === 'inspection_component_codes'
                  || row.field === 'inspection_method_codes'
                "
              >
                <el-select
                  v-model="row.codeValues"
                  multiple
                  filterable
                  :placeholder="`请选择${factFieldDefinition(row.field).label}`"
                  style="width: 100%"
                >
                  <el-option
                    v-for="option in factFieldDefinition(row.field).options"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </template>
              <template v-else-if="row.field === 'risk_evidence_items'">
                <el-select
                  v-model="row.codeValues"
                  multiple
                  filterable
                  placeholder="选择资料明确支持的风险；没有可不选"
                  style="width: 100%"
                >
                  <el-option
                    v-for="option in factFieldDefinition(row.field).options"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-input
                  v-for="riskCode in row.codeValues"
                  :key="riskCode"
                  v-model="row.riskEvidence[riskCode]"
                  class="doc-agent__risk-evidence"
                  :placeholder="`${riskOptionLabel(riskCode)}的来源依据`"
                >
                  <template #prepend>{{ riskOptionLabel(riskCode) }}</template>
                </el-input>
              </template>
              <el-input v-else v-model="row.valueText" type="textarea" :rows="2" />
              <div class="doc-agent__field-help">
                {{ factFieldDefinition(row.field).help }}
              </div>
              <details class="doc-agent__provenance">
                <summary>查看或修正来源依据</summary>
                <el-select v-model="row.sourceDocumentVersionId" style="width: 100%">
                  <el-option
                    v-for="source in selectedTask.sources"
                    :key="source.document_version_id"
                    :label="source.document_title"
                    :value="source.document_version_id"
                  />
                </el-select>
                <el-input
                  v-model="row.textQuote"
                  placeholder="Agent提取的来源原文；仅在识别不完整时需要修正"
                />
              </details>
            </template>
          </el-table-column>
        </el-table>

        <el-collapse v-if="supplementalFactDrafts.length" class="doc-agent__advanced">
          <el-collapse-item
            :title="`其他已识别信息（${supplementalFactDrafts.length}项，默认一并采用）`"
            name="supplemental-facts"
          >
            <el-table :data="supplementalFactDrafts">
              <el-table-column label="采用" width="65">
                <template #default="{ row }"><el-checkbox v-model="row.selected" /></template>
              </el-table-column>
              <el-table-column label="信息项" min-width="180">
                <template #default="{ row }">
                  <el-input v-if="row.isManual" v-model="row.field" placeholder="补充事实名称" />
                  <span v-else>{{ factFieldDefinition(row.field).label }}</span>
                </template>
              </el-table-column>
              <el-table-column label="内容" min-width="380">
                <template #default="{ row }">
                  <el-input v-model="row.valueText" type="textarea" :rows="2" />
                  <details class="doc-agent__provenance">
                    <summary>来源依据</summary>
                    <el-select v-model="row.sourceDocumentVersionId" style="width: 100%">
                      <el-option
                        v-for="source in selectedTask.sources"
                        :key="source.document_version_id"
                        :label="source.document_title"
                        :value="source.document_version_id"
                      />
                    </el-select>
                    <el-input v-model="row.textQuote" placeholder="来源原文" />
                  </details>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
        <div class="doc-agent__actions">
          <el-button @click="addManualFact">高级：补充其他事实</el-button>
          <el-button type="primary" :loading="actionLoading" @click="confirmFacts">
            确认并开始编制
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
          <el-button
            :disabled="allSectionsLocked"
            :loading="actionLoading"
            @click="lockAllSections"
          >
            一键确认全部无错误章节
          </el-button>
          <el-button
            type="primary"
            :disabled="!allSectionsLocked"
            :loading="actionLoading"
            @click="submitReview"
          >
            提交技术负责人批准
          </el-button>
        </div>
      </template>

      <div v-if="selectedTask.status === 'pending_approval'" class="doc-agent__actions">
        <span>初稿已完成人工复核，等待技术负责人批准。</span>
          <el-button
            v-if="canApprove"
            type="primary"
            :disabled="!isProjectActive"
            :loading="actionLoading"
            @click="approveTask"
          >
            技术负责人批准
          </el-button>
      </div>

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

    <el-dialog v-model="createDialogVisible" title="开始编制四措两案" width="720px">
      <el-form label-position="top">
        <el-form-item label="当前项目的入场前置资料">
          <el-select
            v-model="createForm.sourceVersionIds"
            multiple
            filterable
            style="width: 100%"
            placeholder="选择合同、任务通知、技术要求等入场前置资料"
            :disabled="eligibleDocuments.length === 0"
          >
            <el-option
              v-for="document in eligibleDocuments"
              :key="document.current_version!.id"
              :label="`${document.folder_name} / ${document.title}`"
              :value="document.current_version!.id"
            />
          </el-select>
          <div v-if="eligibleDocuments.length" class="doc-agent__field-help">
            已自动全选 {{ eligibleDocuments.length }} 份合格资料；无需逐份添加，可取消明显无关的文件。
          </div>
          <el-alert
            v-if="eligibleDocuments.length === 0"
            title="该项目暂无入场前置资料，请先到“资料中心 → 入场前置资料”上传。"
            type="warning"
            :closable="false"
            show-icon
          />
        </el-form-item>
        <el-collapse class="doc-agent__advanced">
          <el-collapse-item title="高级设置：Word版式（通常无需修改）" name="layout">
            <el-form-item label="输出版式">
              <el-select v-model="createForm.templateId" style="width: 100%">
                <el-option
                  v-for="template in templates"
                  :key="template.id"
                  :label="template.display_name"
                  :value="template.id"
                >
                  <div class="doc-agent__template-option">
                    <strong>{{ template.display_name }}</strong>
                    <small>{{ templateHint(template) }}</small>
                  </div>
                </el-option>
              </el-select>
              <div class="doc-agent__field-help">
                这里选择的是Word页面和样式基线，不决定四措两案的业务内容。
              </div>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
        <el-alert
          title="Agent会同时使用两层参考：当前项目资料用于确定事实；系统内已批准的条款和RAG案例用于组织专业正文。"
          type="info"
          :closable="false"
        />
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="actionLoading"
          :disabled="eligibleDocuments.length === 0"
          @click="createAndExtract"
        >
          一键开始分析
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

.doc-agent__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.doc-agent__directory-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 2px 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.doc-agent__directory-heading > div {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.doc-agent__directory-heading h3,
.doc-agent__directory-heading p {
  margin: 0;
}

.doc-agent__directory-heading span,
.doc-agent__directory-heading p {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.doc-agent__conversation-directory {
  padding: 18px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-bg-color);
}

.doc-agent__conversation-list {
  display: grid;
  gap: 6px;
  padding-top: 8px;
}

.doc-agent__conversation-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--el-text-color-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: background-color 0.16s ease;
}

.doc-agent__conversation-item:hover,
.doc-agent__conversation-item:focus-visible {
  background: var(--el-fill-color-light);
  outline: none;
}

.doc-agent__conversation-item:disabled {
  cursor: wait;
  opacity: 0.7;
}

.doc-agent__conversation-copy,
.doc-agent__conversation-state {
  display: grid;
  gap: 5px;
}

.doc-agent__conversation-copy {
  min-width: 0;
}

.doc-agent__conversation-copy strong,
.doc-agent__conversation-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-agent__conversation-copy small,
.doc-agent__conversation-state small {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.doc-agent__conversation-state {
  flex: 0 0 auto;
  justify-items: end;
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

.doc-agent__field-help {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.doc-agent__fact-name {
  display: grid;
  align-items: center;
  gap: 4px 8px;
  grid-template-columns: minmax(0, max-content) max-content;
}

.doc-agent__fact-name small {
  overflow: hidden;
  color: var(--el-text-color-secondary);
  grid-column: 1 / -1;
  text-overflow: ellipsis;
}

.doc-agent__risk-evidence {
  margin-top: 8px;
}

.doc-agent__advanced {
  margin-top: 14px;
}

.doc-agent__provenance {
  margin-top: 10px;
}

.doc-agent__provenance summary {
  margin-bottom: 8px;
  color: var(--el-color-primary);
  cursor: pointer;
}

.doc-agent__provenance .el-input {
  margin-top: 8px;
}

.doc-agent__template-option {
  display: grid;
  line-height: 1.35;
}

.doc-agent__template-option small {
  color: var(--el-text-color-secondary);
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

  .doc-agent__directory-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .doc-agent__conversation-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__conversation-state {
    justify-items: start;
  }
}
</style>
