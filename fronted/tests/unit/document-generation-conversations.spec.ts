import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { AuthUser } from '@/modules/auth/auth.types'
import { useAuthStore } from '@/modules/auth/stores/auth.store'
import type { GenerationTask } from '@/modules/document-generation'
import DocumentGenerationPanel from '@/modules/document-generation/components/DocumentGenerationPanel.vue'
import { useConversationContextStore } from '@/modules/document-generation/stores/conversation-context.store'
import type { DocumentItem } from '@/modules/documents/documents.types'
import type { Project } from '@/modules/projects/projects.types'

const mocks = vi.hoisted(() => ({
  fetchGenerationTasks: vi.fn(),
  fetchGenerationTask: vi.fn(),
  fetchGenerationEvents: vi.fn(),
  fetchGenerationTemplates: vi.fn(),
  fetchDocuments: vi.fn(),
  fetchAvailableAgentPersonnel: vi.fn(),
  confirmAndGenerate: vi.fn(),
  stopGenerationTask: vi.fn(),
  deleteGenerationTask: vi.fn(),
  regenerateSection: vi.fn(),
  retryGenerationTask: vi.fn(),
  startGenerationPipeline: vi.fn(),
  selectGenerationTemplate: vi.fn(),
  uploadClientTemplate: vi.fn(),
  uploadConversationAttachment: vi.fn(),
}))

vi.mock('@/modules/document-generation/api/document-generation.api', () => ({
  approveGenerationTask: vi.fn(),
  confirmAndGenerate: mocks.confirmAndGenerate,
  deleteGenerationTask: mocks.deleteGenerationTask,
  exportGenerationTask: vi.fn(),
  fetchGenerationEvents: mocks.fetchGenerationEvents,
  fetchGenerationTask: mocks.fetchGenerationTask,
  fetchGenerationTasks: mocks.fetchGenerationTasks,
  fetchGenerationTemplates: mocks.fetchGenerationTemplates,
  generateEntryPlan: vi.fn(),
  lockAllGeneratedSections: vi.fn(),
  regenerateSection: mocks.regenerateSection,
  retryGenerationTask: mocks.retryGenerationTask,
  setGeneratedSectionLock: vi.fn(),
  selectGenerationTemplate: mocks.selectGenerationTemplate,
  startGenerationPipeline: mocks.startGenerationPipeline,
  stopGenerationTask: mocks.stopGenerationTask,
  submitGenerationReview: vi.fn(),
  updateGeneratedSection: vi.fn(),
}))

vi.mock('@/modules/documents/api/documents.api', () => ({
  downloadDocument: vi.fn(),
  fetchDocument: vi.fn(),
  fetchDocuments: mocks.fetchDocuments,
}))

vi.mock('@/modules/document-generation/services/personnel.service', () => ({
  fetchAvailableAgentPersonnel: mocks.fetchAvailableAgentPersonnel,
}))

vi.mock('@/modules/document-generation/services/client-template.service', () => ({
  uploadClientTemplate: mocks.uploadClientTemplate,
  uploadConversationAttachment: mocks.uploadConversationAttachment,
}))

const project: Project = {
  id: 7,
  name: '海上风电示范项目',
  code: 'WF-007',
  description: '',
  manager: 1,
  manager_name: '项目经理',
  status: 'active',
  created_by: 1,
  created_by_name: '管理员',
  created_at: '2026-07-01T08:00:00+08:00',
  updated_at: '2026-07-28T08:00:00+08:00',
  archived_at: null,
  archived_by: null,
}

const currentUser: AuthUser = {
  id: 1,
  username: 'zhang.gong',
  real_name: '张工',
  employee_no: 'E001',
  role: 'project_manager',
  phone: '',
  email: '',
  is_active: true,
  must_change_password: false,
  webauthn_enabled: true,
  webauthn_credentials_count: 1,
  created_at: '2026-07-01T08:00:00+08:00',
}

