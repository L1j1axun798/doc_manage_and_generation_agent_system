from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence

from pydantic import JsonValue

from .contracts import (
    ConfirmedFact,
    FactCandidate,
    FactConflict,
    FactEvidence,
    FactMergeResult,
    MergedFactCandidate,
    ParsedDocument,
    RejectedFactCandidate,
)
from .errors import AgentError, FactsIncompleteError, SourcePurposeMismatchError

RESULT_VALUE_MARKERS = (
    "经检测发现",
    "检测结果表明",
    "检测结论",
    "实测结果",
    "缺陷清单",
    "处理结果",
    "验收结论",
    "完工报告",
)


def _canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _strings(value: JsonValue) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def contains_result_fact(value: JsonValue) -> bool:
    return any(marker in text for text in _strings(value) for marker in RESULT_VALUE_MARKERS)


class FactMergeService:
    def merge(self, candidates: Sequence[FactCandidate]) -> FactMergeResult:
        grouped: dict[str, list[FactCandidate]] = defaultdict(list)
        rejected: list[RejectedFactCandidate] = []
        for candidate in candidates:
            if contains_result_fact(candidate.value):
                rejected.append(
                    RejectedFactCandidate(
                        field=candidate.field,
                        reason_code="RESULT_FACT_FORBIDDEN",
                        source_document_version_id=candidate.source_document_version_id,
                    )
                )
                continue
            grouped[candidate.field].append(candidate)

        merged: list[MergedFactCandidate] = []
        conflicts: list[FactConflict] = []
        for field in sorted(grouped):
            by_value: dict[str, list[FactCandidate]] = defaultdict(list)
            for candidate in grouped[field]:
                key = f"{candidate.value_type}:{_canonical_json(candidate.value)}"
                by_value[key].append(candidate)
            value_groups = [self._merge_same_value(group) for _, group in sorted(by_value.items())]
            if len(value_groups) == 1:
                merged.append(value_groups[0])
            else:
                conflicts.append(
                    FactConflict(
                        field=field,
                        candidates=tuple(value_groups),
                    )
                )
        return FactMergeResult(
            merged=tuple(merged),
            conflicts=tuple(conflicts),
            rejected=tuple(rejected),
        )

    @staticmethod
    def _merge_same_value(
        candidates: Sequence[FactCandidate],
    ) -> MergedFactCandidate:
        first = candidates[0]
        evidence_by_key: dict[str, FactEvidence] = {}
        for candidate in candidates:
            evidence = FactEvidence(
                source_document_version_id=candidate.source_document_version_id,
                locator=candidate.locator,
                confidence=candidate.confidence,
            )
            key = f"{candidate.source_document_version_id}:{candidate.locator.model_dump_json()}"
            evidence_by_key.setdefault(key, evidence)
        return MergedFactCandidate(
            field=first.field,
            value=first.value,
            value_type=first.value_type,
            evidence=tuple(evidence_by_key[key] for key in sorted(evidence_by_key)),
            confidence=max(candidate.confidence for candidate in candidates),
        )


class RequiredFactGate:
    def validate(
        self,
        facts: Sequence[ConfirmedFact],
        *,
        required_fields: Sequence[str],
    ) -> tuple[ConfirmedFact, ...]:
        by_field: dict[str, ConfirmedFact] = {}
        for fact in facts:
            if contains_result_fact(fact.value):
                raise SourcePurposeMismatchError("完工结果或检测结论不能提升为入场方案事实")
            existing = by_field.get(fact.field)
            if existing is not None and _canonical_json(existing.value) != _canonical_json(
                fact.value
            ):
                raise AgentError(
                    "FACT_CONFIRMATION_CONFLICT",
                    f"字段 {fact.field} 存在多个已确认值",
                )
            if existing is not None and existing.value_type != fact.value_type:
                raise AgentError(
                    "FACT_CONFIRMATION_CONFLICT",
                    f"字段 {fact.field} 存在多个已确认类型",
                )
            by_field.setdefault(fact.field, fact)

        missing = sorted(set(required_fields) - by_field.keys())
        if "inspection_quantity" in by_field and "inspection_unit" not in by_field:
            missing.append("inspection_unit")
        if missing:
            raise FactsIncompleteError(sorted(set(missing)))
        return tuple(by_field[field] for field in sorted(by_field))


class FactEvidenceGate:
    def validate(
        self,
        facts: Sequence[ConfirmedFact],
        *,
        documents: Sequence[ParsedDocument],
    ) -> tuple[ConfirmedFact, ...]:
        documents_by_id: dict[int, ParsedDocument] = {}
        duplicate_document_ids: set[int] = set()
        for document in documents:
            if document.document_version_id in documents_by_id:
                duplicate_document_ids.add(document.document_version_id)
            documents_by_id[document.document_version_id] = document
        if duplicate_document_ids:
            raise AgentError(
                "SOURCE_VERSION_DUPLICATE",
                "同一来源文档版本不得重复输入",
                details={"document_version_ids": sorted(duplicate_document_ids)},
            )

        invalid_fields: list[str] = []
        for fact in facts:
            source_document = documents_by_id.get(fact.source_document_version_id)
            if source_document is None or not self._locator_exists(fact, source_document):
                invalid_fields.append(fact.field)
        if invalid_fields:
            raise AgentError(
                "FACT_EVIDENCE_INVALID",
                "已确认事实的来源定位不存在或不属于本次输入",
                details={"fields": sorted(set(invalid_fields))},
            )
        return tuple(facts)

    @staticmethod
    def _locator_exists(
        fact: ConfirmedFact,
        document: ParsedDocument,
    ) -> bool:
        expected = fact.locator
        has_locator = any(
            (
                expected.paragraph_index is not None,
                expected.page is not None,
                expected.table_index is not None,
                bool(expected.heading_path),
                bool(expected.text_quote and expected.text_quote.strip()),
            )
        )
        if not has_locator:
            return False

        for block in document.blocks:
            actual = block.locator
            if (
                expected.paragraph_index is not None
                and actual.paragraph_index != expected.paragraph_index
            ):
                continue
            if expected.page is not None and actual.page != expected.page:
                continue
            if expected.table_index is not None and actual.table_index != expected.table_index:
                continue
            if expected.heading_path and actual.heading_path != expected.heading_path:
                continue
            if expected.text_quote:
                quote = " ".join(expected.text_quote.split())
                block_text = " ".join(block.text.split())
                if quote not in block_text:
                    continue
            return True
        return False
