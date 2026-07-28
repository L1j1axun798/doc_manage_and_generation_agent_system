from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from hashlib import sha256

from .contracts import (
    ENTRY_PLAN_SECTION_BLUEPRINTS,
    ENTRY_PLAN_SECTION_MIN_CHARACTERS,
    ClauseSelection,
    ConfirmedFact,
    FactCandidate,
    GeneratedSection,
    ParsedBlock,
    ParsedBlockType,
    ParsedDocument,
    RenderedArtifact,
    RenderRequest,
    RetrievalQuery,
    RetrievalResult,
    RiskProfile,
    SectionContext,
    SourceCitation,
    SourceDocument,
    SourceLocator,
    StoredArtifact,
    ValidationIssue,
    ValidationSeverity,
)

DEFAULT_SECTION_TITLES = {
    "overview": "工程概况",
    "organization_measures": "组织措施",
    "construction_plan": "施工方案",
    "technical_measures": "技术措施",
    "safety_measures": "安全措施",
    "risk_identification": "风险辨识",
    "emergency_plan": "应急预案",
    "environmental_measures": "环境保护措施",
}
_CHINESE_ORDINALS = ("一", "二", "三", "四", "五", "六", "七", "八")


class FakeSourceParser:
    def parse(self, source: SourceDocument) -> ParsedDocument:
        text = source.content.decode("utf-8", errors="replace").strip()
        if not text:
            text = source.filename
        locator = SourceLocator(paragraph_index=0, text_quote=text[:200])
        block = ParsedBlock(
            block_id=f"{source.document_version_id}:p:0",
            block_type=ParsedBlockType.PARAGRAPH,
            text=text,
            locator=locator,
        )
        return ParsedDocument(
            document_version_id=source.document_version_id,
            filename=source.filename,
            mime_type=source.mime_type,
            content_sha256=sha256(source.content).hexdigest(),
            title=source.filename,
            blocks=(block,),
        )