const task: GenerationTask = {
  id: 'ca019b25-a270-42de-a80e-feb6b0da2101',
  project_id: project.id,
  project_name: project.name,
  template_id: 3,
  template_name: '风机质保检测四措两案模板',
  document_purpose: 'entry_four_measures_two_plans',
  business_type: 'wind_turbine_inspection_four_measures_two_plans',
  status: 'draft',
  operation: 'extract',
  progress: 0,
  conversation_context: {
    initial_message: '请开始编制四措两案',
    personnel: [],
    template: null,
  },
  facts_snapshot: [],
  fact_conflicts: [],
  risk_profile: {},
  pending_section_codes: [],
  provider_alias: '',
  model_alias: '',
  prompt_version: '',
  chunk_rule_version: '',
  generation_attempts: 0,
  error_code: '',
  error_message: '',
  output_document_version_id: null,
  output_document_id: null,
  created_by_name: '张工',
  reviewed_by_name: null,
  approved_at: null,
  started_at: null,
  completed_at: null,
  created_at: '2026-07-28T10:30:00+08:00',
  updated_at: '2026-07-28T10:30:00+08:00',
  sources: [],
  sections: [],
  reviews: [],
  reference_summary: {
    project_source_files: 0,
    approved_rag_chunks: 0,
    approved_rag_source_files: 0,
    approved_clause_blocks: 0,
    used_rag_citations: 0,
  },
}

function makeEntryDocument(index: number, filename = `entry-${index}.docx`): DocumentItem {
  return {
    id: 100 + index,
    project: project.id,
    project_name: project.name,
    folder: 2,
    folder_name: '入场前置资料',
    title: `参考资料 ${index}`,
    description: '',
    access_level: 'internal',
    source_type: 'entrance_material',
    current_version: {
      id: 200 + index,
      document: 100 + index,
      version_number: 1,
      original_filename: filename,
      content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      file_size: 128,
      sha256: String(index).repeat(64).slice(0, 64),
      uploaded_by: 1,
      uploaded_by_name: '张工',
      created_at: '2026-08-05T10:00:00+08:00',
    },
    can_download: true,
    can_update: true,
    can_delete: false,
    can_restore: false,
    can_create_version: true,
    lock_version: 1,
    deleted_at: null,
    deleted_by: null,
    deleted_by_name: null,
    created_by: 1,
    created_by_name: '张工',
    created_at: '2026-08-05T10:00:00+08:00',
    updated_at: '2026-08-05T10:00:00+08:00',
  }
}

