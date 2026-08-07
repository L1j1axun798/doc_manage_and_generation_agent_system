from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

DocumentPurpose = Literal["entry_four_measures_two_plans"]
DOCUMENT_PURPOSE: Final[DocumentPurpose] = "entry_four_measures_two_plans"
ENTRY_PLAN_SECTION_CODES: Final[tuple[str, ...]] = (
    "overview",
    "organization_measures",
    "construction_plan",
    "technical_measures",
    "safety_measures",
    "risk_identification",
    "emergency_plan",
    "environmental_measures",
)
ENTRY_PLAN_SECTION_TITLES: Final[dict[str, str]] = {
    "overview": "工程概况与编制依据",
    "organization_measures": "组织措施",
    "construction_plan": "施工方案",
    "technical_measures": "技术措施",
    "safety_measures": "安全措施",
    "risk_identification": "风险辨识与管控",
    "emergency_plan": "应急预案",
    "environmental_measures": "环境保护与文明施工措施",
}
ENTRY_PLAN_SECTION_BLUEPRINTS: Final[dict[str, tuple[str, ...]]] = {
    "overview": (
        "项目基本信息和工作范围",
        "检测对象数量方法及计划工期",
        "编制依据和适用边界",
        "人员设备及入场条件概述",
    ),
    "organization_measures": (
        "组织架构和岗位职责",
        "人员资格培训及技术安全交底",
        "进场协调沟通和信息报告",
        "设备工器具及防护用品管理",
        "作业过程监督和责任落实",
    ),
    "construction_plan": (
        "施工准备和进场安排",
        "检测作业流程和工序衔接",
        "各检测方法的实施步骤",
        "现场配合和作业区域管理",
        "质量记录复核及资料管理",
        "退场和现场恢复安排",
    ),
    "technical_measures": (
        "技术依据和方法适用范围",
        "仪器设备状态及校准核验",
        "检测前技术准备",
        "检测过程技术控制",
        "质量复核和记录要求",
        "异常情况的技术处置边界",
    ),
    "safety_measures": (
        "安全责任和入场教育",
        "个人防护及工器具安全",
        "作业许可和现场隔离",
        "已识别风险的逐项预控",
        "高风险作业监护和停止作业条件",
        "班前班后检查及安全记录",
    ),
    "risk_identification": (
        "风险辨识方法和责任",
        "已确认危险源逐项分析",
        "风险预防控制措施",
        "动态风险复核和升级报告",
        "措施落实检查和闭环要求",
    ),
    "emergency_plan": (
        "应急组织和岗位职责",
        "信息报告及联络机制",
        "现场警戒疏散和先期处置",
        "已识别风险的专项处置",
        "外部救援衔接和人员转运",
        "应急终止复工及记录要求",
    ),
    "environmental_measures": (
        "环境保护责任和现场文明要求",
        "废弃物废液及污染预防",
        "生态噪声消防和交通影响控制",
        "现场清理恢复和检查记录",
    ),
}
# The technical owner recorded that a usable eight-section plan normally contains
# at least about 15,000 Chinese characters. The distribution prevents one long
# chapter from hiding major omissions in another chapter.
ENTRY_PLAN_SECTION_MIN_CHARACTERS: Final[dict[str, int]] = {
    "overview": 1200,
    "organization_measures": 1600,
    "construction_plan": 2800,
    "technical_measures": 2500,
    "safety_measures": 2600,
    "risk_identification": 1600,
    "emergency_plan": 1800,
    "environmental_measures": 1000,
}
NonBlankString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256String = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

