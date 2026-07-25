from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from .engine.contracts import (
    ClauseSelection,
    KnowledgeChunk,
    PersistedSection,
    RetrievalQuery,
    RiskProfile,
    ValidationIssue,
)
from .engine.contracts import (
    GeneratedSection as ContractGeneratedSection,
)
from .models import (
    ApprovalStatus,
    ClauseBlock,
    GeneratedSection,
    KnowledgeSection,
)


class ORMKnowledgeRepository:
    def add(self, chunks: Sequence[KnowledgeChunk]) -> int:
        created = 0
        for chunk in chunks:
            _, was_created = KnowledgeSection.objects.update_or_create(
                chunk_id=chunk.chunk_id,
                defaults={
                    "source_document_version_id": chunk.source_document_version_id,
                    "business_type": chunk.business_type,
                    "client_code": chunk.client_code or "",
                    "section_code": chunk.section_code,
                    "heading_path": list(chunk.heading_path),
                    "paragraph_start": chunk.paragraph_start,
                    "paragraph_end": chunk.paragraph_end,
                    "locator": {
                        "heading_path": list(chunk.heading_path),
                        "paragraph_start": chunk.paragraph_start,
                        "paragraph_end": chunk.paragraph_end,
                    },
                    "text": chunk.text,
                    "content_sha256": chunk.content_sha256,
                    "component_tags": list(chunk.component_tags),
                    "method_tags": list(chunk.method_tags),
                    "risk_tags": list(chunk.risk_tags),
                    "embedding": list(chunk.embedding),
                    "embedding_model_alias": chunk.embedding_model_alias,
                    "embedding_dimension": chunk.embedding_dimension,
                    "is_active": True,
                    "approval_status": ApprovalStatus.APPROVED,
                },
            )
            created += int(was_created)
        return created

    def candidates(self, query: RetrievalQuery) -> Sequence[KnowledgeChunk]:
        rows = KnowledgeSection.objects.filter(
            business_type=query.business_type,
            section_code=query.section_code,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        if query.client_code:
            rows = rows.filter(client_code__in=["", query.client_code])
        return tuple(
            KnowledgeChunk(
                chunk_id=row.chunk_id,
                source_document_version_id=row.source_document_version_id,
                business_type=row.business_type,
                client_code=row.client_code or None,
                section_code=row.section_code,
                heading_path=tuple(row.heading_path),
                paragraph_start=row.paragraph_start,
                paragraph_end=row.paragraph_end,
                text=row.text,
                component_tags=tuple(row.component_tags),
                method_tags=tuple(row.method_tags),
                risk_tags=tuple(row.risk_tags),
                approval_status="approved",
                content_sha256=row.content_sha256,
                embedding=tuple(float(value) for value in row.embedding),
                embedding_model_alias=row.embedding_model_alias,
                embedding_dimension=row.embedding_dimension,
            )
            for row in rows
        )


class ORMClauseRepository:
    def select(
        self,
        risk_profile: RiskProfile,
        section_code: str,
    ) -> Sequence[ClauseSelection]:
        active_risks = set(risk_profile.risk_codes)
        rows = ClauseBlock.objects.filter(
            section_code=section_code,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        selected: list[ClauseSelection] = []
        for row in rows:
            configured = {
                value for value in row.risk_conditions if isinstance(value, str) and value.strip()
            }
            matched = tuple(sorted(configured & active_risks))
            if configured and not matched:
                continue
            selected.append(
                ClauseSelection(
                    clause_id=str(row.pk),
                    clause_code=row.code,
                    clause_version=row.version,
                    section_code=row.section_code,
                    text=row.text,
                    matched_risk_codes=matched,
                )
            )
        return tuple(selected)


class ORMSectionRepository:
    def load(self, task_key: str, section_code: str) -> PersistedSection | None:
        row = GeneratedSection.objects.filter(
            task_id=UUID(task_key),
            section_code=section_code,
        ).first()
        if row is None:
            return None
        return self._persisted(row)

    def save(
        self,
        task_key: str,
        section: ContractGeneratedSection,
        validation_issues: Sequence[ValidationIssue],
    ) -> PersistedSection:
        defaults = {
            "title": section.title,
            "content": self._plain_text(section),
            "structured_content": section.model_dump(mode="json"),
            "citations": [citation.model_dump(mode="json") for citation in section.citations],
            "validation_issues": [issue.model_dump(mode="json") for issue in validation_issues],
        }
        row, created = GeneratedSection.objects.get_or_create(
            task_id=UUID(task_key),
            section_code=section.section_code,
            defaults={**defaults, "revision": 1},
        )
        if not created:
            if row.is_locked:
                return self._persisted(row)
            for field, value in defaults.items():
                setattr(row, field, value)
            row.revision += 1
            row.save(
                update_fields=[
                    *defaults.keys(),
                    "revision",
                    "updated_at",
                ]
            )
        return self._persisted(row)

    def lock(self, task_key: str, section_code: str) -> PersistedSection:
        row = GeneratedSection.objects.get(
            task_id=UUID(task_key),
            section_code=section_code,
        )
        if not row.is_locked:
            row.is_locked = True
            row.save(update_fields=["is_locked", "updated_at"])
        return self._persisted(row)

    @staticmethod
    def _plain_text(section: ContractGeneratedSection) -> str:
        parts = list(section.paragraphs)
        parts.extend(item for group in section.lists for item in group)
        for table in section.tables:
            parts.append(" | ".join(table.headers))
            parts.extend(" | ".join(row) for row in table.rows)
        return "\n".join(parts)

    @staticmethod
    def _persisted(row: GeneratedSection) -> PersistedSection:
        return PersistedSection(
            task_key=str(row.task_id),
            section_code=row.section_code,
            revision=row.revision,
            locked=row.is_locked,
            section=ContractGeneratedSection.model_validate(row.structured_content),
            validation_issues=tuple(
                ValidationIssue.model_validate(issue) for issue in row.validation_issues
            ),
        )
