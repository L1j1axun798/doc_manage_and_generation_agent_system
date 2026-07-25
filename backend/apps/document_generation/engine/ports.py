from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .contracts import (
    ClauseSelection,
    ConfirmedFact,
    FactCandidate,
    GeneratedSection,
    KnowledgeChunk,
    ParsedDocument,
    PersistedSection,
    RenderedArtifact,
    RenderRequest,
    RetrievalQuery,
    RetrievalResult,
    RiskProfile,
    SectionContext,
    SourceDocument,
    StoredArtifact,
    ValidationIssue,
)


class SourceParser(Protocol):
    def parse(self, source: SourceDocument) -> ParsedDocument: ...


class LLMProvider(Protocol):
    @property
    def model_alias(self) -> str: ...

    def extract_facts(
        self,
        documents: Sequence[ParsedDocument],
    ) -> Sequence[FactCandidate]: ...

    def draft_section(self, context: SectionContext) -> GeneratedSection: ...

    def revise_section(
        self,
        context: SectionContext,
        section: GeneratedSection,
        issues: Sequence[ValidationIssue],
    ) -> GeneratedSection: ...

    def repair_structured_output(self, raw_output: str) -> GeneratedSection: ...


class EmbeddingProvider(Protocol):
    @property
    def model_alias(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class KnowledgeRepository(Protocol):
    def add(self, chunks: Sequence[KnowledgeChunk]) -> int: ...

    def candidates(self, query: RetrievalQuery) -> Sequence[KnowledgeChunk]: ...


class ClauseRepository(Protocol):
    def select(
        self,
        risk_profile: RiskProfile,
        section_code: str,
    ) -> Sequence[ClauseSelection]: ...


class RiskProfiler(Protocol):
    def build(self, facts: Sequence[ConfirmedFact]) -> RiskProfile: ...


class SectionRetriever(Protocol):
    @property
    def embedding_model_alias(self) -> str: ...

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


class SectionValidator(Protocol):
    def validate(
        self,
        section: GeneratedSection,
        context: SectionContext,
    ) -> Sequence[ValidationIssue]: ...


class SectionRepository(Protocol):
    def load(self, task_key: str, section_code: str) -> PersistedSection | None: ...

    def save(
        self,
        task_key: str,
        section: GeneratedSection,
        validation_issues: Sequence[ValidationIssue],
    ) -> PersistedSection: ...

    def lock(self, task_key: str, section_code: str) -> PersistedSection: ...


class TemplateRenderer(Protocol):
    def render(self, request: RenderRequest) -> RenderedArtifact: ...


class ArtifactStorage(Protocol):
    def save(self, artifact: RenderedArtifact) -> StoredArtifact: ...
