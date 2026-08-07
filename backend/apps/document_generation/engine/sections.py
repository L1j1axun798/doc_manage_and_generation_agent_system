from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .contracts import (
    ENTRY_PLAN_SECTION_BLUEPRINTS,
    ENTRY_PLAN_SECTION_MIN_CHARACTERS,
    ENTRY_PLAN_SECTION_TITLES,
    AgentConversationContext,
    ClauseSelection,
    ConfirmedFact,
    GeneratedSection,
    PersistedSection,
    RetrievalResult,
    RetrievedSection,
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
        conversation_context: AgentConversationContext | None = None,
        revision_instruction: str = "",
        revision_conversation: Sequence[str] = (),
        revision_required_literals: Sequence[str] = (),
        previous_content: str = "",
        priority_references: Sequence[RetrievedSection] = (),
    ) -> SectionContext:
        if retrieval.query.section_code != section_code:
            raise AgentError("SECTION_CONTEXT_INVALID", "检索结果章节与目标章节不一致")
        title = ENTRY_PLAN_SECTION_TITLES.get(section_code, section_code)
        topics = ENTRY_PLAN_SECTION_BLUEPRINTS.get(section_code, ())
        minimum_characters = ENTRY_PLAN_SECTION_MIN_CHARACTERS.get(section_code)
        quality_parts = [
            f"编写入场四措两案的“{title}”章节",
            "不得重复堆砌项目概况",
        ]
        if topics:
            quality_parts.append(f"必须覆盖：{'；'.join(topics)}")
        if minimum_characters is not None:
            quality_parts.append(
                f"写作目标不少于{minimum_characters * 5 // 4}个中文字符，"
                f"确定性最低门禁为{minimum_characters}个中文字符"
            )
        quality_parts.append("资料不足时必须登记缺项，不得编造")
        active_conversation_context = conversation_context or AgentConversationContext()
        initial_message = active_conversation_context.initial_message.strip()
        if initial_message:
            quality_parts.insert(
                1,
                f"用户本次编制要求是关键任务依据，必须在本章适用范围内落实：{initial_message}",
            )
        if (
            active_conversation_context.template is not None
            and active_conversation_context.template.format_locked
        ):
            quality_parts.append(
                "严格使用当前选定模板，只填写允许位置，不得改变章节顺序、标题层级、表格和版式"
            )
        references = tuple(
            {
                reference.chunk_id: reference
                for reference in (*priority_references, *retrieval.sections)
            }.values()
        )
        return SectionContext(
            section_code=section_code,
            objective="质量结构要求：" + "；".join(quality_parts),
            confirmed_facts=tuple(confirmed_facts),
            risk_profile=risk_profile,
            clauses=tuple(clauses),
            references=references,
            conversation_context=active_conversation_context,
            revision_instruction=revision_instruction,
            revision_conversation=tuple(revision_conversation),
            revision_required_literals=tuple(revision_required_literals),
            previous_content=previous_content,
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
