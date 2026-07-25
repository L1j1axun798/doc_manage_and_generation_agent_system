from __future__ import annotations

from time import monotonic

from ..engine.contracts import RiskProfile, SectionContext
from ..engine.ports import EmbeddingProvider, LLMProvider


def check_providers(
    *,
    llm_provider: LLMProvider,
    embedding_provider: EmbeddingProvider,
) -> dict[str, object]:
    started = monotonic()
    vectors = embedding_provider.embed(("风电机组检测四措两案入场计划",))
    if len(vectors) != 1 or len(vectors[0]) != embedding_provider.dimension:
        raise ValueError("Embedding健康检查返回维度不一致")
    section = llm_provider.draft_section(
        SectionContext(
            section_code="overview",
            objective="模型连通性检查：仅生成不含项目事实的入场计划章节结构",
            confirmed_facts=(),
            risk_profile=RiskProfile(),
        )
    )
    if section.section_code != "overview":
        raise ValueError("LLM健康检查返回章节编码不一致")
    return {
        "llm_model": llm_provider.model_alias,
        "embedding_model": embedding_provider.model_alias,
        "embedding_dimension": embedding_provider.dimension,
        "elapsed_seconds": round(monotonic() - started, 3),
    }
