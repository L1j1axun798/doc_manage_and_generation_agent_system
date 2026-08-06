<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'

import { appConfig } from '@/config/app'
import { getErrorMessage } from '@/core/http/error-normalizer'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import { downloadDocument, fetchDocument, fetchDocuments } from '@/modules/documents/api/documents.api'
import type { DocumentItem } from '@/modules/documents/documents.types'
import type { Project } from '@/modules/projects/projects.types'
import { formatDateTime } from '@/shared/utils/format'
import {
  approveGenerationTask,
  confirmAndGenerate,
  deleteGenerationTask,
  exportGenerationTask,
  fetchGenerationEvents,
  fetchGenerationExportInfo,
  fetchGenerationTask,
  fetchGenerationTasks,
  fetchGenerationTemplates,
  generateEntryPlan,
  lockAllGeneratedSections,
  regenerateSection,
  retryGenerationTask,
  setGeneratedSectionLock,
  selectGenerationTemplate,
  startGenerationPipeline,
  stopGenerationTask,
  submitGenerationReview,
  updateGeneratedSection,
} from '../api/document-generation.api'
import {
  BUSINESS_TYPE,
  DOCUMENT_PURPOSE,
  type AgentPersonnelContext,
  type AvailableAgentPersonnel,
  type ConfirmedFactPayload,
  type ConversationSourceAttachment,
  type DocumentGenerationTemplate,
  type FactProposal,
  type GeneratedSection,
  type GenerationExportInfo,
  type GenerationReview,
  type GenerationTask,
  type GenerationTaskStatus,
  type GenerationTraceEvent,
  type SourceLocator,
} from '../document-generation.types'
import { uploadClientTemplate, uploadConversationAttachment } from '../services/client-template.service'
import { fetchAvailableAgentPersonnel } from '../services/personnel.service'
import { useConversationContextStore } from '../stores/conversation-context.store'
import AgentStatusIndicator from './AgentStatusIndicator.vue'
import ChatComposer from './ChatComposer.vue'
import ContextAttachmentBar from './ContextAttachmentBar.vue'
import ConversationSidebar from './ConversationSidebar.vue'
import GenerationWorkflowTrace from './GenerationWorkflowTrace.vue'
import PersonnelSelector from './PersonnelSelector.vue'
import TemplateSelector from './TemplateSelector.vue'
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
  project: Project | null
}>()

const authStore = useAuthStore()
const conversationContextStore = useConversationContextStore()
const loading = ref(false)
const actionLoading = ref(false)
const uploadLoading = ref(false)
const openingTaskId = ref<string | null>(null)
const conversationActionTaskId = ref<string | null>(null)
const refreshingTaskId = ref<string | null>(null)
const templateSelectorVisible = ref(false)
const personnelSelectorVisible = ref(false)
const sourceDialogVisible = ref(false)
const messagesContainer = ref<HTMLElement>()
const followingLatest = ref(true)
const composerCollapsed = ref(false)
const personnelLoading = ref(false)
const personnelError = ref('')
const exportDialogVisible = ref(false)
const exportInfoLoading = ref(false)
const exportInfo = ref<GenerationExportInfo | null>(null)
const exportFilename = ref('')
const templates = ref<DocumentGenerationTemplate[]>([])
const documents = ref<DocumentItem[]>([])
const availablePersonnel = ref<AvailableAgentPersonnel[]>([])
const tasks = ref<GenerationTask[]>([])
const selectedTask = ref<GenerationTask | null>(null)
const workflowEvents = ref<GenerationTraceEvent[]>([])
const factDrafts = ref<FactDraft[]>([])
const sectionDrafts = reactive<Record<string, string>>({})
const revisionDrafts = reactive<Record<string, string>>({})
const selectedRagChunks = reactive<Record<string, string[]>>({})
const selectedRevisionSectionCode = ref('')
let pollTimer: number | undefined
let projectLoadSequence = 0

