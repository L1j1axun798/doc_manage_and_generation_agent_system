from __future__ import annotations

import ast
from pathlib import Path

import pytest

from apps.document_generation.engine.contracts import (
    GeneratedSection,
    GenerationRequest,
    RiskProfile,
    SectionContext,
    SourceLocator,
    TraceStatus,
    ValidationIssue,
    ValidationSeverity,
)
from apps.document_generation.engine.errors import (
    AgentError,
    IdempotencyConflictError,
    WorkflowExecutionError,
)
from apps.document_generation.engine.fakes import (
    BasicSectionValidator,
    FakeLLMProvider,
)
from apps.document_generation.engine.orchestrator import GenerationOrchestrator
from apps.document_generation.engine.sections import (
    InMemorySectionRepository,
    JsonSectionRepository,
)


def test_fake_pipeline_runs_in_deterministic_tool_order(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    result = orchestrator.run(generation_request)

    assert result.sections[0].title == "工程概况与编制依据"
    assert result.artifact.artifact_id.startswith("memory:")
    assert [event.tool for event in result.trace.events] == [
        "validate_generation_request",
        "parse_source_document",
        "validate_fact_set",
        "build_risk_profile",
        "select_clause_blocks",
        "retrieve_reference_sections",
        "rag_context_ready",
        "build_section_context",
        "draft_document_section",
        "normalize_section_provenance",
        "validate_document_section",
        "render_word_document",
        "publish_document_version",
        "complete_generation",
    ]
    assert all(event.status == TraceStatus.SUCCEEDED for event in result.trace.events)


def test_repeated_execution_is_idempotent(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    first = orchestrator.run(generation_request)
    second = orchestrator.run(generation_request)

    assert first is second

    conflicting = generation_request.model_copy(update={"request_id": "request-002"})
    with pytest.raises(IdempotencyConflictError):
        orchestrator.run(conflicting)


def test_missing_fact_stops_before_risk_and_generation(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    incomplete = generation_request.model_copy(
        update={"confirmed_facts": generation_request.confirmed_facts[:1]}
    )

    with pytest.raises(WorkflowExecutionError) as captured:
        orchestrator.run(incomplete)

    assert captured.value.code == "FACTS_INCOMPLETE"
    tools = [event.tool for event in captured.value.trace.events]
    assert tools[-1] == "validate_fact_set"
    assert "build_risk_profile" not in tools
    assert "draft_document_section" not in tools


def test_nonexistent_confirmed_fact_locator_stops_before_generation(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    invalid_fact = generation_request.confirmed_facts[0].model_copy(
        update={"locator": SourceLocator(paragraph_index=99)}
    )
    invalid_request = generation_request.model_copy(
        update={
            "confirmed_facts": (
                invalid_fact,
                generation_request.confirmed_facts[1],
            )
        }
    )

    with pytest.raises(WorkflowExecutionError) as captured:
        orchestrator.run(invalid_request)

    assert captured.value.code == "FACT_EVIDENCE_INVALID"
    assert captured.value.details == {"fields": ["project_name"]}
    assert captured.value.trace.events[-1].tool == "validate_fact_set"


def test_parser_failure_stops_the_pipeline(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    class FailingParser:
        def parse(self, source):
            raise AgentError("SOURCE_PARSE_FAILED", "fixture parse failure")

    orchestrator.parser = FailingParser()

    with pytest.raises(WorkflowExecutionError) as captured:
        orchestrator.run(generation_request)

    assert captured.value.code == "SOURCE_PARSE_FAILED"
    assert captured.value.trace.events[-1].tool == "parse_source_document"
    assert captured.value.trace.events[-1].status == TraceStatus.FAILED


def test_engine_has_no_django_rq_or_http_client_imports() -> None:
    engine_root = Path(__file__).resolve().parents[1]
    forbidden_roots = {"django", "django_rq", "httpx", "redis", "requests", "rq"}
    found: set[str] = set()

    for path in engine_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".", 1)[0])

    assert found.isdisjoint(forbidden_roots)


def test_basic_validator_rejects_result_language_outside_paragraphs() -> None:
    context = SectionContext(
        section_code="safety_measures",
        objective="编写安全措施",
        confirmed_facts=(),
        risk_profile=RiskProfile(),
    )
    section = GeneratedSection(
        section_code="safety_measures",
        title="安全措施",
        lists=(("检测结果表明设备存在缺陷",),),
    )

    issues = BasicSectionValidator().validate(section, context)

    assert [issue.code for issue in issues] == ["RESULT_CONTENT_FORBIDDEN"]


def test_section_gets_one_controlled_revision_before_failure(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
) -> None:
    class FirstPassValidator:
        calls = 0

        def validate(self, section, context):
            self.calls += 1
            if self.calls == 1:
                return (
                    ValidationIssue(
                        code="UNSOURCED_NUMBER",
                        message="fixture issue",
                        severity=ValidationSeverity.ERROR,
                        section_code=context.section_code,
                    ),
                )
            return ()

    validator = FirstPassValidator()
    orchestrator.section_validator = validator

    result = orchestrator.run(generation_request)

    assert validator.calls == 2
    assert "revise_document_section" in [event.tool for event in result.trace.events]
    assert "revalidate_document_section" in [event.tool for event in result.trace.events]


def test_locked_section_is_reused_without_calling_model_again(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    repository = InMemorySectionRepository()
    orchestrator.section_repository = repository
    first = orchestrator.run(generation_request)
    repository.lock(generation_request.idempotency_key, "overview")
    draft_count = fake_llm_provider.draft_call_count
    resumed = GenerationOrchestrator(
        parser=orchestrator.parser,
        llm_provider=orchestrator.llm_provider,
        risk_profiler=orchestrator.risk_profiler,
        clause_repository=orchestrator.clause_repository,
        retriever=orchestrator.retriever,
        section_validator=orchestrator.section_validator,
        renderer=orchestrator.renderer,
        storage=orchestrator.storage,
        section_repository=repository,
    )

    second = resumed.run(generation_request)

    assert second.sections == first.sections
    assert fake_llm_provider.draft_call_count == draft_count
    assert any(
        event.tool == "reuse_persisted_section" and event.status == TraceStatus.SKIPPED
        for event in second.trace.events
    )


def test_invalid_unlocked_persisted_section_is_regenerated(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    repository = InMemorySectionRepository()
    repository.save(
        generation_request.idempotency_key,
        GeneratedSection(
            section_code="overview",
            title="失效草稿",
            paragraphs=("检测结果表明设备存在缺陷",),
        ),
        (),
    )
    orchestrator.section_repository = repository

    result = orchestrator.run(generation_request)

    assert result.sections[0].title == "工程概况与编制依据"
    assert fake_llm_provider.draft_call_count == 1
    assert any(
        event.tool == "discard_invalid_persisted_section"
        for event in result.trace.events
    )


def test_invalid_locked_persisted_section_fails_without_overwrite(
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    repository = InMemorySectionRepository()
    repository.save(
        generation_request.idempotency_key,
        GeneratedSection(
            section_code="overview",
            title="人工锁定草稿",
            paragraphs=("检测结果表明设备存在缺陷",),
        ),
        (),
    )
    repository.lock(generation_request.idempotency_key, "overview")
    orchestrator.section_repository = repository

    with pytest.raises(WorkflowExecutionError) as error:
        orchestrator.run(generation_request)

    assert error.value.code == "LOCKED_SECTION_VALIDATION_FAILED"
    assert fake_llm_provider.draft_call_count == 0
    assert repository.load(
        generation_request.idempotency_key,
        "overview",
    ).section.title == "人工锁定草稿"


def test_persisted_section_resumes_after_process_restart_and_force_can_replace(
    tmp_path,
    orchestrator: GenerationOrchestrator,
    generation_request: GenerationRequest,
    fake_llm_provider: FakeLLMProvider,
) -> None:
    state_path = tmp_path / "sections.json"
    orchestrator.section_repository = JsonSectionRepository(state_path)
    orchestrator.run(generation_request)
    draft_count = fake_llm_provider.draft_call_count

    resumed = GenerationOrchestrator(
        parser=orchestrator.parser,
        llm_provider=orchestrator.llm_provider,
        risk_profiler=orchestrator.risk_profiler,
        clause_repository=orchestrator.clause_repository,
        retriever=orchestrator.retriever,
        section_validator=orchestrator.section_validator,
        renderer=orchestrator.renderer,
        storage=orchestrator.storage,
        section_repository=JsonSectionRepository(state_path),
    )
    resumed.run(generation_request)

    assert fake_llm_provider.draft_call_count == draft_count

    forced_request = generation_request.model_copy(
        update={
            "force_regenerate_section_codes": generation_request.section_codes,
        }
    )
    forced = GenerationOrchestrator(
        parser=orchestrator.parser,
        llm_provider=orchestrator.llm_provider,
        risk_profiler=orchestrator.risk_profiler,
        clause_repository=orchestrator.clause_repository,
        retriever=orchestrator.retriever,
        section_validator=orchestrator.section_validator,
        renderer=orchestrator.renderer,
        storage=orchestrator.storage,
        section_repository=JsonSectionRepository(state_path),
    )
    forced.run(forced_request)

    assert fake_llm_provider.draft_call_count == draft_count + 1