FORBIDDEN_FACT_FIELD_PARTS = frozenset(
    {
        "actual_result",
        "completion_result",
        "defect",
        "detection_conclusion",
        "inspection_conclusion",
        "inspection_result",
        "measured_result",
        "test_conclusion",
        "test_result",
        "实测结果",
        "完工结果",
        "检测结论",
        "检测结果",
        "缺陷清单",
        "验收结论",
    }
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ParsedBlockType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class WorkflowStage(StrEnum):
    INITIALIZED = "initialized"
    PARSING = "parsing"
    EXTRACTING_FACTS = "extracting_facts"
    VALIDATING_FACTS = "validating_facts"
    BUILDING_RISK_PROFILE = "building_risk_profile"
    SELECTING_CLAUSES = "selecting_clauses"
    RETRIEVING_REFERENCES = "retrieving_references"
    GENERATING_SECTIONS = "generating_sections"
    VALIDATING_SECTIONS = "validating_sections"
    RENDERING = "rendering"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


class TraceStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceLocator(ContractModel):
    heading_path: tuple[str, ...] = ()
    paragraph_index: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=1)
    table_index: int | None = Field(default=None, ge=0)
    text_quote: str | None = Field(default=None, max_length=200)


class SourceDocument(ContractModel):
    document_version_id: int = Field(ge=0)
    filename: NonBlankString
    mime_type: NonBlankString
    content: bytes = Field(repr=False, min_length=1)
    purpose: DocumentPurpose = DOCUMENT_PURPOSE


class ParsedBlock(ContractModel):
    block_id: NonBlankString
    block_type: ParsedBlockType
    text: NonBlankString
    heading_path: tuple[str, ...] = ()
    locator: SourceLocator
    rows: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def validate_table_rows(self) -> ParsedBlock:
        if self.block_type == ParsedBlockType.TABLE and not self.rows:
            raise ValueError("table blocks require rows")
        if self.block_type != ParsedBlockType.TABLE and self.rows:
            raise ValueError("only table blocks may contain rows")
        return self


