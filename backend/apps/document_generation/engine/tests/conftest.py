from __future__ import annotations

import pytest

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    GenerationRequest,
    SourceDocument,
    SourceLocator,
    TemplateDocument,
)
from apps.document_generation.engine.fakes import (
    BasicSectionValidator,
    EmptySectionRetriever,
    FakeLLMProvider,
    FakeRiskProfiler,
    FakeSourceParser,
    FakeTemplateRenderer,
    InMemoryArtifactStorage,
    StaticClauseRepository,
)
from apps.document_generation.engine.orchestrator import GenerationOrchestrator


@pytest.fixture
def generation_request() -> GenerationRequest:
    locator = SourceLocator(
        paragraph_index=0,
        text_quote="计划开展风电机组入场检测",
    )
    return GenerationRequest(
        request_id="request-001",
        idempotency_key="idem-001",
        business_type="wind_turbine_inspection_four_measures_two_plans",
        template=TemplateDocument(
            template_id="template-001",
            filename="entry-plan-template.docx",
            content=b"fake-template",
        ),
        sources=(
            SourceDocument(
                document_version_id=101,
                filename="task-notice.txt",
                mime_type="text/plain",
                content="计划开展风电机组入场检测".encode(),
            ),
        ),
        confirmed_facts=(
            ConfirmedFact(
                field="project_name",
                value="示例入场项目",
                value_type="string",
                source_document_version_id=101,
                locator=locator,
                confidence=1,
                confirmed_by=7,
            ),
            ConfirmedFact(
                field="planned_inspection_quantity",
                value=12,
                value_type="integer",
                source_document_version_id=101,
                locator=locator,
                confidence=1,
                confirmed_by=7,
            ),
        ),
        required_fact_fields=("project_name", "planned_inspection_quantity"),
        section_codes=("overview",),
    )


@pytest.fixture
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider(section_titles={"overview": "工程概况"})


@pytest.fixture
def orchestrator(fake_llm_provider: FakeLLMProvider) -> GenerationOrchestrator:
    return GenerationOrchestrator(
        parser=FakeSourceParser(),
        llm_provider=fake_llm_provider,
        risk_profiler=FakeRiskProfiler(),
        clause_repository=StaticClauseRepository(),
        retriever=EmptySectionRetriever(),
        section_validator=BasicSectionValidator(),
        renderer=FakeTemplateRenderer(),
        storage=InMemoryArtifactStorage(),
    )
