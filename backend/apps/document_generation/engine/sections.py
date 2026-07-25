from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .contracts import (
    ClauseSelection,
    ConfirmedFact,
    GeneratedSection,
    PersistedSection,
    RetrievalResult,
    RiskProfile,
    SectionContext,
    ValidationIssue,
)
from .errors import AgentError


class SectionContextBuilder:
    def build(
        self,
        *,
        section_code: str,
        confirmed_facts: Sequence[ConfirmedFact],
        risk_profile: RiskProfile,
        clauses: Sequence[ClauseSelection],
        retrieval: RetrievalResult,
    ) -> SectionContext:
        if retrieval.query.section_code != section_code:
            raise AgentError("SECTION_CONTEXT_INVALID", "检索结果章节与目标章节不一致")
        return SectionContext(
            section_code=section_code,
            objective=f"编写入场四措两案的{section_code}章节",
            confirmed_facts=tuple(confirmed_facts),
            risk_profile=risk_profile,
            clauses=tuple(clauses),
            references=retrieval.sections,
        )


class InMemorySectionRepository:
    def __init__(self) -> None:
        self._sections: dict[tuple[str, str], PersistedSection] = {}

    def load(self, task_key: str, section_code: str) -> PersistedSection | None:
        return self._sections.get((task_key, section_code))

    def save(
        self,
        task_key: str,
        section: GeneratedSection,
        validation_issues: Sequence[ValidationIssue],
    ) -> PersistedSection:
        key = (task_key, section.section_code)
        existing = self._sections.get(key)
        if existing is not None and existing.locked:
            return existing
        persisted = PersistedSection(
            task_key=task_key,
            section_code=section.section_code,
            revision=1 if existing is None else existing.revision + 1,
            locked=False,
            section=section,
            validation_issues=tuple(validation_issues),
        )
        self._sections[key] = persisted
        return persisted

    def lock(self, task_key: str, section_code: str) -> PersistedSection:
        key = (task_key, section_code)
        existing = self._sections.get(key)
        if existing is None:
            raise AgentError("SECTION_NOT_FOUND", "不能锁定尚未生成的章节")
        locked = existing.model_copy(update={"locked": True})
        self._sections[key] = locked
        return locked


class JsonSectionRepository(InMemorySectionRepository):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("section state must contain a JSON list")
            for item in payload:
                persisted = PersistedSection.model_validate(item)
                self._sections[(persisted.task_key, persisted.section_code)] = persisted

    def save(
        self,
        task_key: str,
        section: GeneratedSection,
        validation_issues: Sequence[ValidationIssue],
    ) -> PersistedSection:
        persisted = super().save(task_key, section, validation_issues)
        self._persist()
        return persisted

    def lock(self, task_key: str, section_code: str) -> PersistedSection:
        persisted = super().lock(task_key, section_code)
        self._persist()
        return persisted

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [
                    persisted.model_dump(mode="json")
                    for _, persisted in sorted(self._sections.items())
                ],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)