class ParsedDocument(ContractModel):
    document_version_id: int = Field(ge=0)
    filename: NonBlankString
    mime_type: NonBlankString
    content_sha256: Sha256String
    title: NonBlankString
    blocks: tuple[ParsedBlock, ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()


def _validate_fact_field_name(value: str) -> str:
    normalized = value.strip().lower()
    if any(part in normalized for part in FORBIDDEN_FACT_FIELD_PARTS):
        raise ValueError("result and conclusion fields are forbidden for entry plans")
    return normalized


class FactCandidate(ContractModel):
    field: NonBlankString
    value: JsonValue
    value_type: NonBlankString
    source_document_version_id: int = Field(ge=0)
    locator: SourceLocator
    confidence: float = Field(ge=0, le=1)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_fact_field_name(value)


class ConfirmedFact(FactCandidate):
    confirmed_by: int = Field(gt=0)


class FactEvidence(ContractModel):
    source_document_version_id: int = Field(ge=0)
    locator: SourceLocator
    confidence: float = Field(ge=0, le=1)


class MergedFactCandidate(ContractModel):
    field: NonBlankString
    value: JsonValue
    value_type: NonBlankString
    evidence: tuple[FactEvidence, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        return _validate_fact_field_name(value)


class FactConflict(ContractModel):
    field: NonBlankString
    candidates: tuple[MergedFactCandidate, ...] = Field(min_length=2)


class RejectedFactCandidate(ContractModel):
    field: NonBlankString
    reason_code: NonBlankString
    source_document_version_id: int = Field(ge=0)


class FactMergeResult(ContractModel):
    merged: tuple[MergedFactCandidate, ...] = ()
    conflicts: tuple[FactConflict, ...] = ()
    rejected: tuple[RejectedFactCandidate, ...] = ()


class FactExtractionResponse(ContractModel):
    facts: tuple[FactCandidate, ...] = ()


class RiskEvidence(ContractModel):
    risk_code: NonBlankString
    evidence: NonBlankString
    source_document_version_id: int | None = Field(default=None, ge=0)
    locator: SourceLocator | None = None


class RiskProfile(ContractModel):
    risk_codes: tuple[str, ...] = ()
    evidence: tuple[RiskEvidence, ...] = ()

    @model_validator(mode="after")
    def evidence_matches_codes(self) -> RiskProfile:
        known_codes = set(self.risk_codes)
        if any(item.risk_code not in known_codes for item in self.evidence):
            raise ValueError("risk evidence must reference a risk code in the profile")
        return self


class ClauseSelection(ContractModel):
    clause_id: NonBlankString
    clause_code: NonBlankString
    clause_version: NonBlankString
    section_code: NonBlankString
    text: NonBlankString
    matched_risk_codes: tuple[str, ...] = ()


class SourceCitation(ContractModel):
    source_document_version_id: int = Field(ge=0)
    locator: SourceLocator
    chunk_id: str | None = None
    fact_field: str | None = None


class RetrievedSection(ContractModel):
    chunk_id: NonBlankString
    source_document_version_id: int = Field(gt=0)
    section_code: NonBlankString
    heading_path: tuple[str, ...]
    text: NonBlankString
    similarity: float = Field(ge=-1, le=1)
    final_score: float
    client_code: str | None = None
    component_tags: tuple[str, ...] = ()
    method_tags: tuple[str, ...] = ()
    risk_tags: tuple[str, ...] = ()


class RetrievalQuery(ContractModel):
    business_type: NonBlankString
    section_code: NonBlankString
    query_text: NonBlankString
    client_code: str | None = None
    component_tags: tuple[str, ...] = ()
    method_tags: tuple[str, ...] = ()
    risk_tags: tuple[str, ...] = ()
    top_k: int = Field(default=5, ge=1, le=8)
    min_similarity: float = Field(default=0.2, ge=-1, le=1)


class RetrievalTraceItem(ContractModel):
    chunk_id: NonBlankString
    source_document_version_id: int = Field(gt=0)
    similarity: float
    tag_score: float
    method_score: float
    client_score: float
    final_score: float
    selected: bool
    rejection_reason: str | None = None


class RetrievalResult(ContractModel):
    query: RetrievalQuery
    sections: tuple[RetrievedSection, ...] = ()
    trace: tuple[RetrievalTraceItem, ...] = ()
    embedding_model_alias: NonBlankString
    embedding_dimension: int = Field(gt=0)


class PersonnelCertificationContext(ContractModel):
    name: str = ""
    certificate_number: str = ""
    valid_until: str | None = None


class PersonnelContext(ContractModel):
    id: NonBlankString
    name: NonBlankString
    gender: str = "unknown"
    id_card_number: str = ""
    phone: str = ""
    job_title: str = ""
    department: str = ""
    contact: str = ""
    certifications: tuple[PersonnelCertificationContext, ...] = ()
    certificate_valid_until: str | None = None
    additional_info: dict[str, JsonValue] = Field(default_factory=dict)


class TemplateFormatConstraints(ContractModel):
    preserve_section_order: bool = True
    preserve_heading_levels: bool = True
    preserve_tables: bool = True
    preserve_headers_and_footers: bool = True
    preserve_typography_and_numbering: bool = True
    fill_only_allowed_positions: bool = True


class AgentTemplateContext(ContractModel):
    id: NonBlankString
    code: NonBlankString
    name: NonBlankString
    filename: NonBlankString
    version: NonBlankString
    document_version_id: int = Field(gt=0)
    format_locked: bool = True
    constraints: TemplateFormatConstraints = Field(default_factory=TemplateFormatConstraints)


class AgentConversationContext(ContractModel):
    initial_message: str = Field(default="", max_length=4000)
    personnel: tuple[PersonnelContext, ...] = Field(default=(), max_length=50)
    template: AgentTemplateContext | None = None


class SectionContext(ContractModel):
    section_code: NonBlankString
    objective: NonBlankString
    confirmed_facts: tuple[ConfirmedFact, ...]
    risk_profile: RiskProfile
    clauses: tuple[ClauseSelection, ...] = ()
    references: tuple[RetrievedSection, ...] = ()
    conversation_context: AgentConversationContext = Field(default_factory=AgentConversationContext)
    revision_instruction: str = ""
    revision_conversation: tuple[str, ...] = ()
    revision_required_literals: tuple[str, ...] = ()
    previous_content: str = ""


class GeneratedTable(ContractModel):
    headers: tuple[str, ...] = Field(min_length=1)
    rows: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def validate_row_width(self) -> GeneratedTable:
        expected_width = len(self.headers)
        if any(len(row) != expected_width for row in self.rows):
            raise ValueError("generated table rows must match the header width")
        return self


class GeneratedSection(ContractModel):
    section_code: NonBlankString
    title: NonBlankString
    paragraphs: tuple[str, ...] = ()
    lists: tuple[tuple[str, ...], ...] = ()
    tables: tuple[GeneratedTable, ...] = ()
    citations: tuple[SourceCitation, ...] = ()
    used_fact_fields: tuple[str, ...] = ()
    used_clause_ids: tuple[str, ...] = ()
    missing_items: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_provenance(self) -> GeneratedSection:
        if len(self.used_fact_fields) != len(set(self.used_fact_fields)):
            raise ValueError("used_fact_fields must be unique")
        if len(self.used_clause_ids) != len(set(self.used_clause_ids)):
            raise ValueError("used_clause_ids must be unique")
        return self


class ValidationIssue(ContractModel):
    code: NonBlankString
    message: NonBlankString
    severity: ValidationSeverity
    section_code: str | None = None


class PersistedSection(ContractModel):
    task_key: NonBlankString
    section_code: NonBlankString
    revision: int = Field(ge=1)
    locked: bool = False
    section: GeneratedSection
    validation_issues: tuple[ValidationIssue, ...] = ()

    @model_validator(mode="after")
    def section_code_matches(self) -> PersistedSection:
        if self.section.section_code != self.section_code:
            raise ValueError("persisted section code does not match section")
        return self


class ModelCallPurpose(StrEnum):
    FACT_EXTRACTION = "fact_extraction"
    SECTION_GENERATION = "section_generation"
    SECTION_REVISION = "section_revision"
    SCHEMA_REPAIR = "schema_repair"


class ModelUsageRecord(ContractModel):
    purpose: ModelCallPurpose
    model_alias: NonBlankString
    prompt_version: NonBlankString
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    request_id: str | None = None
    retry_count: int = Field(ge=0)


class TemplateDocument(ContractModel):
    template_id: NonBlankString
    filename: NonBlankString
    content: bytes = Field(repr=False, min_length=1)
    required_placeholders: tuple[str, ...] = ()
    purpose: DocumentPurpose = DOCUMENT_PURPOSE


class TemplateValidationResult(ContractModel):
    valid: bool
    declared_placeholders: tuple[str, ...] = ()
    missing_placeholders: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class RenderRequest(ContractModel):
    template: TemplateDocument
    facts: tuple[ConfirmedFact, ...]
    sections: tuple[GeneratedSection, ...]


class RenderedArtifact(ContractModel):
    filename: NonBlankString
    media_type: NonBlankString
    content: bytes = Field(repr=False, min_length=1)
    sha256: Sha256String


class StoredArtifact(ContractModel):
    artifact_id: NonBlankString
    filename: NonBlankString
    media_type: NonBlankString
    sha256: Sha256String


class TraceEvent(ContractModel):
    sequence: int = Field(ge=1)
    stage: WorkflowStage
    tool: NonBlankString
    status: TraceStatus
    detail: str | None = Field(default=None, max_length=300)


class GenerationTrace(ContractModel):
    request_id: NonBlankString
    idempotency_key: NonBlankString
    document_purpose: DocumentPurpose
    events: tuple[TraceEvent, ...]
    llm_model_alias: NonBlankString
    embedding_model_alias: NonBlankString


class GenerationRequest(ContractModel):
    request_id: NonBlankString
    idempotency_key: NonBlankString
    document_purpose: DocumentPurpose = DOCUMENT_PURPOSE
    business_type: NonBlankString
    template: TemplateDocument
    sources: tuple[SourceDocument, ...] = Field(min_length=1)
    confirmed_facts: tuple[ConfirmedFact, ...] = ()
    conversation_context: AgentConversationContext = Field(default_factory=AgentConversationContext)
    required_fact_fields: tuple[str, ...] = ()
    section_codes: tuple[str, ...] = Field(min_length=1)
    force_regenerate_section_codes: tuple[str, ...] = ()
    section_revision_instructions: dict[str, str] = Field(default_factory=dict)
    section_revision_conversations: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    section_revision_required_literals: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    section_previous_contents: dict[str, str] = Field(default_factory=dict)
    section_priority_references: dict[str, tuple[RetrievedSection, ...]] = Field(
        default_factory=dict
    )

    @field_validator("required_fact_fields")
    @classmethod
    def validate_required_fields(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_fact_field_name(value) for value in values)

    @field_validator("section_codes")
    @classmethod
    def validate_unique_sections(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("section_codes must be unique")
        return values

    @model_validator(mode="after")
    def purpose_is_consistent(self) -> GenerationRequest:
        if self.template.purpose != self.document_purpose:
            raise ValueError("template purpose does not match the generation purpose")
        if any(source.purpose != self.document_purpose for source in self.sources):
            raise ValueError("source purpose does not match the generation purpose")
        if not set(self.force_regenerate_section_codes).issubset(self.section_codes):
            raise ValueError("force regeneration sections must be requested sections")
        revision_sections = (
            set(self.section_revision_instructions)
            | set(self.section_revision_conversations)
            | set(self.section_revision_required_literals)
            | set(self.section_previous_contents)
            | set(self.section_priority_references)
        )
        if not revision_sections.issubset(self.force_regenerate_section_codes):
            raise ValueError("revision context is only allowed for forced regeneration sections")
        return self


class GenerationResult(ContractModel):
    request_id: NonBlankString
    request_fingerprint: Sha256String
    sections: tuple[GeneratedSection, ...]
    artifact: StoredArtifact
    trace: GenerationTrace


class KnowledgeChunkDraft(ContractModel):
    chunk_id: NonBlankString
    source_document_version_id: int = Field(gt=0)
    business_type: NonBlankString
    client_code: str | None = None
    section_code: NonBlankString
    heading_path: tuple[str, ...]
    paragraph_start: int = Field(ge=0)
    paragraph_end: int = Field(ge=0)
    text: NonBlankString
    component_tags: tuple[str, ...] = ()
    method_tags: tuple[str, ...] = ()
    risk_tags: tuple[str, ...] = ()
    approval_status: Literal["approved"]
    content_sha256: Sha256String

    @model_validator(mode="after")
    def validate_range(self) -> KnowledgeChunkDraft:
        if self.paragraph_end < self.paragraph_start:
            raise ValueError("paragraph_end must be greater than or equal to paragraph_start")
        return self


class KnowledgeChunk(KnowledgeChunkDraft):
    embedding: tuple[float, ...] = Field(min_length=1)
    embedding_model_alias: NonBlankString
    embedding_dimension: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_embedding_dimension(self) -> KnowledgeChunk:
        if len(self.embedding) != self.embedding_dimension:
            raise ValueError("embedding length does not match embedding_dimension")
        return self


class KnowledgeSectionInput(ContractModel):
    source_document_version_id: int = Field(gt=0)
    business_type: NonBlankString
    client_code: str | None = None
    section_code: NonBlankString
    blocks: tuple[ParsedBlock, ...] = Field(min_length=1)
    component_tags: tuple[str, ...] = ()
    method_tags: tuple[str, ...] = ()
    risk_tags: tuple[str, ...] = ()
    approval_status: Literal["approved"]
    document_purpose: DocumentPurpose = DOCUMENT_PURPOSE
