from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256

import pytest
from pydantic import ValidationError

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    KnowledgeChunk,
    KnowledgeSectionInput,
    ParsedBlock,
    ParsedBlockType,
    RetrievalQuery,
    SourceLocator,
)
from apps.document_generation.engine.errors import SourcePurposeMismatchError
from apps.document_generation.engine.rag import (
    HistoricalEntityBlacklist,
    InMemoryKnowledgeRepository,
    JsonKnowledgeRepository,
    KnowledgeIndexer,
    RagRetriever,
    SectionChunker,
    _cosine_similarity,
    calculate_hit_at_k,
)


class MappingEmbeddingProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors

    @property
    def model_alias(self) -> str:
        return "mapping-v1"

    @property
    def dimension(self) -> int:
        return 2

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return tuple(self.vectors[text] for text in texts)


def test_cosine_similarity_clamps_floating_point_overflow() -> None:
    vector = (1 / 3**0.5,) * 3

    assert _cosine_similarity(vector, vector) == 1.0


def _paragraph(
    block_id: str,
    text: str,
    paragraph_index: int,
    heading_path: tuple[str, ...] = ("四、安全措施",),
) -> ParsedBlock:
    return ParsedBlock(
        block_id=block_id,
        block_type=ParsedBlockType.PARAGRAPH,
        text=text,
        heading_path=heading_path,
        locator=SourceLocator(
            heading_path=heading_path,
            paragraph_index=paragraph_index,
        ),
    )


def _section(
    *,
    version_id: int = 1,
    business_type: str = "business-a",
    section_code: str = "safety_measures",
    blocks: tuple[ParsedBlock, ...] | None = None,
) -> KnowledgeSectionInput:
    return KnowledgeSectionInput(
        source_document_version_id=version_id,
        business_type=business_type,
        client_code="CLIENT-A",
        section_code=section_code,
        blocks=blocks
        or (
            _paragraph("p1", "高处作业前核验安全带并完成安全交底。", 1),
            _paragraph("p2", "人员进入塔筒前确认通信和监护安排。", 2),
        ),
        component_tags=("tower",),
        method_tags=("ultrasonic",),
        risk_tags=("high_altitude",),
        approval_status="approved",
    )


def _chunk(
    *,
    chunk_id: str,
    version_id: int,
    text: str,
    vector: tuple[float, float],
    business_type: str = "business-a",
    section_code: str = "safety_measures",
    client_code: str | None = None,
    component_tags: tuple[str, ...] = (),
    method_tags: tuple[str, ...] = (),
    risk_tags: tuple[str, ...] = (),
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        source_document_version_id=version_id,
        business_type=business_type,
        client_code=client_code,
        section_code=section_code,
        heading_path=("四、安全措施",),
        paragraph_start=1,
        paragraph_end=2,
        text=text,
        component_tags=component_tags,
        method_tags=method_tags,
        risk_tags=risk_tags,
        approval_status="approved",
        content_sha256=sha256(text.encode()).hexdigest(),
        embedding=vector,
        embedding_model_alias="mapping-v1",
        embedding_dimension=2,
    )


def test_chunker_splits_by_section_and_repeats_table_header() -> None:
    rows = (("风险", "控制措施"),) + tuple(
        (f"风险{i}", "进入现场前完成检查和确认" * 3) for i in range(10)
    )
    table = ParsedBlock(
        block_id="table-1",
        block_type=ParsedBlockType.TABLE,
        text="\n".join(" | ".join(row) for row in rows),
        heading_path=("四、安全措施", "风险表"),
        locator=SourceLocator(heading_path=("四、安全措施", "风险表"), table_index=0),
        rows=rows,
    )
    chunker = SectionChunker(min_chars=50, max_chars=160, overlap_chars=20)

    chunks = chunker.chunk(_section(blocks=(table,)))

    assert len(chunks) > 1
    assert all(chunk.text.startswith("风险 | 控制措施") for chunk in chunks)
    assert all(len(chunk.text) <= 160 for chunk in chunks)
    assert all(chunk.section_code == "safety_measures" for chunk in chunks)
    assert all(chunk.heading_path == ("四、安全措施", "风险表") for chunk in chunks)
    assert all(chunk.block_type == "table" for chunk in chunks)
    assert all(chunk.structured_rows[0] == ("风险", "控制措施") for chunk in chunks)


def test_chunker_uses_section_code_when_source_has_no_heading() -> None:
    paragraph = _paragraph(
        "p1",
        "进入现场前完成安全确认。",
        1,
        heading_path=(),
    )

    chunks = SectionChunker().chunk(_section(blocks=(paragraph,)))

    assert chunks[0].heading_path == ("safety_measures",)


def test_chunker_applies_overlap_when_a_heading_group_spans_chunks() -> None:
    blocks = tuple(_paragraph(f"p{index}", str(index) * 90, index) for index in range(1, 4))

    chunks = SectionChunker(
        min_chars=80,
        max_chars=160,
        overlap_chars=20,
    ).chunk(_section(blocks=blocks))

    assert len(chunks) >= 2
    for left, right in zip(chunks, chunks[1:], strict=False):
        overlap = max(
            length for length in range(1, 21) if left.text[-length:] == right.text[:length]
        )
        assert overlap >= 19
    assert all(80 <= len(chunk.text) <= 160 for chunk in chunks)
    assert chunks[1].paragraph_start == 1
    assert chunks[1].paragraph_end == 2