class FakeLLMProvider:
    def __init__(
        self,
        *,
        fact_candidates: Sequence[FactCandidate] = (),
        section_titles: dict[str, str] | None = None,
        model_alias: str = "fake-llm-v1",
    ) -> None:
        self._fact_candidates = tuple(fact_candidates)
        self._section_titles = {
            **DEFAULT_SECTION_TITLES,
            **(section_titles or {}),
        }
        self._model_alias = model_alias
        self.extract_call_count = 0
        self.draft_call_count = 0

    @property
    def model_alias(self) -> str:
        return self._model_alias

    def extract_facts(
        self,
        documents: Sequence[ParsedDocument],
    ) -> Sequence[FactCandidate]:
        self.extract_call_count += 1
        return self._fact_candidates

    def draft_section(self, context: SectionContext) -> GeneratedSection:
        self.draft_call_count += 1
        fact_summary = "；".join(
            f"计划{fact.field}={fact.value}" for fact in context.confirmed_facts
        )
        paragraphs = [f"计划内容：{fact_summary}"]
        topics = ENTRY_PLAN_SECTION_BLUEPRINTS.get(context.section_code, ())
        minimum_characters = ENTRY_PLAN_SECTION_MIN_CHARACTERS.get(
            context.section_code,
            0,
        )
        if topics:
            target_per_topic = minimum_characters // len(topics) + 80
            for index, topic in enumerate(topics):
                paragraphs.append(f"（{_CHINESE_ORDINALS[index]}）{topic}")
                sentence = (
                    f"围绕{topic}，本节按入场前计划明确责任分工、作业准备、"
                    "过程检查、协同确认和记录留存要求，相关事项须在现场作业开始前核实。"
                )
                paragraphs.append(
                    (sentence * (target_per_topic // len(sentence) + 1))[:target_per_topic]
                )
        paragraphs.extend(clause.text for clause in context.clauses)
        reference_citations = tuple(
            SourceCitation(
                source_document_version_id=reference.source_document_version_id,
                locator=SourceLocator(heading_path=reference.heading_path),
                chunk_id=reference.chunk_id,
            )
            for reference in context.references
        )
        fact_citations = tuple(
            SourceCitation(
                source_document_version_id=fact.source_document_version_id,
                locator=fact.locator,
                fact_field=fact.field,
            )
            for fact in context.confirmed_facts
        )
        return GeneratedSection(
            section_code=context.section_code,
            title=self._section_titles.get(context.section_code, context.section_code),
            paragraphs=tuple(paragraphs),
            citations=(*fact_citations, *reference_citations),
            used_fact_fields=tuple(fact.field for fact in context.confirmed_facts),
            used_clause_ids=tuple(clause.clause_id for clause in context.clauses),
        )

    def revise_section(
        self,
        context: SectionContext,
        section: GeneratedSection,
        issues: Sequence[ValidationIssue],
    ) -> GeneratedSection:
        return section

    def repair_structured_output(self, raw_output: str) -> GeneratedSection:
        payload = json.loads(raw_output)
        return GeneratedSection.model_validate(payload)


class HashingEmbeddingProvider:
    def __init__(self, *, dimension: int = 64, model_alias: str = "hashing-fake-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_alias = model_alias

    @property
    def model_alias(self) -> str:
        return self._model_alias

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return tuple(self._embed_one(text) for text in texts)

    def _embed_one(self, text: str) -> tuple[float, ...]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        compact = normalized.replace(" ", "")
        weighted_features: list[tuple[str, float]] = []
        weighted_features.extend((f"c1:{character}", 0.25) for character in compact)
        weighted_features.extend(
            (f"c2:{compact[index : index + 2]}", 1.0) for index in range(max(0, len(compact) - 1))
        )
        weighted_features.extend(
            (f"w:{token}", 1.0) for token in re.findall(r"[a-z0-9_]+", normalized)
        )
        if not weighted_features:
            weighted_features = [("_empty_", 1.0)]
        vector = [0.0] * self.dimension
        for feature, weight in weighted_features:
            digest = sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)


class StaticClauseRepository:
    def __init__(self, clauses: Sequence[ClauseSelection] = ()) -> None:
        self._clauses = tuple(clauses)

    def select(
        self,
        risk_profile: RiskProfile,
        section_code: str,
    ) -> Sequence[ClauseSelection]:
        risk_codes = set(risk_profile.risk_codes)
        return tuple(
            clause
            for clause in self._clauses
            if clause.section_code == section_code
            and set(clause.matched_risk_codes).issubset(risk_codes)
        )


class FakeRiskProfiler:
    def __init__(self, profile: RiskProfile | None = None) -> None:
        self._profile = profile or RiskProfile()

    def build(self, facts: Sequence[ConfirmedFact]) -> RiskProfile:
        return self._profile


class EmptySectionRetriever:
    def __init__(self, embedding_model_alias: str = "fake-embedding-v1") -> None:
        self._embedding_model_alias = embedding_model_alias

    @property
    def embedding_model_alias(self) -> str:
        return self._embedding_model_alias

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            embedding_model_alias=self.embedding_model_alias,
            embedding_dimension=1,
        )


class BasicSectionValidator:
    _forbidden_phrases = (
        "检测结果表明",
        "经检测发现",
        "检测结论",
        "完工报告",
    )

    def validate(
        self,
        section: GeneratedSection,
        context: SectionContext,
    ) -> Sequence[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not section.paragraphs and not section.lists and not section.tables:
            issues.append(
                ValidationIssue(
                    code="SECTION_CONTENT_EMPTY",
                    message="生成章节没有正文内容",
                    severity=ValidationSeverity.ERROR,
                    section_code=context.section_code,
                )
            )
        if section.section_code != context.section_code:
            issues.append(
                ValidationIssue(
                    code="SECTION_CODE_MISMATCH",
                    message="生成章节编码与上下文不一致",
                    severity=ValidationSeverity.ERROR,
                    section_code=context.section_code,
                )
            )
        section_text_parts = [section.title, *section.paragraphs]
        section_text_parts.extend(
            item for generated_list in section.lists for item in generated_list
        )
        section_text_parts.extend(
            cell for table in section.tables for row in (table.headers, *table.rows) for cell in row
        )
        section_text = "\n".join(section_text_parts)
        for phrase in self._forbidden_phrases:
            if phrase in section_text:
                issues.append(
                    ValidationIssue(
                        code="RESULT_CONTENT_FORBIDDEN",
                        message="入场四措两案不得包含完工结果或检测结论",
                        severity=ValidationSeverity.ERROR,
                        section_code=context.section_code,
                    )
                )
                break
        return tuple(issues)


class FakeTemplateRenderer:
    def render(self, request: RenderRequest) -> RenderedArtifact:
        payload = {
            "template_id": request.template.template_id,
            "facts": {fact.field: fact.value for fact in request.facts},
            "sections": [section.model_dump(mode="json") for section in request.sections],
        }
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        filename = request.template.filename.rsplit(".", 1)[0] + "-generated.docx"
        return RenderedArtifact(
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=content,
            sha256=sha256(content).hexdigest(),
        )


class InMemoryArtifactStorage:
    def __init__(self) -> None:
        self.artifacts: dict[str, RenderedArtifact] = {}

    def save(self, artifact: RenderedArtifact) -> StoredArtifact:
        artifact_id = f"memory:{artifact.sha256}"
        self.artifacts.setdefault(artifact_id, artifact)
        return StoredArtifact(
            artifact_id=artifact_id,
            filename=artifact.filename,
            media_type=artifact.media_type,
            sha256=artifact.sha256,
        )
