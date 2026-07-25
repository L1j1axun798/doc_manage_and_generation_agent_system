export const DOCUMENT_PURPOSE = 'entry_four_measures_two_plans' as const
export const BUSINESS_TYPE = 'wind_turbine_inspection_four_measures_two_plans' as const

export type GenerationTaskStatus =
  | 'draft'
  | 'extracting'
  | 'needs_confirmation'
  | 'ready'
  | 'queued'
  | 'generating'
  | 'review_required'
  | 'approved'
  | 'exported'
  | 'failed'

export type GenerationOperation = 'extract' | 'generate'

export interface SourceLocator {
  heading_path?: string[]
  paragraph_index?: number | null
  page?: number | null
  table_index?: number | null
  text_quote?: string | null
}

export interface FactEvidence {
  source_document_version_id: number
  locator: SourceLocator
  confidence: number
}

export interface FactProposal {
  field: string
  value: unknown
  value_type: string
  evidence?: FactEvidence[]
  confidence?: number
}

export interface ConfirmedFactPayload {
  field: string
  value: unknown
  value_type: string
  source_document_version_id: number
  locator: SourceLocator
  confidence: number
}

export interface DocumentGenerationTemplate {
  id: number
  code: string
  client_name: string
  business_type: typeof BUSINESS_TYPE
  version: string
  document_version_id: number
  filename: string
  field_mapping: Record<string, unknown>
  section_order: string[]
  required_fact_fields: string[]
}

export interface GenerationSource {
  id: number
  document_version_id: number
  document_title: string
  filename: string
  file_sha256: string
  parse_status: 'pending' | 'parsed' | 'failed'
  parse_error: string
  created_at: string
}

export interface GeneratedSection {
  section_code: string
  title: string
  content: string
  structured_content: Record<string, unknown>
  citations: Array<Record<string, unknown>>
  validation_issues: Array<{
    code: string
    message: string
    severity: 'info' | 'warning' | 'error'
  }>
  revision: number
  is_locked: boolean
  generated_at: string
  updated_at: string
}

export interface GenerationReview {
  id: number
  section_code: string | null
  action: string
  comment: string
  metadata: Record<string, unknown>
  actor_name: string
  created_at: string
}

export interface GenerationTask {
  id: string
  project_id: number
  project_name: string
  template_id: number
  template_name: string
  document_purpose: typeof DOCUMENT_PURPOSE
  business_type: typeof BUSINESS_TYPE
  status: GenerationTaskStatus
  operation: GenerationOperation
  progress: number
  facts_snapshot: FactProposal[] | ConfirmedFactPayload[]
  fact_conflicts: Array<Record<string, unknown>>
  risk_profile: Record<string, unknown>
  pending_section_codes: string[]
  provider_alias: string
  model_alias: string
  prompt_version: string
  chunk_rule_version: string
  generation_attempts: number
  error_code: string
  error_message: string
  output_document_version_id: number | null
  output_document_id: number | null
  created_by_name: string
  reviewed_by_name: string | null
  approved_at: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
  sources: GenerationSource[]
  sections: GeneratedSection[]
  reviews: GenerationReview[]
}

export interface CreateGenerationTaskPayload {
  project_id: number
  template_id: number
  document_purpose: typeof DOCUMENT_PURPOSE
  business_type: typeof BUSINESS_TYPE
  idempotency_key: string
  facts: Array<{
    field: string
    value: unknown
    value_type: string
  }>
}
