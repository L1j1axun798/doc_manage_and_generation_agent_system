import type { DocumentItem } from '@/modules/documents/documents.types'
import type {
  ConfirmedFactPayload,
  FactProposal,
  GenerationTaskStatus,
} from './document-generation.types'

export const GENERATION_POLL_INTERVAL_MS = 2000

export interface FactOption {
  value: string
  label: string
}

export interface FactFieldDefinition {
  label: string
  help: string
  valueType: 'string' | 'array'
  options?: FactOption[]
}

export const COMPONENT_OPTIONS: FactOption[] = [
  { value: 'tower_weld', label: '塔筒焊缝' },
  { value: 'tower_component', label: '塔筒部件（资料未细分）' },
  { value: 'high_strength_bolt', label: '高强度螺栓' },
  { value: 'pitch_bearing', label: '变桨轴承' },
  { value: 'blade_bolt', label: '叶片螺栓' },
]

export const METHOD_OPTIONS: FactOption[] = [
  { value: 'UT', label: '超声检测（UT）' },
  { value: 'PAUT', label: '相控阵超声检测（PAUT）' },
  { value: 'MT', label: '磁粉检测（MT）' },
  { value: 'PT', label: '渗透检测（PT）' },
  { value: 'VT', label: '目视检测（VT）' },
  { value: 'ET', label: '涡流检测（ET）' },
]

export const RISK_OPTIONS: FactOption[] = [
  { value: 'high_altitude', label: '高处作业' },
  { value: 'climbing_tower', label: '攀爬塔筒' },
  { value: 'electrical_work', label: '电气作业' },
  { value: 'temporary_power', label: '临时用电' },
  { value: 'fire_hot_work', label: '消防或动火' },
  { value: 'mechanical_injury', label: '机械伤害' },
  { value: 'falling_object', label: '物体打击或高空坠物' },
  { value: 'confined_space', label: '有限或狭小空间' },
  { value: 'extreme_weather', label: '极端天气' },
  { value: 'vehicle_traffic', label: '车辆交通' },
  { value: 'environmental_pollution', label: '环境污染' },
  { value: 'lifting_hoisting', label: '起吊或电动葫芦' },
]

export const FACT_FIELD_DEFINITIONS: Record<string, FactFieldDefinition> = {
  project_name: {
    label: '项目名称',
    help: '本次四措两案对应的完整项目名称。',
    valueType: 'string',
  },
  work_scope: {
    label: '工作范围',
    help: '写清机组数量、型号、检测部件和本次服务范围，以来源资料原文为准。',
    valueType: 'string',
  },
  inspection_component_codes: {
    label: '检测部件',
    help: '选择本项目实际检测的部件，可多选。',
    valueType: 'array',
    options: COMPONENT_OPTIONS,
  },
  inspection_method_codes: {
    label: '检测方法',
    help: '选择来源资料明确采用的检测方法，可多选。',
    valueType: 'array',
    options: METHOD_OPTIONS,
  },
  risk_evidence_items: {
    label: '当前项目风险依据',
    help: '只选择当前资料明确成立的风险，并逐项核对依据；没有明确风险时可不选。',
    valueType: 'array',
    options: RISK_OPTIONS,
  },
}

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
    && document.source_type === 'entrance_material'
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

export function factFieldDefinition(field: string): FactFieldDefinition {
  return FACT_FIELD_DEFINITIONS[field] || {
    label: field,
    help: 'Agent从来源资料中提取的补充事实。',
    valueType: 'string',
  }
}

export function missingRequiredFactFields(
  requiredFields: string[],
  proposals: Array<Pick<FactProposal, 'field'>>,
): string[] {
  const present = new Set(proposals.map((proposal) => proposal.field))
  return requiredFields.filter((field) => !present.has(field))
}
