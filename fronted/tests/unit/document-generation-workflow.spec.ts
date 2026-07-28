import type { DocumentItem } from '@/modules/documents/documents.types'
import {
  factFieldDefinition,
  isEligibleEntrySource,
  missingRequiredFactFields,
  proposalToConfirmedFact,
  shouldPollGenerationTask,
} from '@/modules/document-generation/workflow'

function documentItem(overrides: Partial<DocumentItem> = {}): DocumentItem {
  return {
    id: 1,
    project: 1,
    project_name: '项目',
    folder: 1,
    folder_name: '入场前置资料',
    title: '入场任务通知',
    description: '',
    access_level: 'internal',
    source_type: 'entrance_material',
    current_version: {
      id: 11,
      document: 1,
      version_number: 1,
      original_filename: '任务通知.docx',
      content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      file_size: 10,
      sha256: '0'.repeat(64),
      uploaded_by: 1,
      uploaded_by_name: '用户',
      created_at: '2026-07-25T00:00:00+08:00',
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
    created_by_name: '用户',
    created_at: '2026-07-25T00:00:00+08:00',
    updated_at: '2026-07-25T00:00:00+08:00',
    ...overrides,
  }
}

it('polls only while extraction or generation is running', () => {
  expect(shouldPollGenerationTask('extracting')).toBe(true)
  expect(shouldPollGenerationTask('queued')).toBe(true)
  expect(shouldPollGenerationTask('generating')).toBe(true)
  expect(shouldPollGenerationTask('needs_confirmation')).toBe(false)
  expect(shouldPollGenerationTask('failed')).toBe(false)
})

it('only accepts current entry-material documents as generation sources', () => {
  expect(isEligibleEntrySource(documentItem())).toBe(true)
  expect(
    isEligibleEntrySource(documentItem({ source_type: 'project_upload' })),
  ).toBe(false)
  expect(
    isEligibleEntrySource(documentItem({ folder_name: '报告模板' })),
  ).toBe(false)
  expect(
    isEligibleEntrySource(documentItem({ title: '塔筒检测报告' })),
  ).toBe(false)
  expect(
    isEligibleEntrySource(documentItem({ current_version: null })),
  ).toBe(false)
})

it('uses the first model evidence when confirming a proposed fact', () => {
  expect(
    proposalToConfirmedFact({
      field: 'project_name',
      value: '示例项目',
      value_type: 'string',
      confidence: 0.95,
      evidence: [
        {
          source_document_version_id: 11,
          locator: { paragraph_index: 0, text_quote: '项目名称：示例项目' },
          confidence: 0.9,
        },
      ],
    }),
  ).toEqual({
    field: 'project_name',
    value: '示例项目',
    value_type: 'string',
    source_document_version_id: 11,
    locator: { paragraph_index: 0, text_quote: '项目名称：示例项目' },
    confidence: 0.95,
  })
})

it('shows required canonical facts with Chinese labels and reports missing fields', () => {
  expect(factFieldDefinition('inspection_component_codes').label).toBe('检测部件')
  expect(factFieldDefinition('inspection_method_codes').options).toContainEqual({
    value: 'PAUT',
    label: '相控阵超声检测（PAUT）',
  })
  expect(
    missingRequiredFactFields(
      ['project_name', 'work_scope', 'risk_evidence_items'],
      [{
        field: 'project_name',
        value: '项目',
        value_type: 'string',
      }],
    ),
  ).toEqual(['work_scope', 'risk_evidence_items'])
})
