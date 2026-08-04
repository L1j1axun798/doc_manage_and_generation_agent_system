import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { GenerationTask } from '@/modules/document-generation'
import DocumentGenerationPanel from '@/modules/document-generation/components/DocumentGenerationPanel.vue'
import type { Project } from '@/modules/projects/projects.types'

const mocks = vi.hoisted(() => ({
  fetchGenerationTasks: vi.fn(),
  fetchGenerationTask: vi.fn(),
  fetchGenerationEvents: vi.fn(),
  fetchGenerationTemplates: vi.fn(),
  fetchDocuments: vi.fn(),
  stopGenerationTask: vi.fn(),
  deleteGenerationTask: vi.fn(),
  regenerateSection: vi.fn(),
}))

vi.mock('@/modules/document-generation/api/document-generation.api', () => ({
  approveGenerationTask: vi.fn(),
  confirmAndGenerate: vi.fn(),
  deleteGenerationTask: mocks.deleteGenerationTask,
  exportGenerationTask: vi.fn(),
  fetchGenerationEvents: mocks.fetchGenerationEvents,
  fetchGenerationTask: mocks.fetchGenerationTask,
  fetchGenerationTasks: mocks.fetchGenerationTasks,
  fetchGenerationTemplates: mocks.fetchGenerationTemplates,
  generateEntryPlan: vi.fn(),
  lockAllGeneratedSections: vi.fn(),
  regenerateSection: mocks.regenerateSection,
  retryGenerationTask: vi.fn(),
  setGeneratedSectionLock: vi.fn(),
  startGenerationPipeline: vi.fn(),
  stopGenerationTask: mocks.stopGenerationTask,
  submitGenerationReview: vi.fn(),
  updateGeneratedSection: vi.fn(),
}))

vi.mock('@/modules/documents/api/documents.api', () => ({
  downloadDocument: vi.fn(),
  fetchDocument: vi.fn(),
  fetchDocuments: mocks.fetchDocuments,
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

describe('document generation conversation directory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

    const wrapper = mount(DocumentGenerationPanel, {
      props: { project },
      global: {
        plugins: [createPinia(), ElementPlus],
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('历史会话')
    expect(wrapper.text()).toContain(task.template_name)
    expect(wrapper.find('.doc-agent__conversation-directory').exists()).toBe(true)
    expect(wrapper.find('.doc-agent__task').exists()).toBe(false)
    expect(mocks.fetchGenerationTask).not.toHaveBeenCalled()

    await wrapper.get('.doc-agent__conversation-item').trigger('click')
    await flushPromises()

    expect(mocks.fetchGenerationTask).toHaveBeenCalledWith(task.id)
    expect(wrapper.find('.doc-agent__conversation-directory').exists()).toBe(false)
    expect(wrapper.find('.doc-agent__task').exists()).toBe(true)

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
    await wrapper.get('.doc-agent__rag-chips button').trigger('click')
    const composer = wrapper.get(
      'textarea[placeholder="输入修改方向、需要加入的信息或其他调整指令…"]',
    )
    await composer.setValue('补充岗位分工')
    await wrapper.get('.doc-agent__composer-footer .el-button').trigger('click')
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
