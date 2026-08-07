from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from functools import partial
from hashlib import sha256
from typing import TypeVar

from .contracts import (
    AgentConversationContext,
    ClauseSelection,
    ConfirmedFact,
    GeneratedSection,
    GenerationRequest,
    GenerationResult,
    GenerationTrace,
    ParsedDocument,
    RenderRequest,
    RetrievalQuery,
    RetrievalResult,
    RetrievedSection,
    RiskProfile,
    SectionContext,
    TraceEvent,
    TraceStatus,
    ValidationIssue,
    ValidationSeverity,
    WorkflowStage,
)
from .errors import (
    AgentError,
    IdempotencyConflictError,
    WorkflowExecutionError,
)
from .facts import FactEvidenceGate, RequiredFactGate
from .ports import (
    ArtifactStorage,
    ClauseRepository,
    LLMProvider,
    RiskProfiler,
    SectionRepository,
    SectionRetriever,
    SectionValidator,
    SourceParser,
    TemplateRenderer,
)
from .sections import SectionContextBuilder
from .validation import normalize_section_provenance

T = TypeVar("T")
MAX_SECTION_VALIDATION_REVISIONS = 3


class _TraceBuilder:
    def __init__(
        self,
        request: GenerationRequest,
        llm_alias: str,
        embedding_alias: str,
        event_sink: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        self.request = request
        self.llm_alias = llm_alias
        self.embedding_alias = embedding_alias
        self.event_sink = event_sink
        self.events: list[TraceEvent] = []

    def add(
        self,
        stage: WorkflowStage,
        tool: str,
        status: TraceStatus,
        detail: str | None = None,
    ) -> None:
        event = TraceEvent(
            sequence=len(self.events) + 1,
            stage=stage,
            tool=tool,
            status=status,
            detail=detail,
        )
        self.events.append(event)
        if self.event_sink is not None:
            self.event_sink(event)

    def invoke(
        self,
        stage: WorkflowStage,
        tool: str,
        function: Callable[[], T],
        *,
        detail: str | None = None,
    ) -> T:
        if self.event_sink is not None:
            self.event_sink(
                TraceEvent(
                    sequence=len(self.events) + 1,
                    stage=stage,
                    tool=tool,
                    status=TraceStatus.STARTED,
                    detail=detail,
                )
            )
        try:
            result = function()
        except Exception as exc:
            failed_detail = f"{detail}:{type(exc).__name__}" if detail else type(exc).__name__
            self.add(stage, tool, TraceStatus.FAILED, failed_detail)
            raise
        self.add(stage, tool, TraceStatus.SUCCEEDED, detail)
        return result

    def build(self) -> GenerationTrace:
        return GenerationTrace(
            request_id=self.request.request_id,
            idempotency_key=self.request.idempotency_key,
            document_purpose=self.request.document_purpose,
            events=tuple(self.events),
            llm_model_alias=self.llm_alias,
            embedding_model_alias=self.embedding_alias,
        )


class GenerationOrchestrator:
    def __init__(
        self,
        *,
        parser: SourceParser,
        llm_provider: LLMProvider,
        risk_profiler: RiskProfiler,
        clause_repository: ClauseRepository,
        retriever: SectionRetriever,
        section_validator: SectionValidator,
        renderer: TemplateRenderer,
        storage: ArtifactStorage,
        section_repository: SectionRepository | None = None,
        context_builder: SectionContextBuilder | None = None,
        event_sink: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        self.parser = parser
        self.llm_provider = llm_provider
        self.risk_profiler = risk_profiler
        self.clause_repository = clause_repository
        self.retriever = retriever
        self.section_validator = section_validator
        self.renderer = renderer
        self.storage = storage
        self.section_repository = section_repository
        self.context_builder = context_builder or SectionContextBuilder()
        self.event_sink = event_sink
        self.fact_gate = RequiredFactGate()
        self.fact_evidence_gate = FactEvidenceGate()
        self._completed: dict[str, tuple[str, GenerationResult]] = {}

    def run(self, request: GenerationRequest) -> GenerationResult:
        fingerprint = self._fingerprint(request)
        cached = self._completed.get(request.idempotency_key)
        if cached is not None:
            cached_fingerprint, cached_result = cached
            if cached_fingerprint != fingerprint:
                raise IdempotencyConflictError
            return cached_result

        trace = _TraceBuilder(
            request,
            self.llm_provider.model_alias,
            self.retriever.embedding_model_alias,
            self.event_sink,
        )
        trace.add(
            WorkflowStage.INITIALIZED,
            "validate_generation_request",
            TraceStatus.SUCCEEDED,
        )
        try:
            parsed_documents = tuple(
                trace.invoke(
                    WorkflowStage.PARSING,
                    "parse_source_document",
                    partial(self.parser.parse, source),
                )
                for source in request.sources
            )
            confirmed_facts = trace.invoke(
                WorkflowStage.VALIDATING_FACTS,
                "validate_fact_set",
                lambda: self._validate_facts(request, parsed_documents),
            )
            risk_profile = trace.invoke(
                WorkflowStage.BUILDING_RISK_PROFILE,
                "build_risk_profile",
                lambda: self.risk_profiler.build(confirmed_facts),
            )
            generated_sections: list[GeneratedSection] = []
            for section_code in request.section_codes:
                persisted = None
                if self.section_repository is not None:
                    persisted = self.section_repository.load(
                        request.idempotency_key,
                        section_code,
                    )
                clauses = trace.invoke(
                    WorkflowStage.SELECTING_CLAUSES,
                    "select_clause_blocks",
                    partial(self._select_clauses, risk_profile, section_code),
                    detail=section_code,
                )
                query = self._build_query(request, section_code, confirmed_facts)
                retrieval = trace.invoke(
                    WorkflowStage.RETRIEVING_REFERENCES,
                    "retrieve_reference_sections",
                    partial(self.retriever.retrieve, query),
                    detail=section_code,
                )
                trace.add(
                    WorkflowStage.RETRIEVING_REFERENCES,
                    "rag_context_ready",
                    TraceStatus.SUCCEEDED,
                    f"{section_code}:命中{len(retrieval.sections)}段/候选{len(retrieval.trace)}段",
                )
                context = trace.invoke(
                    WorkflowStage.GENERATING_SECTIONS,
                    "build_section_context",
                    partial(
                        self._build_context,
                        section_code,
                        confirmed_facts,
                        risk_profile,
                        clauses,
                        retrieval,
                        conversation_context=request.conversation_context,
                        revision_instruction=request.section_revision_instructions.get(
                            section_code,
                            "",
                        ),
                        revision_conversation=(
                            request.section_revision_conversations.get(
                                section_code,
                                (),
                            )
                        ),
                        revision_required_literals=(
                            request.section_revision_required_literals.get(
                                section_code,
                                (),
                            )
                        ),
                        previous_content=request.section_previous_contents.get(
                            section_code,
                            "",
                        ),
                        priority_references=request.section_priority_references.get(
                            section_code,
                            (),
                        ),
                    ),
                    detail=section_code,
                )
                if (
                    persisted is not None
                    and section_code not in request.force_regenerate_section_codes
                ):
                    reusable_section = persisted.section
                    if not persisted.locked:
                        reusable_section = trace.invoke(
                            WorkflowStage.VALIDATING_SECTIONS,
                            "normalize_persisted_section_provenance",
                            partial(
                                normalize_section_provenance,
                                reusable_section,
                                context,
                            ),
                        )
                    persisted_issues = trace.invoke(
                        WorkflowStage.VALIDATING_SECTIONS,
                        "revalidate_persisted_section",
                        partial(
                            self._validate_section,
                            reusable_section,
                            context,
                        ),
                    )
                    persisted_blocking_issues = tuple(
                        issue
                        for issue in persisted_issues
                        if issue.severity == ValidationSeverity.ERROR
                    )
                    if not persisted_blocking_issues:
                        if (
                            not persisted.locked
                            and self.section_repository is not None
                            and (
                                reusable_section != persisted.section
                                or tuple(persisted_issues) != persisted.validation_issues
                            )
                        ):
                            trace.invoke(
                                WorkflowStage.GENERATING_SECTIONS,
                                "persist_revalidated_section",
                                partial(
                                    self.section_repository.save,
                                    request.idempotency_key,
                                    reusable_section,
                                    persisted_issues,
                                ),
                            )
                        trace.add(
                            WorkflowStage.GENERATING_SECTIONS,
                            "reuse_persisted_section",
                            TraceStatus.SKIPPED,
                            section_code,
                        )
                        generated_sections.append(reusable_section)
                        continue
                    if persisted.locked:
                        raise AgentError(
                            "LOCKED_SECTION_VALIDATION_FAILED",
                            f"已锁定章节 {section_code} 不再满足当前确定性校验",
                            details={
                                "section_code": section_code,
                                "issues": [
                                    issue.model_dump(mode="json")
                                    for issue in persisted_blocking_issues
                                ],
                            },
                        )
                    trace.add(
                        WorkflowStage.GENERATING_SECTIONS,
                        "discard_invalid_persisted_section",
                        TraceStatus.SKIPPED,
                        section_code,
                    )
                section = trace.invoke(
                    WorkflowStage.GENERATING_SECTIONS,
                    "draft_document_section",
                    partial(self.llm_provider.draft_section, context),
                    detail=section_code,
                )
                section = trace.invoke(
                    WorkflowStage.VALIDATING_SECTIONS,
                    "normalize_section_provenance",
                    partial(normalize_section_provenance, section, context),
                    detail=section_code,
                )
                issues = trace.invoke(
                    WorkflowStage.VALIDATING_SECTIONS,
                    "validate_document_section",
                    partial(self._validate_section, section, context),
                    detail=section_code,
                )
                blocking_issues = tuple(
                    issue for issue in issues if issue.severity == ValidationSeverity.ERROR
                )
                revision_attempt = 0
                while blocking_issues and revision_attempt < MAX_SECTION_VALIDATION_REVISIONS:
                    revision_attempt += 1
                    section = trace.invoke(
                        WorkflowStage.GENERATING_SECTIONS,
                        "revise_document_section",
                        partial(
                            self.llm_provider.revise_section,
                            context,
                            section,
                            blocking_issues,
                        ),
                        detail=f"{section_code}:attempt={revision_attempt}",
                    )
                    section = trace.invoke(
                        WorkflowStage.VALIDATING_SECTIONS,
                        "normalize_revised_section_provenance",
                        partial(normalize_section_provenance, section, context),
                        detail=f"{section_code}:attempt={revision_attempt}",
                    )
                    issues = trace.invoke(
                        WorkflowStage.VALIDATING_SECTIONS,
                        "revalidate_document_section",
                        partial(self._validate_section, section, context),
                        detail=f"{section_code}:attempt={revision_attempt}",
                    )
                    blocking_issues = tuple(
                        issue for issue in issues if issue.severity == ValidationSeverity.ERROR
                    )
                if blocking_issues:
                    raise AgentError(
                        "VALIDATION_FAILED",
                        f"章节 {section_code} 未通过确定性校验",
                        details={
                            "section_code": section_code,
                            "issues": [issue.model_dump(mode="json") for issue in blocking_issues],
                        },
                    )
                if self.section_repository is not None:
                    trace.invoke(
                        WorkflowStage.GENERATING_SECTIONS,
                        "persist_generated_section",
                        partial(
                            self.section_repository.save,
                            request.idempotency_key,
                            section,
                            issues,
                        ),
                        detail=section_code,
                    )
                generated_sections.append(section)
            artifact = trace.invoke(
                WorkflowStage.RENDERING,
                "render_word_document",
                lambda: self.renderer.render(
                    RenderRequest(
                        template=request.template,
                        facts=confirmed_facts,
                        sections=tuple(generated_sections),
                    )
                ),
            )
            stored_artifact = trace.invoke(
                WorkflowStage.STORING,
                "publish_document_version",
                lambda: self.storage.save(artifact),
            )
            trace.add(WorkflowStage.COMPLETED, "complete_generation", TraceStatus.SUCCEEDED)
        except Exception as exc:
            cause = (
                exc
                if isinstance(exc, AgentError)
                else AgentError(
                    "WORKFLOW_FAILED",
                    "生成流水线执行失败",
                    details={"exception_type": type(exc).__name__},
                )
            )
            if not trace.events or trace.events[-1].status != TraceStatus.FAILED:
                trace.add(
                    WorkflowStage.FAILED,
                    "stop_workflow",
                    TraceStatus.FAILED,
                    cause.code,
                )
            raise WorkflowExecutionError(cause, trace.build()) from exc

        result = GenerationResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            sections=tuple(generated_sections),
            artifact=stored_artifact,
            trace=trace.build(),
        )
        self._completed[request.idempotency_key] = (fingerprint, result)
        return result

    def _validate_facts(
        self,
        request: GenerationRequest,
        parsed_documents: Sequence[ParsedDocument],
    ) -> tuple[ConfirmedFact, ...]:
        confirmed = self.fact_gate.validate(
            request.confirmed_facts,
            required_fields=request.required_fact_fields,
        )
        return self.fact_evidence_gate.validate(
            confirmed,
            documents=parsed_documents,
        )

    def _build_context(
        self,
        section_code: str,
        confirmed_facts: tuple[ConfirmedFact, ...],
        risk_profile: RiskProfile,
        clauses: tuple[ClauseSelection, ...],
        retrieval: RetrievalResult,
        *,
        conversation_context: AgentConversationContext | None = None,
        revision_instruction: str = "",
        revision_conversation: tuple[str, ...] = (),
        revision_required_literals: tuple[str, ...] = (),
        previous_content: str = "",
        priority_references: tuple[RetrievedSection, ...] = (),
    ) -> SectionContext:
        return self.context_builder.build(
            section_code=section_code,
            confirmed_facts=confirmed_facts,
            risk_profile=risk_profile,
            clauses=clauses,
            retrieval=retrieval,
            conversation_context=conversation_context,
            revision_instruction=revision_instruction,
            revision_conversation=revision_conversation,
            revision_required_literals=revision_required_literals,
            previous_content=previous_content,
            priority_references=priority_references,
        )

    def _select_clauses(
        self,
        risk_profile: RiskProfile,
        section_code: str,
    ) -> tuple[ClauseSelection, ...]:
        return tuple(self.clause_repository.select(risk_profile, section_code))

    def _validate_section(
        self,
        section: GeneratedSection,
        context: SectionContext,
    ) -> tuple[ValidationIssue, ...]:
        return tuple(self.section_validator.validate(section, context))

    @staticmethod
    def _build_query(
        request: GenerationRequest,
        section_code: str,
        facts: Sequence[ConfirmedFact],
    ) -> RetrievalQuery:
        fact_text = " ".join(f"{fact.field} {fact.value}" for fact in facts)
        values = {fact.field: fact.value for fact in facts}
        component_tags = values.get("inspection_component_codes")
        method_tags = values.get("inspection_method_codes")
        risk_items = values.get("risk_evidence_items")
        risk_tags = (
            tuple(
                str(item["risk_code"])
                for item in risk_items
                if isinstance(item, dict) and item.get("risk_code")
            )
            if isinstance(risk_items, list)
            else ()
        )
        return RetrievalQuery(
            business_type=request.business_type,
            section_code=section_code,
            query_text=(
                f"{section_code} {request.conversation_context.initial_message} {fact_text}"
            ).strip(),
            client_code=(str(values["client_code"]).strip() if values.get("client_code") else None),
            component_tags=(
                tuple(str(value) for value in component_tags)
                if isinstance(component_tags, list)
                else ()
            ),
            method_tags=(
                tuple(str(value) for value in method_tags) if isinstance(method_tags, list) else ()
            ),
            risk_tags=risk_tags,
        )

    @staticmethod
    def _fingerprint(request: GenerationRequest) -> str:
        payload = {
            "request_id": request.request_id,
            "document_purpose": request.document_purpose,
            "business_type": request.business_type,
            "template": {
                "template_id": request.template.template_id,
                "sha256": sha256(request.template.content).hexdigest(),
            },
            "sources": [
                {
                    "document_version_id": source.document_version_id,
                    "filename": source.filename,
                    "mime_type": source.mime_type,
                    "sha256": sha256(source.content).hexdigest(),
                }
                for source in request.sources
            ],
            "confirmed_facts": [fact.model_dump(mode="json") for fact in request.confirmed_facts],
            "conversation_context": request.conversation_context.model_dump(mode="json"),
            "required_fact_fields": request.required_fact_fields,
            "section_codes": request.section_codes,
            "force_regenerate_section_codes": request.force_regenerate_section_codes,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()
