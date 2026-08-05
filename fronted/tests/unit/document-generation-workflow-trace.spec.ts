import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { describe, expect, it } from 'vitest'

import GenerationWorkflowTrace from '@/modules/document-generation/components/GenerationWorkflowTrace.vue'
import type {
  GenerationTask,
  GenerationTraceEvent,
} from '@/modules/document-generation/document-generation.types'

const task = {
  status: 'generating',
  model_alias: 'qwen-test',
  reference_summary: {
    project_source_files: 2,
    approved_rag_chunks: 20,
    approved_rag_source_files: 4,
    approved_clause_blocks: 8,
    used_rag_citations: 0,
  },
} as GenerationTask

const events: GenerationTraceEvent[] = Array.from({ length: 5 }, (_, index) => ({
  sequence: index + 1,
  stage: index === 4 ? 'generating_sections' : 'parsing',
  event_type: index === 4 ? 'model' : 'tool',
  tool: `tool-${index + 1}`,
  status: index === 4 ? 'started' : 'succeeded',
  title: `执行状态 ${index + 1}`,
  detail: `状态详情 ${index + 1}`,
  metadata: {},
  created_at: `2026-08-05T10:0${index}:00+08:00`,
}))

describe('document generation workflow trace', () => {
  it('keeps the latest statuses compact and expands the full execution detail on demand', async () => {
    const wrapper = mount(GenerationWorkflowTrace, {
      props: { task, events },
      global: { plugins: [ElementPlus] },
    })

    expect(wrapper.text()).not.toContain('执行状态 1')
    expect(wrapper.text()).not.toContain('执行状态 2')
    expect(wrapper.text()).toContain('执行状态 3')
    expect(wrapper.text()).toContain('执行状态 5')
    expect(wrapper.text()).toContain('共 5 条状态')
    expect(wrapper.text()).toContain('展开全部执行详情（5 条）')

    await wrapper.get('.workflow-trace__expand-actions button').trigger('click')

    expect(wrapper.text()).toContain('执行状态 1')
    expect(wrapper.text()).toContain('执行状态 2')
    expect(wrapper.text()).toContain('当前项目事实资料 2 份')
    expect(wrapper.text()).toContain('收起执行详情')
  })
})