def test_chunker_splits_oversized_table_rows_and_repeats_header() -> None:
    table = ParsedBlock(
        block_id="table-long-row",
        block_type=ParsedBlockType.TABLE,
        text="风险 | 控制措施\n高处 | " + "进入现场前确认" * 40,
        heading_path=("四、安全措施", "风险表"),
        locator=SourceLocator(
            heading_path=("四、安全措施", "风险表"),
            table_index=0,
        ),
        rows=(("风险", "控制措施"), ("高处", "进入现场前确认" * 40)),
    )

    chunks = SectionChunker(
        min_chars=50,
        max_chars=120,
        overlap_chars=20,
    ).chunk(_section(blocks=(table,)))

    assert len(chunks) > 1
    assert all(chunk.text.startswith("风险 | 控制措施\n") for chunk in chunks)
    assert all(len(chunk.text) <= 120 for chunk in chunks)


def test_indexer_deduplicates_same_chunk_and_json_repository_round_trips(
    tmp_path,
    monkeypatch,
) -> None:
    text_a = "高处作业前核验安全带并完成安全交底。"
    text_b = "人员进入塔筒前确认通信和监护安排。"
    provider = MappingEmbeddingProvider({f"{text_a}\n{text_b}": (1.0, 0.0)})
    path = tmp_path / "knowledge.json"
    repository = JsonKnowledgeRepository(path)
    indexer = KnowledgeIndexer(
        chunker=SectionChunker(),
        embedding_provider=provider,
        repository=repository,
    )

    first = indexer.index(_section())
    second = indexer.index(_section())
    monkeypatch.setattr(
        JsonKnowledgeRepository,
        "_persist",
        lambda self: pytest.fail("loading an existing repository must not rewrite it"),
    )
    reloaded = JsonKnowledgeRepository(path)

    assert first == second
    assert len(repository.all()) == 1
    assert reloaded.all() == repository.all()


def test_unapproved_knowledge_section_is_rejected_by_contract() -> None:
    payload = _section().model_dump()
    payload["approval_status"] = "pending"

    with pytest.raises(ValidationError, match="approved"):
        KnowledgeSectionInput.model_validate(payload)


def test_report_result_content_never_enters_index() -> None:
    blocks = (_paragraph("p1", "检测结论为需要返修。", 1),)

    with pytest.raises(SourcePurposeMismatchError):
        SectionChunker().chunk(_section(blocks=blocks))


def test_metadata_filter_and_weighted_score_put_relevant_chunk_first() -> None:
    relevant = _chunk(
        chunk_id="relevant",
        version_id=1,
        text="匹配风险和方法",
        vector=(0.8, 0.6),
        client_code="CLIENT-A",
        component_tags=("tower",),
        method_tags=("ultrasonic",),
        risk_tags=("high_altitude",),
    )
    vector_only = _chunk(
        chunk_id="vector-only",
        version_id=2,
        text="仅向量相似",
        vector=(0.95, 0.31),
    )
    wrong_business = _chunk(
        chunk_id="wrong-business",
        version_id=3,
        text="错误业务",
        vector=(1.0, 0.0),
        business_type="business-b",
    )
    provider = MappingEmbeddingProvider({"高处塔筒超声检测": (1.0, 0.0)})
    repository = InMemoryKnowledgeRepository((relevant, vector_only, wrong_business))
    retriever = RagRetriever(repository=repository, embedding_provider=provider)

    result = retriever.retrieve(
        RetrievalQuery(
            business_type="business-a",
            section_code="safety_measures",
            query_text="高处塔筒超声检测",
            client_code="CLIENT-A",
            component_tags=("tower",),
            method_tags=("ultrasonic",),
            risk_tags=("high_altitude",),
        )
    )

    assert [section.chunk_id for section in result.sections] == [
        "relevant",
        "vector-only",
    ]
    assert all(item.chunk_id != "wrong-business" for item in result.trace)
    assert result.trace[0].selected is True
    assert result.sections[0].source_document_version_id == 1
    assert result.sections[0].heading_path == ("四、安全措施",)


def test_low_similarity_returns_empty_result_with_trace() -> None:
    chunk = _chunk(
        chunk_id="orthogonal",
        version_id=1,
        text="完全不相关",
        vector=(0.0, 1.0),
    )
    provider = MappingEmbeddingProvider({"查询": (1.0, 0.0)})
    retriever = RagRetriever(
        repository=InMemoryKnowledgeRepository((chunk,)),
        embedding_provider=provider,
    )

    result = retriever.retrieve(
        RetrievalQuery(
            business_type="business-a",
            section_code="safety_measures",
            query_text="查询",
            min_similarity=0.2,
        )
    )

    assert result.sections == ()
    assert result.trace[0].rejection_reason == "below_similarity"


def test_hit_at_3_and_historical_entity_blacklist() -> None:
    chunk = _chunk(
        chunk_id="relevant",
        version_id=1,
        text="匹配内容",
        vector=(1.0, 0.0),
    )
    provider = MappingEmbeddingProvider({"查询": (1.0, 0.0)})
    retriever = RagRetriever(
        repository=InMemoryKnowledgeRepository((chunk,)),
        embedding_provider=provider,
    )
    query = RetrievalQuery(
        business_type="business-a",
        section_code="safety_measures",
        query_text="查询",
    )
    result = retriever.retrieve(query)
    cases = [(result, {"relevant"}) for _ in range(5)]
    facts = (
        ConfirmedFact(
            field="project_name",
            value="历史项目A",
            value_type="string",
            source_document_version_id=1,
            locator=SourceLocator(paragraph_index=1),
            confidence=1,
            confirmed_by=1,
        ),
        ConfirmedFact(
            field="client_name",
            value="当前甲方",
            value_type="string",
            source_document_version_id=1,
            locator=SourceLocator(paragraph_index=2),
            confidence=1,
            confirmed_by=1,
        ),
    )

    blacklist = HistoricalEntityBlacklist().extract(
        facts,
        current_entities=("当前甲方",),
    )

    assert calculate_hit_at_k(cases) == 1.0
    assert blacklist == frozenset({"历史项目A"})
