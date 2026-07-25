from __future__ import annotations

from apps.document_generation.engine.contracts import GeneratedSection, SectionContext
from apps.document_generation.engine.fakes import HashingEmbeddingProvider
from apps.document_generation.providers.health import check_providers


class _ProbeLLM:
    model_alias = "probe-llm"

    def extract_facts(self, documents):
        return ()

    def draft_section(self, context: SectionContext) -> GeneratedSection:
        return GeneratedSection(
            section_code=context.section_code,
            title="健康检查",
        )

    def repair_structured_output(self, raw_output: str) -> GeneratedSection:
        raise NotImplementedError


def test_provider_healthcheck_validates_both_provider_contracts() -> None:
    embedding = HashingEmbeddingProvider(dimension=16, model_alias="probe-embedding")

    result = check_providers(
        llm_provider=_ProbeLLM(),
        embedding_provider=embedding,
    )

    assert result["llm_model"] == "probe-llm"
    assert result["embedding_model"] == "probe-embedding"
    assert result["embedding_dimension"] == 16