const sectionNames: Record<string, string> = {
  overview: '工程概况与编制依据',
  organization_measures: '组织措施',
  construction_plan: '施工方案',
  technical_measures: '技术措施',
  safety_measures: '安全措施',
  risk_identification: '风险辨识与预控',
  emergency_plan: '应急预案',
  environmental_measures: '环境保护与文明施工',
}
const revisionQuickCommands = [
  '精简重复表述，突出本章关键动作',
  '补充岗位分工、检查要求和记录留存',
  '强化风险预控措施及责任闭环',
  '调整为正式、清晰的技术方案语言',
  '优先吸收已批准RAG中的专业做法',
]
const MAX_CONVERSATION_SOURCE_COUNT = 5
const currentUsername = computed(
  () => authStore.user?.real_name?.trim() || authStore.user?.username?.trim() || '用户',
)
const welcomeGreeting = computed(
  () => props.project ? `hello,${currentUsername.value},今天从哪里开始？` : '请先选择项目',
)
const showSectionReview = computed(
  () => Boolean(
    selectedTask.value?.sections.length
    && ['review_required', 'queued', 'generating'].includes(selectedTask.value.status),
  ),
)
const eligibleDocuments = computed(() => documents.value.filter(isEligibleEntrySource))
const activeProjectId = computed(() => props.project?.id ?? 0)
const draftContext = computed(() => conversationContextStore.forProject(activeProjectId.value))
const draftTemplate = computed(
  () => templates.value.find((template) => template.id === draftContext.value.templateId) || null,
)
const draftPersonnel = computed<AgentPersonnelContext[]>(() =>
  draftContext.value.personnelIds
    .map((id) => availablePersonnel.value.find((person) => person.folder_id === id))
    .filter((person): person is AvailableAgentPersonnel => Boolean(person)),
)
const activePersonnel = computed<AgentPersonnelContext[]>(() =>
  selectedTask.value?.conversation_context?.personnel || draftPersonnel.value,
)
const activeTemplate = computed(() => selectedTask.value ? selectedTemplate.value : draftTemplate.value)
const activeTemplateName = computed(() => selectedTask.value?.template_name || activeTemplate.value?.display_name || '')
const activeSources = computed<ConversationSourceAttachment[]>(() => {
  if (selectedTask.value) {
    return selectedTask.value.sources.map((source) => ({
      document_version_id: source.document_version_id,
      title: source.document_title,
      filename: source.filename,
    }))
  }
  return draftContext.value.sourceVersionIds
    .map((versionId) => {
      const document = documents.value.find((item) => item.current_version?.id === versionId)
      return {
        document_version_id: versionId,
        title: document?.title || `资料 ${versionId}`,
        filename: document?.current_version?.original_filename || document?.title || `资料 ${versionId}`,
      }
    })
})
const activeSourceCount = computed(
  () => selectedTask.value?.sources.length ?? draftContext.value.sourceVersionIds.length,
)
const composerMessage = computed({
  get: () => {
    if (selectedTask.value?.status === 'review_required' && selectedRevisionSectionCode.value) {
      return revisionDrafts[selectedRevisionSectionCode.value] || ''
    }
    return selectedTask.value ? '' : draftContext.value.message
  },
  set: (value: string) => {
    if (selectedTask.value?.status === 'review_required' && selectedRevisionSectionCode.value) {
      revisionDrafts[selectedRevisionSectionCode.value] = value
      return
    }
    if (!selectedTask.value) draftContext.value.message = value
  },
})
const revisionTargetOptions = computed(() =>
  (selectedTask.value?.sections || [])
    .filter((section) => !section.is_locked)
    .map((section) => ({ value: section.section_code, label: section.title })),
)
const composerDisabled = computed(() => Boolean(
  !props.project || (selectedTask.value && selectedTask.value.status !== 'review_required'),
))
const composerCanSend = computed(() => {
  if (!props.project || actionLoading.value || !composerMessage.value.trim()) return false
  if (selectedTask.value) {
    const target = selectedTask.value.sections.find(
      (section) => section.section_code === selectedRevisionSectionCode.value,
    )
    return selectedTask.value.status === 'review_required'
      && Boolean(target)
      && !target!.is_locked
      && !isSectionRegenerating(target!)
  }
  return Boolean(
    isProjectActive.value
    && draftContext.value.templateId
    && draftContext.value.sourceVersionIds.length,
  )
})
const composerHelperText = computed(() => {
  if (!props.project) return '请先选择项目，选择后将在当前界面加载对应会话和资料'
  if (!selectedTask.value) return 'Enter 发送并开始分析 · Shift + Enter 换行'
  if (selectedTask.value.status === 'review_required') return '选择目标章节后发送修改要求'
  return '当前阶段请完成上方操作，Agent 状态变化后输入区会自动恢复'
})
const sourceSelectionModel = computed({
  get: () => selectedTask.value
    ? selectedTask.value.sources.map((source) => source.document_version_id)
    : draftContext.value.sourceVersionIds,
  set: (value: number[]) => {
    if (selectedTask.value) return
    const uniqueValues = [...new Set(value)]
    if (uniqueValues.length > MAX_CONVERSATION_SOURCE_COUNT) {
      ElMessage.warning(`当前会话最多选择 ${MAX_CONVERSATION_SOURCE_COUNT} 份参考资料`)
    }
    draftContext.value.sourceVersionIds = uniqueValues.slice(0, MAX_CONVERSATION_SOURCE_COUNT)
  },
})
const latestStateSignature = computed(() => {
  const task = selectedTask.value
  if (!task) return ''
  return [
    task.id,
    task.status,
    task.progress,
    task.updated_at,
    workflowEvents.value.length,
    task.sections.length,
    task.reviews.length,
  ].join(':')
})
const criticalFactDrafts = computed(() => factDrafts.value.filter((fact) => fact.isRequired))
const supplementalFactDrafts = computed(() => factDrafts.value.filter((fact) => !fact.isRequired))
const invalidEvidenceFields = computed(
  () => new Set(
    (selectedTask.value?.fact_conflicts || [])
      .filter((conflict) => conflict.reason === 'evidence_invalid')
      .map((conflict) => typeof conflict.field === 'string' ? conflict.field : ''),
  ),
)
const recoveryGuidance = computed(() => {
  const task = selectedTask.value
  if (!task?.error_code) {
    return ''
  }
  if (task.error_code === 'FACT_EVIDENCE_INVALID') {
    return task.status === 'needs_confirmation'
      ? '处理方式：重新核对标记事实的来源资料和来源原文，然后点击“确认并开始编制”。'
      : '处理方式：点击“自动修复来源并重试”；无法自动修复时，系统会返回事实核对页面。'
  }
  if (task.error_code === 'VALIDATION_FAILED') {
    const sectionCode = task.pending_section_codes[0]
    const sectionHint = sectionCode ? `（${sectionNames[sectionCode] || sectionCode}）` : ''
    return `处理方式：系统已保留通过校验的章节。点击“从失败章节继续”后，将从未通过章节${sectionHint}及后续未完成章节继续生成。`
  }
  if (task.status === 'failed') {
    return '处理方式：确认资料文件、Redis队列和模型服务可用后点击“重试当前步骤”，系统会从可恢复节点继续。'
  }
  return ''
})
const isProjectActive = computed(() => props.project?.status === 'active')
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
const exportFilenameError = computed(() => {
  const filename = normalizedExportFilenameStem()
  if (!filename) {
    return '请输入导出文件名'
  }
  if (filename.length > 250) {
    return '文件名不能超过250个字符'
  }
  if (/[\\/:*?"<>|]/.test(filename) || filename.endsWith('.')) {
    return '文件名不能包含 \\ / : * ? " < > |，也不能以句点结尾'
  }
  return ''
})

function normalizedExportFilenameStem(): string {
  return exportFilename.value.trim().replace(/\.docx$/i, '').trim()
}

function normalizeExportFilenameInput(): void {
  exportFilename.value = normalizedExportFilenameStem()
}

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
  cancelled: '已停止',
}

onBeforeUnmount(stopPolling)
watch(
  () => props.project?.id ?? null,
  () => {
    void loadInitialData()
  },
  { immediate: true },
)
watch(
  () => [selectedTask.value?.id || null, selectedTask.value?.status || null] as const,
  ([taskId, status], [previousTaskId, previousStatus]) => {
    if (!taskId) {
      composerCollapsed.value = false
      return
    }
    if (taskId !== previousTaskId) {
      composerCollapsed.value = status === 'review_required'
      return
    }
    if (status === 'review_required' && previousStatus !== 'review_required') {
      composerCollapsed.value = true
    }
  },
)
watch(
  () => selectedTask.value?.id,
  () => {
    followingLatest.value = true
    scrollMessagesToLatest(true)
  },
  { flush: 'post' },
)
watch(latestStateSignature, () => scrollMessagesToLatest(), { flush: 'post' })

function handleMessagesScroll(): void {
  const container = messagesContainer.value
  if (!container) return
  const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
  followingLatest.value = distanceFromBottom <= 80
}

function scrollMessagesToLatest(force = false): void {
  if (!force && !followingLatest.value) return
  void nextTick(() => {
    const container = messagesContainer.value
    if (!container) return
    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top: container.scrollHeight, behavior: force ? 'auto' : 'smooth' })
    } else {
      container.scrollTop = container.scrollHeight
    }
    followingLatest.value = true
  })
}

