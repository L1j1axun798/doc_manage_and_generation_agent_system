import type { DocumentItem } from '@/modules/documents/documents.types'
import type {
  ConfirmedFactPayload,
  FactProposal,
  GenerationTaskStatus,
} from './document-generation.types'

export const GENERATION_POLL_INTERVAL_MS = 2000

const POLLING_STATUSES: ReadonlySet<GenerationTaskStatus> = new Set([
  'extracting',
  'queued',
  'generating',
])

const BLOCKED_FOLDER_NAMES = ['报告模板', '竣工资料档案', '完工资料', '检测报告']
const BLOCKED_FILE_MARKERS = ['检测报告', '试验报告', '验收报告', '完工报告', '竣工资料']

export function shouldPollGenerationTask(status: GenerationTaskStatus): boolean {
  return POLLING_STATUSES.has(status)
}

export function isEligibleEntrySource(document: DocumentItem): boolean {
  const names = `${document.folder_name} ${document.title} ${document.current_version?.original_filename || ''}`
  return Boolean(document.current_version)
    && !BLOCKED_FOLDER_NAMES.some((value) => document.folder_name.includes(value))
    && !BLOCKED_FILE_MARKERS.some((value) => names.includes(value))
}

export function proposalToConfirmedFact(proposal: FactProposal): ConfirmedFactPayload | null {
  const evidence = proposal.evidence?.[0]
  if (!evidence) {
    return null
  }
  return {
    field: proposal.field,
    value: proposal.value,
    value_type: proposal.value_type,
    source_document_version_id: evidence.source_document_version_id,
    locator: evidence.locator,
    confidence: proposal.confidence ?? evidence.confidence,
  }
}
