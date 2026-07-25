from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final

import numpy as np

from .contracts import (
    ConfirmedFact,
    KnowledgeChunk,
    KnowledgeChunkDraft,
    KnowledgeSectionInput,
    ParsedBlock,
    ParsedBlockType,
    RetrievalQuery,
    RetrievalResult,
    RetrievalTraceItem,
    RetrievedSection,
)
from .errors import AgentError, SourcePurposeMismatchError
from .parsing import contains_result_content
from .ports import EmbeddingProvider

DEFAULT_MAX_CHARS: Final = 1000
DEFAULT_MIN_CHARS: Final = 400
DEFAULT_OVERLAP_CHARS: Final = 100
MAX_VECTOR_CANDIDATES: Final = 8
MAX_CHUNKS_PER_SOURCE: Final = 2


def _clean_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _split_ranges(
    text: str,
    *,
    min_chars: int,
    max_chars: int,
    overlap_chars: int,
) -> list[tuple[int, int]]:
    if len(text) <= max_chars:
        return [(0, len(text))]
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            latest_end_for_minimum_tail = len(text) + overlap_chars - min_chars
            if start + min_chars < latest_end_for_minimum_tail < end:
                end = latest_end_for_minimum_tail
            boundary = max(
                text.rfind("。", start, end),
                text.rfind("；", start, end),
                text.rfind("\n", start, end),
            )
            if boundary >= start + min_chars:
                end = boundary + 1
        ranges.append((start, end))
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return ranges


def _split_text(
    text: str,
    *,
    min_chars: int,
    max_chars: int,
    overlap_chars: int,
) -> list[str]:
    return [
        text[start:end].strip()
        for start, end in _split_ranges(
            text,
            min_chars=min_chars,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )
        if text[start:end].strip()
    ]


