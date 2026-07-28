import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

import type { GenerationTask } from '@/modules/document-generation'
import DocumentGenerationPanel from '@/modules/document-generation/components/DocumentGenerationPanel.vue'
import type { Project } from '@/modules/projects/projects.types'

const mocks = vi.hoisted(() => ({
  fetchGenerationTasks: vi.fn(),
  fetchGenerationTask: vi.fn(),
  fetchGenerationEvents: vi.fn(),
  fetchGenerationTemplates: vi.fn(),
  fetchDocuments: vi.fn(),
}))

vi.mock('@/modules/document-generation/api/document-generation.api', () => ({
  approveGenerationTask: vi.fn(),
  confirmAndGenerate: vi.fn(),
  exportGenerationTask: vi.fn(),
  fetchGenerationEvents: mocks.fetchGenerationEvents,
  fetchGenerationTask: mocks.fetchGenerationTask,
  fetchGenerationTasks: mocks.fetchGenerationTasks,
  fetchGenerationTemplates: mocks.fetchGenerationTemplates,
  generateEntryPlan: vi.fn(),
  lockAllGeneratedSections: vi.fn(),
  regenerateSection: vi.fn(),
  retryGenerationTask: vi.fn(),
  setGeneratedSectionLock: vi.fn(),
  startGenerationPipeline: vi.fn(),
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
})
