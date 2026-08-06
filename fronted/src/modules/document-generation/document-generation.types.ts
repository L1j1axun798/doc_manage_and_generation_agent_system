export const DOCUMENT_PURPOSE = 'entry_four_measures_two_plans' as const
export const BUSINESS_TYPE = 'wind_turbine_inspection_four_measures_two_plans' as const

export type KnowledgeSectionCode =
  | 'overview'
  | 'organization_measures'
  | 'construction_plan'
  | 'technical_measures'
  | 'safety_measures'
  | 'risk_identification'
  | 'emergency_plan'
  | 'environmental_measures'

export type KnowledgeCorpusUploadStatus = 'queued' | 'processing' | 'succeeded' | 'failed'

export interface KnowledgeCorpusUpload {
  id: string
  filename: string
  file_sha256: string
  business_type: typeof BUSINESS_TYPE
  section_codes: KnowledgeSectionCode[]
  section_names: string[]
  indexed_section_codes: KnowledgeSectionCode[]
  indexed_section_names: string[]
  skipped_section_codes: KnowledgeSectionCode[]
  skipped_section_names: string[]
  status: KnowledgeCorpusUploadStatus
  chunk_count: number
  embedding_model_alias: string
  embedding_dimension: number | null
  error_code: string
  error_message: string
  created_by_name: string
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface RagSectionCoverage {
  code: KnowledgeSectionCode
  name: string
  chunk_count: number
}

export interface RagOperations {
  status: 'healthy' | 'processing' | 'attention'
  redis_status: 'ok' | 'unavailable'
  worker_status: 'idle' | 'busy' | 'offline' | 'unknown'
  queue_depth: number
  processing_uploads: number
  failed_uploads: number
  latest_upload_status: KnowledgeCorpusUploadStatus | null
  latest_upload_at: string | null
}

export interface RagOverview {
  knowledge_status: 'ready' | 'empty'
  knowledge_chunks: number
  source_documents: number
  covered_section_count: number
  total_section_count: number
  section_coverage: RagSectionCoverage[]
  last_indexed_at: string | null
  embedding_model_alias: string
  embedding_dimension: number
  operations: RagOperations | null
}

export type GenerationTaskStatus =
  | 'draft'
  | 'extracting'
  | 'needs_confirmation'
  | 'ready'
  | 'queued'
  | 'generating'
  | 'review_required'
  | 'pending_approval'
  | 'approved'
  | 'exported'
  | 'failed'
  | 'cancelled'

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
  display_name: string
  business_type: typeof BUSINESS_TYPE
  version: string
  document_version_id: number
  filename: string
  field_mapping: Record<string, unknown>
  section_order: string[]
  required_fact_fields: string[]
}

export type TemplateSyncStatus = 'synced' | 'already_present' | 'folder_missing'

export interface TemplateSelectionResult extends DocumentGenerationTemplate {
  sync_status: TemplateSyncStatus
}

export interface AgentPersonnelCertification {
  name: string
  certificate_number: string
  valid_until: string | null
}

export interface AgentPersonnelContext {
  id: string
  name: string
  gender: 'unknown' | 'male' | 'female'
  id_card_number: string
  phone: string
  job_title: string
  department: string
  contact: string
  certifications: AgentPersonnelCertification[]
  certificate_valid_until: string | null
  additional_info: Record<string, unknown>
}

export interface AvailableAgentPersonnel extends AgentPersonnelContext {
  folder_id: number
  gender_display: string
  profile_complete: boolean
  updated_at: string | null
}

export interface AgentTemplateContext {
  id: string
  code: string
  name: string
  filename: string
  version: string
  document_version_id: number
  format_locked: boolean
  constraints: {
    preserve_section_order: boolean
    preserve_heading_levels: boolean
    preserve_tables: boolean
    preserve_headers_and_footers: boolean
    preserve_typography_and_numbering: boolean
    fill_only_allowed_positions: boolean
  }
}

export interface AgentConversationContext {
  initial_message: string
  personnel: AgentPersonnelContext[]
  template: AgentTemplateContext | null
}

export interface GenerationConversationContextPayload {
  initial_message: string
  selected_personnel_ids: number[]
}

export interface ConversationSourceAttachment {
  document_version_id: number
  title: string
  filename: string
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

export type GenerationTraceEventType = 'system' | 'tool' | 'model' | 'rag'
export type GenerationTraceStatus = 'started' | 'succeeded' | 'failed' | 'skipped'

export interface GenerationTraceEvent {
  sequence: number
  stage: string
  event_type: GenerationTraceEventType
  tool: string
  status: GenerationTraceStatus
  title: string
  detail: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface GenerationReferenceSummary {
  project_source_files: number
  approved_rag_chunks: number
  approved_rag_source_files: number
  approved_clause_blocks: number
  used_rag_citations: number
}

export interface GenerationExportInfo {
  target_folder: string
  agent_generated_count: number
  default_filename: string
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
  conversation_context: AgentConversationContext
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
  reference_summary: GenerationReferenceSummary
}

export interface CreateGenerationTaskPayload {
  project_id: number
  template_id: number
  document_purpose: typeof DOCUMENT_PURPOSE
  business_type: typeof BUSINESS_TYPE
  idempotency_key: string
  conversation_context?: GenerationConversationContextPayload
  facts: Array<{
    field: string
    value: unknown
    value_type: string
  }>
}

export interface CreateGenerationPipelinePayload extends CreateGenerationTaskPayload {
  document_version_ids: number[]
}