async function loadInitialData(): Promise<void> {
  const loadSequence = ++projectLoadSequence
  const projectId = props.project?.id ?? null
  stopPolling()
  selectedTask.value = null
  workflowEvents.value = []
  factDrafts.value = []
  documents.value = []
  tasks.value = []
  availablePersonnel.value = []
  composerCollapsed.value = false
  loading.value = true
  try {
    const [templateRows, documentRows, taskRows] = await Promise.all([
      fetchGenerationTemplates(projectId || undefined),
      projectId ? fetchAllProjectDocuments(projectId) : Promise.resolve([]),
      projectId ? fetchAllGenerationTasks(projectId) : Promise.resolve([]),
    ])
    if (loadSequence !== projectLoadSequence) return
    templates.value = templateRows
    documents.value = documentRows
    tasks.value = taskRows
    if (projectId && !draftContext.value.sourceVersionIds.length) {
      draftContext.value.sourceVersionIds = eligibleDocuments.value
        .map((document) => document.current_version?.id)
        .filter((id): id is number => typeof id === 'number')
        .slice(0, MAX_CONVERSATION_SOURCE_COUNT)
    } else if (draftContext.value.sourceVersionIds.length > MAX_CONVERSATION_SOURCE_COUNT) {
      draftContext.value.sourceVersionIds = draftContext.value.sourceVersionIds
        .slice(0, MAX_CONVERSATION_SOURCE_COUNT)
    }
    if (projectId) await loadAvailablePersonnel(projectId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    if (loadSequence === projectLoadSequence) loading.value = false
  }
}

async function fetchAllGenerationTasks(projectId: number): Promise<GenerationTask[]> {
  const rows: GenerationTask[] = []
  let page = 1
  while (page <= 50) {
    const response = await fetchGenerationTasks(projectId, page)
    rows.push(...response.results)
    if (!response.next || rows.length >= response.count) {
      break
    }
    page += 1
  }
  return rows
}

async function fetchAllProjectDocuments(projectId: number): Promise<DocumentItem[]> {
  const rows: DocumentItem[] = []
  let page = 1
  while (page <= 50) {
    const response = await fetchDocuments({
      project: projectId,
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
  const projectId = props.project?.id
  tasks.value = projectId ? await fetchAllGenerationTasks(projectId) : []
}

async function loadAvailablePersonnel(projectId = props.project?.id): Promise<void> {
  if (!projectId) {
    availablePersonnel.value = []
    personnelError.value = ''
    return
  }
  personnelLoading.value = true
  personnelError.value = ''
  try {
    const personnel = await fetchAvailableAgentPersonnel(projectId)
    if (props.project?.id === projectId) availablePersonnel.value = personnel
  } catch (error) {
    availablePersonnel.value = []
    personnelError.value = getErrorMessage(error)
  } finally {
    personnelLoading.value = false
  }
}

async function openConversation(task: GenerationTask): Promise<void> {
  openingTaskId.value = task.id
  try {
    selectedTask.value = await fetchGenerationTask(task.id)
    workflowEvents.value = await fetchGenerationEvents(task.id)
    hydrateTaskDrafts()
    selectDefaultRevisionTarget()
    configurePolling()
  } catch (error) {
    selectedTask.value = null
    workflowEvents.value = []
    ElMessage.error(getErrorMessage(error))
  } finally {
    openingTaskId.value = null
  }
}

function startNewConversation(): void {
  if (!props.project) {
    ElMessage.warning('请先选择项目')
    return
  }
  stopPolling()
  selectedTask.value = null
  workflowEvents.value = []
  factDrafts.value = []
  selectedRevisionSectionCode.value = ''
  composerCollapsed.value = false
  const draft = conversationContextStore.reset(props.project.id)
  draft.sourceVersionIds = eligibleDocuments.value
    .map((document) => document.current_version?.id)
    .filter((id): id is number => typeof id === 'number')
    .slice(0, MAX_CONVERSATION_SOURCE_COUNT)
}

function conversationTitle(task: GenerationTask): string {
  return `四措两案编制 · ${formatDateTime(task.created_at)}`
}

function agentStatusMessage(task: GenerationTask): string {
  if (task.status === 'needs_confirmation') return '资料分析已完成，请核对下方关键事实后继续。'
  if (task.status === 'review_required') return '初稿已生成，请逐章复核；需要修改时在底部选择章节并发送要求。'
  if (task.status === 'pending_approval') return '人工复核已完成，正在等待技术负责人批准。'
  if (task.status === 'approved') return '文档已批准，可以导出到当前项目“技术方案”目录。'
  if (task.status === 'exported') return '正式 Word 已归档，可直接下载。'
  if (task.status === 'failed') return '本次处理未完成，请查看错误和恢复建议后重试。'
  if (task.status === 'cancelled') return '本会话已停止，已产生的中间内容仍保留。'
  return 'Agent 正在分析资料并执行当前编制步骤，完成后会自动更新。'
}

async function refreshConversation(task: GenerationTask): Promise<void> {
  refreshingTaskId.value = task.id
  try {
    if (selectedTask.value?.id === task.id) {
      await refreshSelectedTask()
    } else {
      const refreshedTask = await fetchGenerationTask(task.id)
      tasks.value = tasks.value.map((item) => item.id === task.id ? refreshedTask : item)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    refreshingTaskId.value = null
  }
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
  tasks.value = tasks.value.map((item) => item.id === task.id ? task : item)
  workflowEvents.value.push(...newEvents)
  if (
    selectedTask.value.status !== previousStatus
    || selectedTask.value.status === 'review_required'
  ) {
    hydrateTaskDrafts()
    selectDefaultRevisionTarget()
  }
  configurePolling()
}

function selectDefaultRevisionTarget(): void {
  const options = revisionTargetOptions.value
  if (!options.some((option) => option.value === selectedRevisionSectionCode.value)) {
    selectedRevisionSectionCode.value = options[0]?.value || ''
  }
}

function hydrateTaskDrafts(): void {
  const task = selectedTask.value
  if (!task) {
    return
  }
  if (task.status === 'needs_confirmation') {
    const snapshots = task.facts_snapshot as Array<FactProposal | ConfirmedFactPayload>
    const proposalFields = new Set(
      snapshots.map((proposal) => proposal.field),
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
    const proposals: Array<FactProposal | ConfirmedFactPayload> = [
      ...snapshots,
      ...conflictDefaults,
    ]
    const requiredFields = selectedTemplate.value?.required_fact_fields || []
    const requiredSet = new Set(requiredFields)
    const drafts = proposals.map((proposal) => {
      const evidence = 'source_document_version_id' in proposal
        ? {
            source_document_version_id: proposal.source_document_version_id,
            locator: proposal.locator,
            confidence: proposal.confidence,
          }
        : proposal.evidence?.[0]
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

function openTemplateSelector(): void {
  if (!selectedTask.value && requireSelectedProject()) templateSelectorVisible.value = true
}

function openPersonnelSelector(): void {
  if (!selectedTask.value && requireSelectedProject()) personnelSelectorVisible.value = true
}

function openSourceDialog(): void {
  if (!selectedTask.value && !requireSelectedProject()) return
  sourceDialogVisible.value = true
}

function requireSelectedProject(): Project | null {
  if (!props.project) {
    ElMessage.warning('请先选择项目')
    return null
  }
  return props.project
}

async function selectDraftTemplate(templateId: number | null): Promise<void> {
  if (!templateId) {
    draftContext.value.templateId = null
    return
  }
  const project = requireSelectedProject()
  if (!project) return
  try {
    const selected = await selectGenerationTemplate(templateId, project.id)
    draftContext.value.templateId = selected.id
    if (selected.sync_status === 'synced') {
      documents.value = await fetchAllProjectDocuments(project.id)
      ElMessage.success('甲方模板已选择并同步到“入场前置资料”')
    } else if (selected.sync_status === 'folder_missing') {
      ElMessage.success('甲方模板已选择；当前项目无“入场前置资料”目录，未执行同步')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function selectDraftPersonnel(personnelIds: number[]): void {
  draftContext.value.personnelIds = personnelIds
}

function removeDraftPersonnel(personnelId: string): void {
  const numericId = Number(personnelId)
  draftContext.value.personnelIds = draftContext.value.personnelIds.filter(
    (id) => id !== numericId,
  )
}

function removeDraftSource(versionId: number): void {
  draftContext.value.sourceVersionIds = draftContext.value.sourceVersionIds
    .filter((sourceVersionId) => sourceVersionId !== versionId)
}

async function handleTemplateUpload(file: File): Promise<void> {
  const project = requireSelectedProject()
  if (!project) return
  uploadLoading.value = true
  try {
    const template = await uploadClientTemplate(project.id, file)
    templates.value = [
      template,
      ...templates.value.filter((item) => item.id !== template.id),
    ]
    draftContext.value.templateId = template.id
    templateSelectorVisible.value = false
    documents.value = await fetchAllProjectDocuments(project.id)
    if (template.sync_status === 'synced') {
      ElMessage.success('甲方模板已选择并同步到“入场前置资料”，可直接用于生成')
    } else {
      ElMessage.success('甲方模板已选择，可直接用于生成；当前项目无“入场前置资料”目录，未执行同步')
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    uploadLoading.value = false
  }
}

async function handleAttachmentUpload(files: File[]): Promise<void> {
  const project = requireSelectedProject()
  if (!project) return
  const remainingCount = MAX_CONVERSATION_SOURCE_COUNT - draftContext.value.sourceVersionIds.length
  if (remainingCount <= 0) {
    ElMessage.warning(`当前会话最多添加 ${MAX_CONVERSATION_SOURCE_COUNT} 份资料`)
    return
  }
  if (files.length > remainingCount) {
    ElMessage.warning(`当前会话还可上传 ${remainingCount} 份资料，请重新选择`)
    return
  }
  uploadLoading.value = true
  let uploadedCount = 0
  const uploadErrors: string[] = []
  try {
    for (const file of files) {
      try {
        const document = await uploadConversationAttachment(project.id, file)
        documents.value = [document, ...documents.value.filter((item) => item.id !== document.id)]
        const versionId = document.current_version?.id
        if (versionId && !draftContext.value.sourceVersionIds.includes(versionId)) {
          draftContext.value.sourceVersionIds.push(versionId)
          uploadedCount += 1
        }
      } catch (error) {
        uploadErrors.push(`${file.name}：${getErrorMessage(error)}`)
      }
    }
    if (uploadedCount) {
      ElMessage.success(`已上传并加入当前会话 ${uploadedCount} 份资料`)
    }
    if (uploadErrors.length) {
      ElMessage.error(`有 ${uploadErrors.length} 份资料上传失败：${uploadErrors[0]}`)
    }
  } finally {
    uploadLoading.value = false
  }
}

async function sendComposerMessage(): Promise<void> {
  if (selectedTask.value) {
    const section = selectedTask.value.sections.find(
      (item) => item.section_code === selectedRevisionSectionCode.value,
    )
    if (!section) {
      ElMessage.warning('请选择需要修改的章节')
      return
    }
    await regenerate(section)
    return
  }
  await createAndExtract()
}

async function createAndExtract(): Promise<void> {
  const project = requireSelectedProject()
  if (!project) return
  if (!draftContext.value.templateId || draftContext.value.sourceVersionIds.length === 0) {
    ElMessage.warning('请选择模板和至少一份当前项目的入场前置资料')
    return
  }
  if (draftContext.value.sourceVersionIds.length > MAX_CONVERSATION_SOURCE_COUNT) {
    ElMessage.warning(`当前会话最多添加 ${MAX_CONVERSATION_SOURCE_COUNT} 份资料`)
    return
  }
  const initialMessage = draftContext.value.message.trim()
  if (!initialMessage) {
    ElMessage.warning('请输入本次四措两案的编制要求')
    return
  }
  actionLoading.value = true
  try {
    const task = await startGenerationPipeline({
      project_id: project.id,
      template_id: draftContext.value.templateId,
      document_version_ids: [...draftContext.value.sourceVersionIds],
      document_purpose: DOCUMENT_PURPOSE,
      business_type: BUSINESS_TYPE,
      idempotency_key: window.crypto.randomUUID(),
      conversation_context: {
        initial_message: initialMessage,
        selected_personnel_ids: [...draftContext.value.personnelIds],
      },
      facts: [
        { field: 'project_name', value: project.name, value_type: 'string' },
        { field: 'project_code', value: project.code, value_type: 'string' },
      ],
    })
    selectedTask.value = task
    workflowEvents.value = await fetchGenerationEvents(task.id)
    await refreshTasks()
    configurePolling()
    ElMessage.success('消息已发送，Agent 正在分析当前会话资料')
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

async function stopConversation(task: GenerationTask): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '停止后，本次会话不会继续生成或进入审核；已经生成的中间章节会保留。',
      '停止当前会话',
      {
        confirmButtonText: '确认停止',
        cancelButtonText: '继续执行',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  conversationActionTaskId.value = task.id
  try {
    const stoppedTask = await stopGenerationTask(task.id)
    tasks.value = tasks.value.map((item) => item.id === task.id ? stoppedTask : item)
    if (selectedTask.value?.id === task.id) {
      selectedTask.value = stoppedTask
      const newEvents = await fetchGenerationEvents(
        task.id,
        workflowEvents.value.at(-1)?.sequence || 0,
      )
      workflowEvents.value.push(...newEvents)
      stopPolling()
    }
    ElMessage.success('会话已停止')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    conversationActionTaskId.value = null
  }
}

async function deleteConversation(task: GenerationTask): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '删除后，该会话将从历史列表中移除；已经正式导出的项目文档不会被删除。',
      '删除历史会话',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  conversationActionTaskId.value = task.id
  try {
    await deleteGenerationTask(task.id)
    tasks.value = tasks.value.filter((item) => item.id !== task.id)
    if (selectedTask.value?.id === task.id) {
      stopPolling()
      selectedTask.value = null
      workflowEvents.value = []
      factDrafts.value = []
    }
    ElMessage.success('历史会话已删除')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    conversationActionTaskId.value = null
  }
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
  const instruction = (revisionDrafts[section.section_code] || '').trim()
  if (!instruction) {
    ElMessage.warning('请先输入本章的修改要求')
    return
  }
  await runAction(async () => {
    selectedTask.value = await regenerateSection(
      selectedTask.value!.id,
      section.section_code,
      instruction,
      selectedRagChunks[section.section_code] || [],
    )
    revisionDrafts[section.section_code] = ''
    selectedRagChunks[section.section_code] = []
    configurePolling()
    ElMessage.success('修改要求已发送，正在重新生成本章')
  })
}

function sectionRevisionTurns(sectionCode: string): GenerationReview[] {
  return (selectedTask.value?.reviews || []).filter(
    (review) =>
      review.action === 'section_regenerated'
      && review.section_code === sectionCode
      && review.comment.trim(),
  )
}

function reviewMetadataText(review: GenerationReview, key: string): string {
  const value = review.metadata[key]
  return typeof value === 'string' ? value : ''
}

function revisionStatus(review: GenerationReview): string {
  return reviewMetadataText(review, 'conversation_status') || 'completed'
}

function appendRevisionCommand(sectionCode: string, command: string): void {
  selectedRevisionSectionCode.value = sectionCode
  const current = (revisionDrafts[sectionCode] || '').trim()
  revisionDrafts[sectionCode] = current ? `${current}\n${command}` : command
}

function citationChunkId(citation: Record<string, unknown>): string {
  return typeof citation.chunk_id === 'string' ? citation.chunk_id : ''
}

function citationLabel(citation: Record<string, unknown>): string {
  const heading = Array.isArray(citation.locator)
    ? ''
    : (
        citation.locator
        && typeof citation.locator === 'object'
        && Array.isArray((citation.locator as Record<string, unknown>).heading_path)
      )
      ? ((citation.locator as Record<string, unknown>).heading_path as unknown[])
          .filter((value): value is string => typeof value === 'string')
          .join(' / ')
      : ''
  return heading || citationChunkId(citation).slice(0, 12) || 'RAG参考'
}

function isRagChunkSelected(sectionCode: string, chunkId: string): boolean {
  return (selectedRagChunks[sectionCode] || []).includes(chunkId)
}

function toggleRagChunk(sectionCode: string, chunkId: string): void {
  if (!chunkId) {
    return
  }
  const selected = selectedRagChunks[sectionCode] || []
  selectedRagChunks[sectionCode] = selected.includes(chunkId)
    ? selected.filter((value) => value !== chunkId)
    : [...selected, chunkId]
}

function isSectionRegenerating(section: GeneratedSection): boolean {
  const task = selectedTask.value
  return Boolean(
    task
    && ['queued', 'generating'].includes(task.status)
    && task.pending_section_codes.includes(section.section_code),
  )
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

async function openExportDialog(): Promise<void> {
  if (!selectedTask.value) {
    return
  }
  exportDialogVisible.value = true
  exportInfoLoading.value = true
  exportInfo.value = null
  exportFilename.value = ''
  try {
    exportInfo.value = await fetchGenerationExportInfo(selectedTask.value.id)
    exportFilename.value = exportInfo.value.default_filename.replace(/\.docx$/i, '')
  } catch (error) {
    exportDialogVisible.value = false
    ElMessage.error(getErrorMessage(error))
  } finally {
    exportInfoLoading.value = false
  }
}

async function exportTask(): Promise<void> {
  if (!selectedTask.value || exportFilenameError.value) {
    ElMessage.warning(exportFilenameError.value || '请检查导出文件名')
    return
  }
  actionLoading.value = true
  try {
    selectedTask.value = await exportGenerationTask(
      selectedTask.value.id,
      window.crypto.randomUUID(),
      `${normalizedExportFilenameStem()}.docx`,
    )
    exportDialogVisible.value = false
    await refreshTasks()
    configurePolling()
    ElMessage.success('已导出到当前项目的“技术方案”目录')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    actionLoading.value = false
  }
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
    <div class="doc-agent__workbench">
      <ConversationSidebar
        :tasks="tasks"
        :username="currentUsername"
        :active-task-id="selectedTask?.id || null"
        :opening-task-id="openingTaskId"
        :action-task-id="conversationActionTaskId"
        :refreshing-task-id="refreshingTaskId"
        :loading="loading"
        :project-selected="Boolean(project)"
        :status-labels="statusLabels"
        @new="startNewConversation"
        @open="openConversation"
        @refresh="refreshConversation"
        @stop="stopConversation"
        @delete="deleteConversation"
      />

      <main class="doc-agent__conversation">
        <header class="doc-agent__conversation-header">
          <div class="doc-agent__project-context"><slot name="project-context" /></div>
          <div class="doc-agent__toolbar-actions">
            <slot name="page-actions" />
          </div>
        </header>

        <div
          ref="messagesContainer"
          class="doc-agent__messages"
          aria-live="polite"
          @scroll.passive="handleMessagesScroll"
        >
          <section v-if="!selectedTask" class="doc-agent__welcome">
            <span class="doc-agent__welcome-logo" aria-hidden="true">
              <img :src="appConfig.logoUrl" alt="" />
            </span>
            <h2 :key="welcomeGreeting" :aria-label="welcomeGreeting" class="doc-agent__welcome-greeting">
              <span
                v-for="(character, index) in Array.from(welcomeGreeting)"
                :key="`${index}-${character}`"
                class="doc-agent__welcome-character"
                :style="{ animationDelay: `${index * 45}ms` }"
                aria-hidden="true"
              >{{ character }}</span>
              <span class="doc-agent__welcome-cursor" aria-hidden="true" />
            </h2>
            <p v-if="project">自主选择或上传甲方模板，并选择入场人员和来源资料，然后发送编制要求。系统会在同一会话内完成事实核对、生成、修改、批准和导出。</p>
            <p v-else>请在上方项目选择框中选择一个在执行项目。选择后，会话记录、模板、人员和资料将在当前界面直接加载。</p>
          </section>

          <template v-else>
            <div class="doc-agent__message-turn doc-agent__message-turn--user">
              <div class="doc-agent__avatar">我</div>
              <div>
                <p>{{ selectedTask.conversation_context?.initial_message || '请基于所选资料开始四措两案编制。' }}</p>
                <small>{{ selectedTask.created_by_name }} · {{ formatDateTime(selectedTask.created_at) }}</small>
              </div>
            </div>
            <div class="doc-agent__message-turn doc-agent__message-turn--agent">
              <div class="doc-agent__avatar">AI</div>
              <div class="doc-agent__ai-response">
                <div class="doc-agent__ai-summary">
                  <AgentStatusIndicator
                    :status="selectedTask.status"
                    :progress="selectedTask.progress"
                    :label="statusLabels[selectedTask.status]"
                  />
                  <p>{{ agentStatusMessage(selectedTask) }}</p>
                </div>

    <el-card class="doc-agent__task" shadow="never">
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
      <el-alert
        v-if="recoveryGuidance"
        class="doc-agent__recovery"
        :title="recoveryGuidance"
        type="info"
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
          :title="
            invalidEvidenceFields.size
              ? '部分事实的来源定位无法自动恢复，请重点核对标记项目。'
              : '不同资料存在同名事实冲突。系统已预填置信度较高的候选值，请重点核对下列项目。'
          "
          type="warning"
          :closable="false"
        />
        <el-table :data="criticalFactDrafts" row-key="field">
          <el-table-column label="关键项目事实" min-width="180">
            <template #default="{ row }">
              <div class="doc-agent__fact-name">
                <span>{{ factFieldDefinition(row.field).label }}</span>
                <el-tag size="small" type="danger">
                  {{ invalidEvidenceFields.has(row.field) ? '来源需核对' : '需确认' }}
                </el-tag>
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
                  <span v-else>
                    {{ factFieldDefinition(row.field).label }}
                    <el-tag
                      v-if="invalidEvidenceFields.has(row.field)"
                      size="small"
                      type="danger"
                    >
                      来源需核对
                    </el-tag>
                  </span>
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
          {{
            selectedTask.error_code === 'FACT_EVIDENCE_INVALID'
              ? '自动修复来源并重试'
              : selectedTask.error_code === 'VALIDATION_FAILED'
                ? '从失败章节继续'
                : '重试当前步骤'
          }}
        </el-button>
      </div>

      <template v-if="showSectionReview">
        <div class="doc-agent__review-heading">
          <div>
            <h3>逐章人工审核</h3>
            <p>可直接编辑正文，也可用对话告诉 Agent 如何修改本章。</p>
          </div>
          <el-tag
            v-if="selectedTask.status !== 'review_required'"
            type="primary"
            effect="light"
          >
            Agent 正在处理修改
          </el-tag>
        </div>
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
            <div class="doc-agent__section-workspace">
              <div class="doc-agent__section-editor">
                <div class="doc-agent__panel-label">
                  <strong>章节正文</strong>
                  <span>修订 {{ section.revision }}</span>
                </div>
                <el-input
                  v-model="sectionDrafts[section.section_code]"
                  type="textarea"
                  :rows="16"
                  :disabled="section.is_locked || isSectionRegenerating(section)"
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
                  <summary>查看完整来源引用（{{ section.citations.length }}）</summary>
                  <pre>{{ JSON.stringify(section.citations, null, 2) }}</pre>
                </details>
                <div class="doc-agent__actions">
                  <el-button
                    :disabled="
                      section.is_locked
                      || selectedTask.status !== 'review_required'
                    "
                    :loading="actionLoading"
                    @click="saveSection(section)"
                  >
                    保存手工修改
                  </el-button>
                  <el-button
                    :disabled="selectedTask.status !== 'review_required'"
                    :loading="actionLoading"
                    @click="toggleSectionLock(section)"
                  >
                    {{ section.is_locked ? '解锁' : '确认并锁定' }}
                  </el-button>
                </div>
              </div>

              <aside class="doc-agent__revision-chat">
                <div class="doc-agent__chat-header">
                  <div>
                    <strong>与 Agent 修改本章</strong>
                    <span>修改要求会进入生成 Prompt 并保留记录</span>
                  </div>
                  <span class="doc-agent__agent-dot" aria-hidden="true" />
                </div>

                <div class="doc-agent__chat-history" aria-live="polite">
                  <div
                    v-if="sectionRevisionTurns(section.section_code).length === 0"
                    class="doc-agent__chat-empty"
                  >
                    <strong>描述你想怎样调整</strong>
                    <span>例如补充信息、强化某项措施，或指定优先参考的RAG片段。</span>
                  </div>
                  <template
                    v-for="turn in sectionRevisionTurns(section.section_code)"
                    :key="turn.id"
                  >
                    <div class="doc-agent__message doc-agent__message--user">
                      <div>{{ turn.comment }}</div>
                      <small>{{ turn.actor_name }} · {{ formatDateTime(turn.created_at) }}</small>
                    </div>
                    <div class="doc-agent__message doc-agent__message--agent">
                      <div>
                        {{
                          reviewMetadataText(turn, 'assistant_message')
                          || '已完成本轮章节修订，请核对正文。'
                        }}
                      </div>
                      <small
                        :class="`doc-agent__message-status--${revisionStatus(turn)}`"
                      >
                        {{
                          revisionStatus(turn) === 'completed'
                            ? '已完成'
                            : revisionStatus(turn) === 'failed'
                              ? '未完成'
                              : '处理中'
                        }}
                      </small>
                    </div>
                  </template>
                </div>

                <div class="doc-agent__quick-commands">
                  <span>常用调整</span>
                  <div>
                    <button
                      v-for="command in revisionQuickCommands"
                      :key="command"
                      type="button"
                      :disabled="section.is_locked || isSectionRegenerating(section)"
                      @click="appendRevisionCommand(section.section_code, command)"
                    >
                      {{ command }}
                    </button>
                  </div>
                </div>

                <div v-if="section.citations.some(citationChunkId)" class="doc-agent__rag-focus">
                  <div class="doc-agent__rag-focus-heading">
                    <span>特别参照的RAG信息</span>
                    <small>可多选本章已批准引用</small>
                  </div>
                  <div class="doc-agent__rag-chips">
                    <button
                      v-for="citation in section.citations.filter(citationChunkId)"
                      :key="citationChunkId(citation)"
                      type="button"
                      :class="{
                        'is-selected': isRagChunkSelected(
                          section.section_code,
                          citationChunkId(citation),
                        ),
                      }"
                      :disabled="section.is_locked || isSectionRegenerating(section)"
                      @click="toggleRagChunk(section.section_code, citationChunkId(citation))"
                    >
                      {{ citationLabel(citation) }}
                    </button>
                  </div>
                </div>

                <button
                  class="doc-agent__use-bottom-composer"
                  type="button"
                  :disabled="section.is_locked || isSectionRegenerating(section)"
                  @click="selectedRevisionSectionCode = section.section_code"
                >
                  在底部输入框中修改“{{ section.title }}”
                </button>
              </aside>
            </div>
          </el-collapse-item>
        </el-collapse>
        <div v-if="selectedTask.status === 'review_required'" class="doc-agent__actions">
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
          @click="openExportDialog"
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
              </div>
            </div>
          </template>
        </div>

        <footer class="doc-agent__composer-shell">
          <div v-if="selectedTask && !followingLatest" class="doc-agent__latest-action">
            <el-button
              class="doc-agent__latest-button"
              type="primary"
              plain
              round
              @click="scrollMessagesToLatest(true)"
            >
              ↓ 回到最新状态
            </el-button>
          </div>
          <ChatComposer
            v-model="composerMessage"
            v-model:collapsed="composerCollapsed"
            :loading="actionLoading"
            :upload-loading="uploadLoading"
            :disabled="composerDisabled"
            :can-send="composerCanSend"
            :helper-text="composerHelperText"
            :editable-context="Boolean(project) && !selectedTask"
            :source-count="draftContext.sourceVersionIds.length"
            :max-source-count="MAX_CONVERSATION_SOURCE_COUNT"
            :placeholder="
              !project
                ? '请先选择项目'
                : selectedTask?.status === 'review_required'
                ? '输入对目标章节的修改要求…'
                : selectedTask
                  ? '当前阶段暂不接收新消息'
                  : '描述本次编制重点、甲方要求或需要特别关注的事项…'
            "
            @send="sendComposerMessage"
            @template="openTemplateSelector"
            @personnel="openPersonnelSelector"
            @sources="openSourceDialog"
            @upload="handleAttachmentUpload"
          >
            <template #attachments>
              <ContextAttachmentBar
                :template="activeTemplate"
                :template-name="activeTemplateName"
                :personnel="activePersonnel"
                :sources="activeSources"
                :source-count="activeSourceCount"
                :max-source-count="MAX_CONVERSATION_SOURCE_COUNT"
                :editable="!selectedTask"
                @template="openTemplateSelector"
                @personnel="openPersonnelSelector"
                @sources="openSourceDialog"
                @remove-template="draftContext.templateId = null"
                @remove-personnel="removeDraftPersonnel"
                @remove-source="removeDraftSource"
              />
            </template>
            <template v-if="selectedTask?.status === 'review_required'" #context-extra>
              <div class="doc-agent__revision-target">
                <span>本条消息将修改</span>
                <el-select
                  v-model="selectedRevisionSectionCode"
                  placeholder="选择目标章节"
                  style="width: min(360px, 100%)"
                >
                  <el-option
                    v-for="option in revisionTargetOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </div>
            </template>
          </ChatComposer>
        </footer>
      </main>
    </div>

    <el-dialog
      v-model="exportDialogVisible"
      title="导出已批准 Word"
      width="560px"
      :close-on-click-modal="false"
    >
      <div v-loading="exportInfoLoading" class="doc-agent__export-dialog">
        <el-alert
          v-if="exportInfo"
          :title="
            exportInfo.agent_generated_count
              ? `“${exportInfo.target_folder}”目录已有 ${exportInfo.agent_generated_count} 份 Agent 生成文件`
              : `“${exportInfo.target_folder}”目录暂无 Agent 生成文件`
          "
          :type="exportInfo.agent_generated_count ? 'warning' : 'success'"
          :closable="false"
          show-icon
        >
          <template #default>
            新文件不会覆盖已有文件；如提示同名，请在下方修改名称后重新导出。
          </template>
        </el-alert>
        <el-form v-if="exportInfo" label-position="top">
          <el-form-item label="导出文件名" :error="exportFilenameError">
            <el-input
              v-model="exportFilename"
              maxlength="250"
              show-word-limit
              clearable
              autocomplete="off"
              placeholder="请输入文件名"
              @blur="normalizeExportFilenameInput"
              @keyup.enter="exportTask"
            >
              <template #append>.docx</template>
            </el-input>
            <div class="doc-agent__field-help">
              保存位置：当前项目 / {{ exportInfo.target_folder }}
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button :disabled="actionLoading" @click="exportDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="actionLoading"
          :disabled="exportInfoLoading || !exportInfo || Boolean(exportFilenameError)"
          @click="exportTask"
        >
          确认导出
        </el-button>
      </template>
    </el-dialog>

    <TemplateSelector
      v-model="templateSelectorVisible"
      :templates="templates"
      :selected-id="draftContext.templateId"
      :uploading="uploadLoading"
      @select="selectDraftTemplate"
      @upload="handleTemplateUpload"
    />

    <PersonnelSelector
      v-model="personnelSelectorVisible"
      :personnel="availablePersonnel"
      :selected-ids="draftContext.personnelIds"
      :loading="personnelLoading"
      :error="personnelError"
      @confirm="selectDraftPersonnel"
      @retry="loadAvailablePersonnel"
    />

    <el-dialog
      v-model="sourceDialogVisible"
      :title="selectedTask ? '本会话来源资料' : '选择系统内参考资料'"
      width="min(760px, 94vw)"
    >
      <el-alert
        :title="`只显示当前项目中你有权读取的“入场前置资料”；最多选择 ${MAX_CONVERSATION_SOURCE_COUNT} 份，检测报告、完工资料和报告模板不会进入 Agent。`"
        type="info"
        :closable="false"
        show-icon
      />
      <el-checkbox-group v-model="sourceSelectionModel" class="doc-agent__source-list">
        <el-checkbox
          v-for="document in eligibleDocuments"
          :key="document.current_version!.id"
          :value="document.current_version!.id"
          :disabled="Boolean(selectedTask) || (
            sourceSelectionModel.length >= MAX_CONVERSATION_SOURCE_COUNT
            && !sourceSelectionModel.includes(document.current_version!.id)
          )"
          class="doc-agent__source-item"
        >
          <span>
            <strong>{{ document.title }}</strong>
            <small>{{ document.current_version!.original_filename }}</small>
          </span>
        </el-checkbox>
      </el-checkbox-group>
      <el-empty
        v-if="!eligibleDocuments.length"
        :image-size="72"
        description="当前项目暂无可用入场前置资料"
      />
      <template #footer>
        <span class="doc-agent__source-count">
          已选择 {{ sourceSelectionModel.length }}/{{ MAX_CONVERSATION_SOURCE_COUNT }} 份
        </span>
        <el-button type="primary" @click="sourceDialogVisible = false">完成</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.doc-agent {
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.doc-agent__workbench {
  display: grid;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-bg-surface);
  box-shadow: var(--shadow-1);
  grid-template-columns: 240px minmax(0, 1fr);
}

.doc-agent__conversation {
  display: flex;
  position: relative;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
}

.doc-agent__conversation-header {
  display: flex;
  align-items: center;
  min-height: 66px;
  padding: 10px 22px;
  border-bottom: 1px solid var(--color-border-light);
  justify-content: space-between;
  gap: 14px;
}

.doc-agent__project-context {
  min-width: 0;
  flex: 1;
}

.doc-agent__messages {
  min-height: 0;
  overflow-y: auto;
  padding: 28px clamp(18px, 4vw, 58px) 36px;
  flex: 1;
  scrollbar-width: thin;
}

.doc-agent__welcome {
  display: grid;
  max-width: 760px;
  min-height: 100%;
  margin: 0 auto;
  place-content: center;
  text-align: center;
}

.doc-agent__welcome-logo {
  display: grid;
  position: relative;
  width: 68px;
  height: 68px;
  margin: 0 auto 18px;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-brand) 24%, var(--color-border-light));
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 8px 22px color-mix(in srgb, var(--color-brand) 18%, transparent);
  place-items: center;
  transition: transform var(--duration-normal), box-shadow var(--duration-normal);
}

.doc-agent__welcome-logo::after {
  position: absolute;
  border: 1px solid color-mix(in srgb, var(--color-brand) 32%, transparent);
  border-radius: inherit;
  content: '';
  inset: 4px;
  opacity: 0;
  transition: opacity var(--duration-normal), transform var(--duration-normal);
}

.doc-agent__welcome-logo:hover {
  box-shadow: 0 12px 28px color-mix(in srgb, var(--color-brand) 26%, transparent);
  transform: translateY(-3px) scale(1.04);
}

.doc-agent__welcome-logo:hover::after {
  opacity: 1;
  transform: scale(0.88);
}

.doc-agent__welcome-logo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.doc-agent__welcome h2,
.doc-agent__welcome p {
  margin: 0;
}

.doc-agent__welcome p {
  max-width: 680px;
  margin-top: 10px;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.doc-agent__welcome-greeting {
  min-height: 1.35em;
}

.doc-agent__welcome-character {
  display: inline-block;
  opacity: 0;
  animation: doc-agent-stream-character 160ms ease-out forwards;
}

.doc-agent__welcome-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 3px;
  background: var(--color-brand);
  vertical-align: -0.08em;
  animation: doc-agent-stream-cursor 720ms steps(1, end) infinite;
}

@keyframes doc-agent-stream-character {
  from {
    opacity: 0;
    transform: translateY(4px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes doc-agent-stream-cursor {
  0%,
  46% {
    opacity: 1;
  }

  47%,
  100% {
    opacity: 0;
  }
}

.doc-agent__message-turn {
  display: grid;
  max-width: 980px;
  margin: 0 auto 22px;
  align-items: flex-start;
  gap: 12px;
  grid-template-columns: 34px minmax(0, 1fr);
}

.doc-agent__message-turn > div:last-child {
  min-width: 0;
  padding: 12px 15px;
  border-radius: var(--radius-lg);
}

.doc-agent__message-turn p {
  margin: 6px 0 0;
  line-height: 1.7;
  white-space: pre-wrap;
}

.doc-agent__message-turn small {
  color: var(--color-text-tertiary);
}

.doc-agent__message-turn--user > div:last-child {
  background: var(--color-brand-soft);
}

.doc-agent__message-turn--agent > div:last-child {
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-surface-secondary);
}

.doc-agent__message-turn--agent {
  max-width: 1180px;
}

.doc-agent__message-turn--agent > .doc-agent__ai-response {
  padding: 0;
}

.doc-agent__ai-summary {
  position: sticky;
  z-index: 3;
  top: 0;
  padding: 13px 16px;
  border-bottom: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: color-mix(in srgb, var(--color-bg-surface-secondary) 96%, transparent);
  backdrop-filter: blur(8px);
}

.doc-agent__latest-action {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
}

.doc-agent__latest-button {
  box-shadow: var(--shadow-2);
}

.doc-agent__avatar {
  display: grid;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-md);
  background: var(--color-text-primary);
  color: var(--color-bg-surface);
  font-size: 12px;
  font-weight: 700;
  place-items: center;
}

.doc-agent__message-turn--agent .doc-agent__avatar {
  background: var(--color-brand);
  color: var(--color-text-inverse);
}

.doc-agent__composer-shell {
  padding: 12px clamp(16px, 4vw, 48px) 16px;
  border-top: 1px solid var(--color-border-light);
  background: color-mix(in srgb, var(--color-bg-surface) 94%, transparent);
}

.doc-agent__revision-target {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-agent__revision-target span,
.doc-agent__source-count {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.doc-agent__source-list {
  display: grid;
  max-height: 420px;
  margin-top: 16px;
  overflow-y: auto;
  gap: 7px;
}

.doc-agent__source-item {
  width: 100%;
  height: auto;
  min-height: 54px;
  margin-right: 0;
  padding: 8px 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.doc-agent__source-item > span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.doc-agent__source-item small {
  overflow: hidden;
  color: var(--color-text-tertiary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-agent__export-dialog {
  min-height: 150px;
}

.doc-agent__export-dialog .el-alert {
  margin-bottom: 22px;
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

.doc-agent__conversation-row {
  display: flex;
  align-items: center;
  border-radius: 10px;
}

.doc-agent__conversation-item {
  display: flex;
  flex: 1;
  min-width: 0;
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

.doc-agent__conversation-actions {
  flex: 0 0 auto;
  padding-right: 14px;
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
  max-width: none;
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.doc-agent__task :deep(.el-card__header) {
  padding: 14px 16px;
  border-bottom-color: var(--color-border-light);
}

.doc-agent__task :deep(.el-card__body) {
  padding: 16px;
}

.doc-agent__meta {
  margin: 18px 0;
}

.doc-agent__recovery {
  margin-top: 12px;
}

.doc-agent__actions {
  justify-content: flex-end;
  margin-top: 16px;
}

.doc-agent__lock-tag {
  margin-left: 12px;
}

.doc-agent__review-heading,
.doc-agent__panel-label,
.doc-agent__chat-header,
.doc-agent__rag-focus-heading,
.doc-agent__composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.doc-agent__review-heading {
  margin: 6px 0 14px;
}

.doc-agent__review-heading h3,
.doc-agent__review-heading p {
  margin: 0;
}

.doc-agent__review-heading p {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.doc-agent__section-workspace {
  display: grid;
  align-items: start;
  gap: 18px;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
}

.doc-agent__section-editor,
.doc-agent__revision-chat {
  min-width: 0;
}

.doc-agent__panel-label {
  margin-bottom: 10px;
}

.doc-agent__panel-label span,
.doc-agent__chat-header span,
.doc-agent__rag-focus-heading small,
.doc-agent__composer-footer span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.doc-agent__revision-chat {
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 18%, var(--el-border-color));
  border-radius: 14px;
  background:
    linear-gradient(
      145deg,
      color-mix(in srgb, var(--el-color-primary) 7%, var(--el-bg-color)) 0%,
      var(--el-bg-color) 42%
    );
  box-shadow: 0 10px 28px color-mix(in srgb, var(--el-color-primary) 7%, transparent);
}

.doc-agent__chat-header {
  padding: 15px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.doc-agent__chat-header > div {
  display: grid;
  gap: 3px;
}

.doc-agent__agent-dot {
  width: 10px;
  height: 10px;
  border: 3px solid color-mix(in srgb, var(--el-color-success) 22%, transparent);
  border-radius: 50%;
  background: var(--el-color-success);
  box-sizing: content-box;
}

.doc-agent__chat-history {
  display: flex;
  max-height: 360px;
  min-height: 150px;
  overflow-y: auto;
  padding: 16px;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
}

.doc-agent__chat-empty {
  display: grid;
  place-content: center;
  min-height: 118px;
  padding: 16px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.doc-agent__chat-empty strong {
  margin-bottom: 5px;
  color: var(--el-text-color-primary);
}

.doc-agent__message {
  display: grid;
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 13px;
  line-height: 1.55;
  gap: 5px;
}

.doc-agent__message small {
  opacity: 0.78;
  font-size: 11px;
}

.doc-agent__message--user {
  align-self: flex-end;
  border-bottom-right-radius: 4px;
  background: var(--el-color-primary);
  color: var(--el-color-white);
}

.doc-agent__message--agent {
  align-self: flex-start;
  border: 1px solid var(--el-border-color-lighter);
  border-bottom-left-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}

.doc-agent__message-status--completed {
  color: var(--el-color-success);
}

.doc-agent__message-status--failed {
  color: var(--el-color-danger);
}

.doc-agent__quick-commands,
.doc-agent__rag-focus {
  display: grid;
  padding: 12px 16px 0;
  gap: 8px;
}

.doc-agent__quick-commands > span,
.doc-agent__rag-focus-heading > span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}

.doc-agent__quick-commands > div,
.doc-agent__rag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.doc-agent__quick-commands button,
.doc-agent__rag-chips button {
  padding: 6px 9px;
  border: 1px solid var(--el-border-color);
  border-radius: 999px;
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  transition: 0.16s ease;
}

.doc-agent__quick-commands button:hover,
.doc-agent__rag-chips button:hover,
.doc-agent__rag-chips button.is-selected {
  border-color: var(--el-color-primary);
  background: color-mix(in srgb, var(--el-color-primary) 10%, var(--el-bg-color));
  color: var(--el-color-primary);
}

.doc-agent__quick-commands button:disabled,
.doc-agent__rag-chips button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.doc-agent__chat-composer {
  padding: 14px 16px 16px;
}

.doc-agent__use-bottom-composer {
  width: calc(100% - 32px);
  margin: 14px 16px 16px;
  padding: 9px 12px;
  border: 1px solid var(--color-brand);
  border-radius: var(--radius-sm);
  background: var(--color-brand-soft);
  color: var(--color-brand);
  cursor: pointer;
  font: inherit;
}

.doc-agent__use-bottom-composer:disabled {
  border-color: var(--color-border);
  color: var(--color-text-disabled);
  cursor: not-allowed;
}

.doc-agent__revision-scope {
  margin: 0 0 9px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.doc-agent__composer-footer {
  align-items: flex-end;
  margin-top: 10px;
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
  .doc-agent {
    height: auto;
  }

  .doc-agent__workbench {
    height: auto;
    min-height: 780px;
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(620px, 1fr);
  }

  .doc-agent__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__directory-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__section-workspace {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .doc-agent__conversation-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__messages {
    padding: 22px 14px 28px;
  }

  .doc-agent__composer-shell {
    padding: 10px;
  }

  .doc-agent__revision-target {
    align-items: stretch;
    flex-direction: column;
  }

  .doc-agent__conversation-row {
    align-items: stretch;
    flex-direction: column;
  }

  .doc-agent__conversation-item {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__conversation-actions {
    padding: 0 16px 10px;
  }

  .doc-agent__conversation-state {
    justify-items: start;
  }

  .doc-agent__review-heading,
  .doc-agent__composer-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-agent__composer-footer .el-button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .doc-agent__welcome-logo,
  .doc-agent__welcome-logo::after,
  .doc-agent__welcome-character {
    transition: none;
    animation: none;
  }

  .doc-agent__welcome-character {
    opacity: 1;
  }

  .doc-agent__welcome-cursor {
    display: none;
  }
}
</style>