describe('document generation conversation directory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchAvailableAgentPersonnel.mockResolvedValue([])
  })

  it('keeps the complete conversation interface visible and disabled before project selection', async () => {
    mocks.fetchGenerationTemplates.mockResolvedValue([])

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project: null },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()

    expect(wrapper.find('.doc-agent__workbench').exists()).toBe(true)
    expect(wrapper.text()).toContain('请先选择项目')
    expect(wrapper.text()).toContain('本功能仅编制入场前四措两案')
    expect(wrapper.find('.doc-agent__welcome .el-alert').exists()).toBe(false)
    expect(
      wrapper.findAll('.context-attachment-bar__label').map((item) => item.text()),
    ).toEqual(['模板', '材料', '人员'])
    expect(wrapper.find('.chat-composer__meta').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Enter 发送')
    expect(wrapper.get('.chat-composer__count').text()).toBe('0/4000')
    expect(wrapper.get('.chat-composer__actions [data-test="chat-send"]').text()).toBe('发送')
    expect(wrapper.findAll('.chat-composer__tool-button').map((button) => button.text())).toEqual([
      '上传甲方模板',
      '选择人员',
      '选择系统内参考资料',
      '从本机上传参考资料',
    ])
    expect(wrapper.get('[data-test="chat-send"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.conversation-sidebar__header button').attributes('disabled')).toBeDefined()
    expect(mocks.fetchGenerationTasks).not.toHaveBeenCalled()
    expect(mocks.fetchDocuments).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('lists historical conversations without automatically opening task details', async () => {
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [task],
    })
    mocks.fetchGenerationTask.mockResolvedValue(task)
    mocks.fetchGenerationEvents.mockResolvedValue([])

    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().user = currentUser
    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [pinia, ElementPlus],
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('编制会话')
    expect(wrapper.text()).toContain('对话1-张工')
    expect(wrapper.text()).not.toContain(task.template_name)
    expect(wrapper.text()).not.toContain('2026/07/28 10:30')
    expect(wrapper.find('.conversation-sidebar').exists()).toBe(true)
    expect(wrapper.get('.doc-agent__welcome-logo img').attributes('src')).toBe('/brand-logo.png')
    expect(wrapper.get('.doc-agent__welcome-greeting').attributes('aria-label')).toBe(
      'hello,张工,今天从哪里开始？',
    )
    expect(wrapper.find('.doc-agent__starter-prompts').exists()).toBe(false)
    expect(wrapper.get('.conversation-sidebar__scope-note').text()).toContain('不生成检测报告')
    expect(wrapper.find('.doc-agent__task').exists()).toBe(false)
    expect(mocks.fetchGenerationTask).not.toHaveBeenCalled()

    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(mocks.fetchGenerationTask).toHaveBeenCalledWith(task.id)
    expect(wrapper.find('.doc-agent__task').exists()).toBe(true)
    expect(wrapper.find('.doc-agent__message-turn--agent .doc-agent__task').exists()).toBe(true)

    wrapper.unmount()
  })

  it('offers document download after visible chapters are locked even if template metadata is stale', async () => {
    const reviewTask: GenerationTask = {
      ...task,
      status: 'review_required',
      operation: 'generate',
      progress: 90,
      sections: [
        {
          section_code: 'overview',
          title: '工程概况与编制依据',
          content: '已确认章节正文',
          structured_content: {},
          citations: [],
          validation_issues: [],
          revision: 1,
          is_locked: true,
          generated_at: '2026-08-07T10:00:00+08:00',
          updated_at: '2026-08-07T10:00:00+08:00',
        },
      ],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([
      {
        id: task.template_id,
        code: 'CLIENT-STALE-OUTLINE',
        client_name: '甲方提供',
        display_name: task.template_name,
        business_type: 'wind_turbine_inspection_four_measures_two_plans',
        version: '自主上传',
        document_version_id: 388,
        filename: 'client-template.docx',
        field_mapping: { self_service: true },
        section_order: ['overview', 'risk_identification'],
        required_fact_fields: ['project_name'],
        sync_status: 'synced',
      },
    ])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [reviewTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(reviewTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])

    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().user = currentUser
    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: { plugins: [pinia, ElementPlus] },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    const downloadButton = wrapper.findAll('button').find(
      (button) => button.text() === '下载生成文档',
    )
    expect(downloadButton).toBeDefined()
    expect(downloadButton?.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toContain('提交技术负责人批准')
    expect(wrapper.text()).not.toContain('技术负责人批准')

    wrapper.unmount()
  })

  it('uses an uploaded client template immediately without adding it as a source', async () => {
    const uploadedTemplate = {
      id: 88,
      code: 'CLIENT-7-abc',
      client_name: '甲方提供',
      display_name: '甲方现场模板',
      business_type: 'wind_turbine_inspection_four_measures_two_plans' as const,
      version: '自主上传',
      document_version_id: 388,
      filename: 'client-template.docx',
      field_mapping: { self_service: true, project_id: project.id },
      section_order: ['overview'],
      required_fact_fields: ['project_name'],
      sync_status: 'synced' as const,
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.uploadClientTemplate.mockResolvedValue(uploadedTemplate)

    const pinia = createPinia()
    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: { plugins: [pinia, ElementPlus] },
    })
    await flushPromises()
    const templateButton = wrapper.findAll('button').find((button) => button.text() === '上传甲方模板')
    await templateButton?.trigger('click')
    await wrapper.vm.$nextTick()
    const fileInput = wrapper.get('.template-selector__file-input')
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [new File(['template'], 'client-template.docx')],
    })
    await fileInput.trigger('change')
    await flushPromises()

    const draft = useConversationContextStore(pinia).forProject(project.id)
    expect(mocks.uploadClientTemplate).toHaveBeenCalledWith(
      project.id,
      expect.objectContaining({ name: 'client-template.docx' }),
    )
    expect(draft.templateId).toBe(uploadedTemplate.id)
    expect(draft.sourceVersionIds).toEqual([])
    expect(wrapper.text()).toContain(uploadedTemplate.display_name)
    wrapper.unmount()
  })

  it('refreshes only the selected history item from the conversation sidebar', async () => {
    const anotherTask: GenerationTask = {
      ...task,
      id: 'ca019b25-a270-42de-a80e-feb6b0da2102',
      progress: 30,
      template_name: '另一份四措两案模板',
    }
    const refreshedTask: GenerationTask = {
      ...anotherTask,
      progress: 55,
      updated_at: '2026-08-05T14:00:00+08:00',
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [task, anotherTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(refreshedTask)

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()

    const refreshButtons = wrapper.findAll('[data-test="refresh-conversation"]')
    expect(refreshButtons).toHaveLength(2)
    await refreshButtons[1]!.trigger('click')
    await flushPromises()

    expect(mocks.fetchGenerationTask).toHaveBeenCalledTimes(1)
    expect(mocks.fetchGenerationTask).toHaveBeenCalledWith(anotherTask.id)
    expect(mocks.fetchGenerationTasks).toHaveBeenCalledTimes(1)
    expect(mocks.fetchGenerationEvents).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('shows selected and uploaded reference files and enforces the five-file limit', async () => {
    const initialDocuments = Array.from({ length: 6 }, (_, index) => makeEntryDocument(index + 1))
    const uploadedDocument = makeEntryDocument(7, 'uploaded-reference.pdf')
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: initialDocuments.length,
      next: null,
      previous: null,
      results: initialDocuments,
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.uploadConversationAttachment.mockResolvedValue(uploadedDocument)

    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: { plugins: [pinia, ElementPlus] },
    })
    await flushPromises()

    const draft = useConversationContextStore().forProject(project.id)
    expect(draft.sourceVersionIds).toHaveLength(5)
    expect(wrapper.text()).toContain('选择系统内参考资料')
    expect(wrapper.text()).toContain('entry-1.docx')
    expect(wrapper.text()).toContain('entry-5.docx')
    expect(wrapper.text()).not.toContain('entry-6.docx')
    expect(wrapper.text()).toContain('参考资料 5/5 份')

    const fileInput = wrapper.get<HTMLInputElement>('input[type="file"]')
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [new File(['a'], 'extra-a.pdf'), new File(['b'], 'extra-b.pdf')],
    })
    await fileInput.trigger('change')
    await flushPromises()
    expect(mocks.uploadConversationAttachment).not.toHaveBeenCalled()

    draft.sourceVersionIds.pop()
    await wrapper.vm.$nextTick()
    Object.defineProperty(fileInput.element, 'files', {
      configurable: true,
      value: [new File(['content'], 'uploaded-reference.pdf')],
    })
    await fileInput.trigger('change')
    await flushPromises()

    expect(mocks.uploadConversationAttachment).toHaveBeenCalledTimes(1)
    expect(draft.sourceVersionIds).toHaveLength(5)
    expect(wrapper.text()).toContain('uploaded-reference.pdf')
    expect(wrapper.text()).toContain('参考资料 5/5 份')

    wrapper.unmount()
  })

  it('submits the first chat message with conversation-scoped template and personnel context', async () => {
    const template = {
      id: 3,
      code: 'T001',
      client_name: '示例甲方',
      display_name: task.template_name,
      business_type: 'wind_turbine_inspection_four_measures_two_plans' as const,
      version: 'v1',
      document_version_id: 10,
      filename: 'template.docx',
      field_mapping: {},
      section_order: ['overview'],
      required_fact_fields: ['project_name'],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([template])
    mocks.fetchDocuments.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{
        id: 31,
        project: project.id,
        project_name: project.name,
        folder: 2,
        folder_name: '入场前置资料',
        title: '入场任务通知',
        description: '',
        access_level: 'internal',
        source_type: 'entrance_material',
        current_version: {
          id: 194,
          document: 31,
          version_number: 1,
          original_filename: 'entry.docx',
          content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          file_size: 128,
          sha256: '1'.repeat(64),
          uploaded_by: 1,
          uploaded_by_name: '张工',
          created_at: '2026-07-30T10:00:00+08:00',
        },
        can_download: true,
        can_update: true,
        can_delete: false,
        can_restore: false,
        can_create_version: true,
        lock_version: 1,
        deleted_at: null,
        deleted_by: null,
        deleted_by_name: null,
        created_by: 1,
        created_by_name: '张工',
        created_at: '2026-07-30T10:00:00+08:00',
        updated_at: '2026-07-30T10:00:00+08:00',
      }],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchAvailableAgentPersonnel.mockResolvedValue([{
      id: '22',
      user_id: 22,
      project_member_id: 8,
      name: '项目成员',
      job_title: '项目操作人员',
      department: '',
      contact: '',
      certifications: [],
      certificate_valid_until: null,
      additional_info: { project_role: 'operator' },
    }])
    const createdTask: GenerationTask = {
      ...task,
      status: 'extracting',
      progress: 5,
      conversation_context: {
        initial_message: '请重点核对人员分工后开始编制',
        personnel: [{
          id: '22',
          name: '项目成员',
          job_title: '项目操作人员',
          department: '',
          contact: '',
          certifications: [],
          certificate_valid_until: null,
          additional_info: { project_role: 'operator' },
        }],
        template: null,
      },
    }
    mocks.startGenerationPipeline.mockResolvedValue(createdTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])

    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: { plugins: [pinia, ElementPlus] },
    })
    await flushPromises()
    const contextStore = useConversationContextStore()
    const draft = contextStore.forProject(project.id)
    draft.templateId = template.id
    draft.personnelIds = [22]
    draft.sourceVersionIds = []
    draft.message = '请重点核对人员分工后开始编制'
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-test="chat-send"]').trigger('click')
    await flushPromises()

    expect(mocks.startGenerationPipeline).toHaveBeenCalledWith(expect.objectContaining({
      template_id: template.id,
      document_version_ids: [],
      conversation_context: {
        initial_message: '请重点核对人员分工后开始编制',
        selected_personnel_ids: [22],
      },
    }))
    expect(wrapper.text()).toContain('项目成员')
    expect(wrapper.text()).toContain('本次生成将严格使用当前模板')
    wrapper.unmount()
  })

  it('sends chapter revision instructions and selected approved RAG references', async () => {
    const reviewTask: GenerationTask = {
      ...task,
      status: 'review_required',
      operation: 'generate',
      progress: 90,
      sections: [
        {
          section_code: 'overview',
          title: '工程概况与编制依据',
          content: '原章节正文',
          structured_content: {},
          citations: [
            {
              chunk_id: 'approved-chunk-001',
              source_document_version_id: 198,
              locator: { heading_path: ['工程概况', '人员分工'] },
            },
          ],
          validation_issues: [],
          revision: 1,
          is_locked: false,
          generated_at: '2026-07-30T10:00:00+08:00',
          updated_at: '2026-07-30T10:00:00+08:00',
        },
      ],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [reviewTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(reviewTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])
    mocks.regenerateSection.mockResolvedValue({
      ...reviewTask,
      status: 'queued',
      pending_section_codes: ['overview'],
      reviews: [
        {
          id: 8,
          section_code: 'overview',
          action: 'section_regenerated',
          comment: '补充岗位分工',
          metadata: {
            conversation_status: 'queued',
            assistant_message: '已收到修改要求，正在重新生成本章。',
          },
          actor_name: '张工',
          created_at: '2026-07-30T10:10:00+08:00',
        },
      ],
    })

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('与 Agent 修改本章')
    expect(wrapper.text()).toContain('特别参照的RAG信息')
    expect(wrapper.get('.chat-composer').classes()).toContain('is-collapsed')
    await wrapper.get('button[aria-label="展开聊天框"]').trigger('click')
    expect(wrapper.get('.chat-composer').classes()).not.toContain('is-collapsed')
    expect(wrapper.get('button[aria-label="收起聊天框"]').exists()).toBe(true)
    await wrapper.get('.doc-agent__rag-chips button').trigger('click')
    const composer = wrapper.get(
      'textarea[placeholder="输入对目标章节的修改要求…"]',
    )
    await composer.setValue('补充岗位分工')
    await wrapper.get('[data-test="chat-send"]').trigger('click')
    await flushPromises()

    expect(mocks.regenerateSection).toHaveBeenCalledWith(
      reviewTask.id,
      'overview',
      '补充岗位分工',
      ['approved-chunk-001'],
    )
    expect(wrapper.text()).toContain('已收到修改要求')

    wrapper.unmount()
  })

  it('shows invalid evidence facts with an actionable recovery path', async () => {
    const recoveryTask: GenerationTask = {
      ...task,
      status: 'needs_confirmation',
      progress: 20,
      error_code: 'FACT_EVIDENCE_INVALID',
      error_message: '部分项目事实的来源已失效，请重新核对标记项后再次提交',
      fact_conflicts: [{ field: 'project_name', reason: 'evidence_invalid' }],
      facts_snapshot: [
        {
          field: 'project_name',
          value: project.name,
          value_type: 'string',
          source_document_version_id: 194,
          locator: {
            paragraph_index: 3,
            text_quote: `项目名称：${project.name}`,
          },
          confidence: 1,
        },
      ],
      sources: [
        {
          id: 1,
          document_version_id: 194,
          document_title: '入场任务通知',
          filename: 'entry.docx',
          file_sha256: '1'.repeat(64),
          parse_status: 'parsed',
          parse_error: '',
          created_at: '2026-07-28T10:00:00+08:00',
        },
      ],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([
      {
        id: recoveryTask.template_id,
        code: 'T001',
        client_name: '示例客户',
        display_name: recoveryTask.template_name,
        business_type: 'wind_turbine_inspection_four_measures_two_plans',
        version: 'v1',
        document_version_id: 10,
        filename: 'template.docx',
        field_mapping: {},
        section_order: ['overview'],
        required_fact_fields: ['project_name'],
      },
    ])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [recoveryTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(recoveryTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('来源需核对')
    expect(wrapper.text()).toContain('重新核对标记事实的来源资料和来源原文')
    expect(
      wrapper.findAll('textarea').some((input) => input.element.value === project.name),
    ).toBe(true)

    wrapper.unmount()
  })

  it('confirms a key fact whose evidence comes from the user prompt', async () => {
    const promptFactTask: GenerationTask = {
      ...task,
      status: 'needs_confirmation',
      progress: 20,
      facts_snapshot: [
        {
          field: 'project_name',
          value: project.name,
          value_type: 'string',
          evidence: [
            {
              source_document_version_id: 0,
              locator: {
                paragraph_index: 0,
                text_quote: `项目名称：${project.name}`,
              },
              confidence: 1,
            },
          ],
          confidence: 1,
        },
      ],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([
      {
        id: promptFactTask.template_id,
        code: 'T001',
        client_name: '示例客户',
        display_name: promptFactTask.template_name,
        business_type: 'wind_turbine_inspection_four_measures_two_plans',
        version: 'v1',
        document_version_id: 10,
        filename: 'template.docx',
        field_mapping: {},
        section_order: ['overview'],
        required_fact_fields: ['project_name'],
      },
    ])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [promptFactTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(promptFactTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])
    mocks.confirmAndGenerate.mockResolvedValue({
      ...promptFactTask,
      status: 'generating',
    })

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('优先从你本次输入的 Prompt 识别')
    const confirmButton = wrapper.findAll('button').find(
      (button) => button.text().includes('确认并开始编制'),
    )
    expect(confirmButton).toBeDefined()
    await confirmButton!.trigger('click')
    await flushPromises()

    expect(mocks.confirmAndGenerate).toHaveBeenCalledWith(promptFactTask.id, [
      expect.objectContaining({
        field: 'project_name',
        source_document_version_id: 0,
      }),
    ])

    wrapper.unmount()
  })

  it('offers prompt re-extraction when the worker returned an empty fact snapshot', async () => {
    const emptyFactTask: GenerationTask = {
      ...task,
      status: 'needs_confirmation',
      progress: 20,
      facts_snapshot: [],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [emptyFactTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(emptyFactTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])
    mocks.retryGenerationTask.mockResolvedValue({
      ...emptyFactTask,
      status: 'extracting',
    })

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    const retryButton = wrapper.findAll('button').find(
      (button) => button.text().includes('重新识别 Prompt'),
    )
    expect(retryButton).toBeDefined()
    await retryButton!.trigger('click')
    await flushPromises()

    expect(mocks.retryGenerationTask).toHaveBeenCalledWith(emptyFactTask.id)
    wrapper.unmount()
  })

  it('shows a validation recovery point and resumes from the failed section', async () => {
    const recoveryTask: GenerationTask = {
      ...task,
      status: 'failed',
      operation: 'generate',
      progress: 78,
      error_code: 'VALIDATION_FAILED',
      error_message: '章节 risk_identification 未通过确定性校验：风险项缺少对应的预控措施。',
      pending_section_codes: ['risk_identification', 'emergency_plan'],
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [recoveryTask],
    })
    mocks.fetchGenerationTask.mockResolvedValue(recoveryTask)
    mocks.fetchGenerationEvents.mockResolvedValue([])

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('风险项缺少对应的预控措施')
    expect(wrapper.text()).toContain('系统已保留通过校验的章节')
    expect(wrapper.text()).toContain('从失败章节继续')
    expect(wrapper.text()).toContain('风险辨识与预控')

    wrapper.unmount()
  })

  it('stops a running conversation from the history directory', async () => {
    const runningTask: GenerationTask = {
      ...task,
      status: 'generating',
      operation: 'generate',
      progress: 68,
    }
    const stoppedTask: GenerationTask = {
      ...runningTask,
      status: 'cancelled',
    }
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [runningTask],
    })
    mocks.stopGenerationTask.mockResolvedValue(stoppedTask)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('[data-test="stop-conversation"]').trigger('click')
    await flushPromises()

    expect(mocks.stopGenerationTask).toHaveBeenCalledWith(task.id)
    expect(wrapper.text()).toContain('已停止')
    expect(wrapper.find('[data-test="delete-conversation"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('deletes a completed conversation from the history directory', async () => {
    mocks.fetchGenerationTemplates.mockResolvedValue([])
    mocks.fetchDocuments.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })
    mocks.fetchGenerationTasks.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [task],
    })
    mocks.deleteGenerationTask.mockResolvedValue(undefined)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()
    await wrapper.get('[data-test="delete-conversation"]').trigger('click')
    await flushPromises()

    expect(mocks.deleteGenerationTask).toHaveBeenCalledWith(task.id)
    expect(wrapper.find('.doc-agent__conversation-item').exists()).toBe(false)

    wrapper.unmount()
  })
})