def _table_pieces(block: ParsedBlock, max_chars: int) -> list[str]:
    header = " | ".join(block.rows[0])
    if len(header) > max_chars:
        raise AgentError("KNOWLEDGE_TABLE_HEADER_TOO_LONG", "表格表头超过单个Chunk上限")
    if len(block.rows) == 1:
        return [header]
    if len(header) >= max_chars:
        raise AgentError("KNOWLEDGE_TABLE_HEADER_TOO_LONG", "表格表头没有为数据行预留空间")
    pieces: list[str] = []
    current = [header]
    current_length = len(header)
    for row in block.rows[1:]:
        row_text = " | ".join(row)
        added_length = len(row_text) + 1
        if len(header) + added_length > max_chars:
            if len(current) > 1:
                pieces.append("\n".join(current))
                current = [header]
                current_length = len(header)
            row_capacity = max_chars - len(header) - 1
            pieces.extend(
                f"{header}\n{segment}"
                for segment in _split_text(
                    row_text,
                    min_chars=min(row_capacity, max(1, row_capacity // 2)),
                    max_chars=row_capacity,
                    overlap_chars=0,
                )
            )
            continue
        if len(current) > 1 and current_length + added_length > max_chars:
            pieces.append("\n".join(current))
            current = [header]
            current_length = len(header)
        current.append(row_text)
        current_length += added_length
    if len(current) > 1:
        pieces.append("\n".join(current))
    return pieces


@dataclass(frozen=True)
class _Piece:
    text: str
    paragraph_start: int
    paragraph_end: int
    heading_path: tuple[str, ...]
    atomic: bool = False


class SectionChunker:
    def __init__(
        self,
        *,
        min_chars: int = DEFAULT_MIN_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> None:
        if min_chars <= 0 or max_chars < min_chars:
            raise ValueError("chunk size configuration is invalid")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be between zero and max_chars")
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk(self, section: KnowledgeSectionInput) -> tuple[KnowledgeChunkDraft, ...]:
        pieces = self._pieces(section.blocks)
        if not pieces:
            raise AgentError("KNOWLEDGE_SECTION_EMPTY", "审核章节没有可索引正文")
        combined = "\n".join(piece.text for piece in pieces)
        if contains_result_content(combined):
            raise SourcePurposeMismatchError("完工结果或检测结论不得进入四措两案知识库")

        grouped: list[list[_Piece]] = []
        for piece in pieces:
            if (
                piece.atomic
                or not grouped
                or grouped[-1][-1].atomic
                or grouped[-1][-1].heading_path != piece.heading_path
            ):
                grouped.append([piece])
            else:
                grouped[-1].append(piece)

        drafts: list[KnowledgeChunkDraft] = []
        seen_hashes: set[str] = set()
        for group in grouped:
            for text, start, end, heading_path in self._combine_group(group):
                content_hash = sha256(text.encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)
                drafts.append(
                    KnowledgeChunkDraft(
                        chunk_id=(
                            f"dv{section.source_document_version_id}:"
                            f"{section.section_code}:{content_hash[:16]}"
                        ),
                        source_document_version_id=section.source_document_version_id,
                        business_type=section.business_type,
                        client_code=section.client_code,
                        section_code=section.section_code,
                        heading_path=heading_path or (section.section_code,),
                        paragraph_start=start,
                        paragraph_end=end,
                        text=text,
                        component_tags=tuple(sorted(set(section.component_tags))),
                        method_tags=tuple(sorted(set(section.method_tags))),
                        risk_tags=tuple(sorted(set(section.risk_tags))),
                        approval_status="approved",
                        content_sha256=content_hash,
                    )
                )
        return tuple(drafts)

    def _pieces(self, blocks: Sequence[ParsedBlock]) -> list[_Piece]:
        pieces: list[_Piece] = []
        for index, block in enumerate(blocks):
            if block.block_type == ParsedBlockType.HEADING:
                continue
            if block.block_type == ParsedBlockType.TABLE:
                texts = _table_pieces(block, self.max_chars)
                atomic = True
            else:
                cleaned = _clean_text(block.text)
                texts = _split_text(
                    cleaned,
                    min_chars=self.min_chars,
                    max_chars=self.max_chars,
                    overlap_chars=self.overlap_chars,
                )
                atomic = len(texts) > 1
            paragraph_index = (
                block.locator.paragraph_index
                if block.locator.paragraph_index is not None
                else index
            )
            for text in texts:
                cleaned_text = _clean_text(text)
                if cleaned_text:
                    pieces.append(
                        _Piece(
                            text=cleaned_text,
                            paragraph_start=paragraph_index,
                            paragraph_end=paragraph_index,
                            heading_path=block.heading_path,
                            atomic=atomic,
                        )
                    )
        return pieces

    def _combine_group(
        self,
        pieces: Sequence[_Piece],
    ) -> Iterable[tuple[str, int, int, tuple[str, ...]]]:
        text = "\n".join(piece.text for piece in pieces)
        spans: list[tuple[int, int, _Piece]] = []
        offset = 0
        for piece in pieces:
            spans.append((offset, offset + len(piece.text), piece))
            offset += len(piece.text) + 1
        for start, end in _split_ranges(
            text,
            min_chars=self.min_chars,
            max_chars=self.max_chars,
            overlap_chars=0 if pieces[0].atomic else self.overlap_chars,
        ):
            intersecting = [
                piece
                for piece_start, piece_end, piece in spans
                if piece_end > start and piece_start < end
            ]
            if not intersecting:
                continue
            chunk_text = text[start:end].strip()
            if chunk_text:
                yield (
                    chunk_text,
                    min(piece.paragraph_start for piece in intersecting),
                    max(piece.paragraph_end for piece in intersecting),
                    pieces[0].heading_path,
                )


class InMemoryKnowledgeRepository:
    def __init__(self, chunks: Sequence[KnowledgeChunk] = ()) -> None:
        self._chunks_by_hash: dict[str, KnowledgeChunk] = {}
        InMemoryKnowledgeRepository.add(self, chunks)

    def add(self, chunks: Sequence[KnowledgeChunk]) -> int:
        added = 0
        for chunk in chunks:
            if chunk.content_sha256 in self._chunks_by_hash:
                continue
            self._chunks_by_hash[chunk.content_sha256] = chunk
            added += 1
        return added

    def candidates(self, query: RetrievalQuery) -> Sequence[KnowledgeChunk]:
        return tuple(
            chunk
            for chunk in self._chunks_by_hash.values()
            if chunk.business_type == query.business_type
            and chunk.section_code == query.section_code
            and chunk.approval_status == "approved"
        )

    def all(self) -> tuple[KnowledgeChunk, ...]:
        return tuple(self._chunks_by_hash.values())


class JsonKnowledgeRepository(InMemoryKnowledgeRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        chunks: tuple[KnowledgeChunk, ...] = ()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            chunks = tuple(KnowledgeChunk.model_validate(item) for item in payload)
        super().__init__(chunks)

    def add(self, chunks: Sequence[KnowledgeChunk]) -> int:
        added = super().add(chunks)
        if added:
            self._persist()
        return added

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = [chunk.model_dump(mode="json") for chunk in self.all()]
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)


class KnowledgeIndexer:
    def __init__(
        self,
        *,
        chunker: SectionChunker,
        embedding_provider: EmbeddingProvider,
        repository: InMemoryKnowledgeRepository,
    ) -> None:
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.repository = repository

    def index(self, section: KnowledgeSectionInput) -> tuple[KnowledgeChunk, ...]:
        drafts = self.chunker.chunk(section)
        vectors = tuple(self.embedding_provider.embed([draft.text for draft in drafts]))
        if len(vectors) != len(drafts):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding返回数量不一致")
        chunks: list[KnowledgeChunk] = []
        for draft, vector in zip(drafts, vectors, strict=True):
            if len(vector) != self.embedding_provider.dimension:
                raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding向量维度不一致")
            chunks.append(
                KnowledgeChunk(
                    **draft.model_dump(),
                    embedding=tuple(float(value) for value in vector),
                    embedding_model_alias=self.embedding_provider.model_alias,
                    embedding_dimension=self.embedding_provider.dimension,
                )
            )
        self.repository.add(chunks)
        return tuple(chunks)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    if left_array.shape != right_array.shape:
        raise AgentError("EMBEDDING_DIMENSION_MISMATCH", "检索向量维度不一致")
    denominator = float(np.linalg.norm(left_array) * np.linalg.norm(right_array))
    if denominator == 0:
        return 0.0
    similarity = float(np.dot(left_array, right_array) / denominator)
    return max(-1.0, min(1.0, similarity))


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


@dataclass(frozen=True)
class _ScoredChunk:
    chunk: KnowledgeChunk
    similarity: float
    tag_score: float
    method_score: float
    client_score: float
    final_score: float


class RagRetriever:
    def __init__(
        self,
        *,
        repository: InMemoryKnowledgeRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider

    @property
    def embedding_model_alias(self) -> str:
        return self.embedding_provider.model_alias

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        candidates = tuple(self.repository.candidates(query))
        if not candidates:
            return self._empty_result(query)
        query_vectors = self.embedding_provider.embed([query.query_text])
        if len(query_vectors) != 1:
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "查询Embedding返回数量不正确")
        query_vector = query_vectors[0]

        scored = [self._score(query, query_vector, chunk) for chunk in candidates]
        scored.sort(
            key=lambda item: (item.final_score, item.similarity, item.chunk.chunk_id),
            reverse=True,
        )
        eligible = [item for item in scored if item.similarity >= query.min_similarity]
        candidate_pool = eligible[:MAX_VECTOR_CANDIDATES]
        selected: list[_ScoredChunk] = []
        source_counts: Counter[int] = Counter()
        rejection_reasons: dict[str, str] = {}
        for item in candidate_pool:
            source_id = item.chunk.source_document_version_id
            if source_counts[source_id] >= MAX_CHUNKS_PER_SOURCE:
                rejection_reasons[item.chunk.chunk_id] = "source_diversity"
                continue
            if any(
                selected_item.chunk.source_document_version_id == source_id
                and _cosine_similarity(
                    selected_item.chunk.embedding,
                    item.chunk.embedding,
                )
                >= 0.97
                for selected_item in selected
            ):
                rejection_reasons[item.chunk.chunk_id] = "near_duplicate_same_source"
                continue
            selected.append(item)
            source_counts[source_id] += 1
            if len(selected) >= query.top_k:
                break

        selected_ids = {item.chunk.chunk_id for item in selected}
        sections = tuple(self._retrieved_section(item) for item in selected)
        trace = tuple(
            RetrievalTraceItem(
                chunk_id=item.chunk.chunk_id,
                source_document_version_id=item.chunk.source_document_version_id,
                similarity=item.similarity,
                tag_score=item.tag_score,
                method_score=item.method_score,
                client_score=item.client_score,
                final_score=item.final_score,
                selected=item.chunk.chunk_id in selected_ids,
                rejection_reason=(
                    None
                    if item.chunk.chunk_id in selected_ids
                    else rejection_reasons.get(
                        item.chunk.chunk_id,
                        "below_similarity"
                        if item.similarity < query.min_similarity
                        else "outside_top_k",
                    )
                ),
            )
            for item in scored
        )
        return RetrievalResult(
            query=query,
            sections=sections,
            trace=trace,
            embedding_model_alias=self.embedding_provider.model_alias,
            embedding_dimension=self.embedding_provider.dimension,
        )

    def _score(
        self,
        query: RetrievalQuery,
        query_vector: Sequence[float],
        chunk: KnowledgeChunk,
    ) -> _ScoredChunk:
        if chunk.embedding_model_alias != self.embedding_provider.model_alias:
            raise AgentError("EMBEDDING_MODEL_MISMATCH", "索引和查询使用了不同Embedding模型")
        similarity = _cosine_similarity(query_vector, chunk.embedding)
        query_tags = (*query.component_tags, *query.risk_tags)
        chunk_tags = (*chunk.component_tags, *chunk.risk_tags)
        tag_score = _jaccard(query_tags, chunk_tags)
        method_score = _jaccard(query.method_tags, chunk.method_tags)
        client_score = float(bool(query.client_code) and query.client_code == chunk.client_code)
        final_score = (
            0.60 * similarity + 0.25 * tag_score + 0.10 * method_score + 0.05 * client_score
        )
        return _ScoredChunk(
            chunk=chunk,
            similarity=similarity,
            tag_score=tag_score,
            method_score=method_score,
            client_score=client_score,
            final_score=final_score,
        )

    @staticmethod
    def _retrieved_section(item: _ScoredChunk) -> RetrievedSection:
        chunk = item.chunk
        return RetrievedSection(
            chunk_id=chunk.chunk_id,
            source_document_version_id=chunk.source_document_version_id,
            section_code=chunk.section_code,
            heading_path=chunk.heading_path,
            text=chunk.text,
            similarity=item.similarity,
            final_score=item.final_score,
            client_code=chunk.client_code,
            component_tags=chunk.component_tags,
            method_tags=chunk.method_tags,
            risk_tags=chunk.risk_tags,
        )

    def _empty_result(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            embedding_model_alias=self.embedding_provider.model_alias,
            embedding_dimension=self.embedding_provider.dimension,
        )


class HistoricalEntityBlacklist:
    _protected_fields = frozenset(
        {
            "client_name",
            "project_name",
            "site_name",
            "project_leader",
            "site_work_leader",
            "safety_supervisor",
            "quality_acceptance_leader",
            "team_members",
            "emergency_contacts",
        }
    )

    def extract(
        self,
        facts: Sequence[ConfirmedFact],
        *,
        current_entities: Sequence[str] = (),
    ) -> frozenset[str]:
        current = {value.strip() for value in current_entities if value.strip()}
        candidates: set[str] = set()
        for fact in facts:
            if fact.field not in self._protected_fields:
                continue
            candidates.update(self._strings(fact.value))
        return frozenset(value for value in candidates if value not in current and len(value) >= 2)

    def _strings(self, value: object) -> set[str]:
        if isinstance(value, str):
            return {value.strip()} if value.strip() else set()
        if isinstance(value, list):
            result: set[str] = set()
            for item in value:
                result.update(self._strings(item))
            return result
        if isinstance(value, Mapping):
            result = set()
            for item in value.values():
                result.update(self._strings(item))
            return result
        return set()


def calculate_hit_at_k(
    cases: Sequence[tuple[RetrievalResult, set[str]]],
    *,
    k: int = 3,
) -> float:
    if not cases:
        return 0.0
    hits = 0
    for result, relevant_chunk_ids in cases:
        returned_ids = {section.chunk_id for section in result.sections[:k]}
        hits += bool(returned_ids & relevant_chunk_ids)
    return hits / len(cases)
