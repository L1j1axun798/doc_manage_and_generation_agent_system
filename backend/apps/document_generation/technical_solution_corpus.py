from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.audit.services import audit_log
from apps.documents.models import Document, DocumentVersion
from common.storage import LocalDocumentStorage

from .engine.contracts import KnowledgeSectionInput, SourceDocument
from .engine.errors import AgentError
from .engine.parsing import EntrySourceParser
from .engine.rag import SectionChunker
from .knowledge_corpus import CORPUS_FOLDER_CODE, _ensure_system_admin
from .knowledge_sections import blocks_for_section, classify_heading_path
from .models import (
    BUSINESS_TYPE,
    ApprovalStatus,
    KnowledgeCorpusUpload,
    KnowledgeSection,
)
from .queues import queue_knowledge_corpus_upload


@dataclass(frozen=True)
class TechnicalSolutionCorpusPlan:
    document_id: int
    version_id: int
    filename: str
    section_codes: tuple[str, ...] = ()
    empty_section_codes: tuple[str, ...] = ()
    existing_section_codes: tuple[str, ...] = ()
    estimated_chunk_count: int = 0
    skip_reason: str = ""

    @property
    def should_queue(self) -> bool:
        return bool(self.section_codes) and self.estimated_chunk_count > 0


def scan_technical_solution_corpus() -> list[TechnicalSolutionCorpusPlan]:
    documents = (
        Document.objects.filter(
            Q(folder__code=CORPUS_FOLDER_CODE) | Q(folder__name="技术方案"),
            folder__is_active=True,
            deleted_at__isnull=True,
            current_version__isnull=False,
        )
        .select_related("current_version")
        .order_by("id")
    )
    parser = EntrySourceParser()
    chunker = SectionChunker()
    storage = LocalDocumentStorage()
    section_order = [code for code, _label in KnowledgeCorpusUpload.SectionCode.choices]
    plans: list[TechnicalSolutionCorpusPlan] = []

    for document in documents:
        version = document.current_version
        if version is None:
            continue
        existing_sections = set(
            KnowledgeSection.objects.filter(
                source_document_version__sha256=version.sha256,
                is_active=True,
                approval_status=ApprovalStatus.APPROVED,
            ).values_list("section_code", flat=True)
        )
        reserved_sections: set[str] = set()
        for upload in KnowledgeCorpusUpload.objects.filter(
            source_document_version__sha256=version.sha256
        ).only("section_code", "section_codes"):
            reserved_sections.update(upload.section_codes or [upload.section_code])

        try:
            path = storage.resolve(version.storage_path)
            if not path.is_file():
                raise AgentError("SOURCE_PARSE_FAILED", "来源文件不存在")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != version.sha256:
                raise AgentError("SOURCE_INTEGRITY_FAILED", "来源文件完整性校验失败")
            parsed = parser.parse(
                SourceDocument(
                    document_version_id=version.pk,
                    filename=version.original_filename,
                    mime_type=version.content_type,
                    content=content,
                )
            )
        except Exception as exc:
            plans.append(
                _skipped_plan(
                    document=document,
                    version=version,
                    existing_sections=existing_sections,
                    reason=_error_reason(exc),
                )
            )
            continue

        recognized = {
            section_code
            for block in parsed.blocks
            if (section_code := classify_heading_path(block.heading_path)) is not None
        }
        missing_sections = [
            code
            for code in section_order
            if code in recognized
            and code not in existing_sections
            and code not in reserved_sections
        ]
        if not missing_sections:
            plans.append(
                _skipped_plan(
                    document=document,
                    version=version,
                    existing_sections=existing_sections,
                    reason="已完整覆盖或已有处理记录",
                )
            )
            continue

        empty_sections: list[str] = []
        estimated_chunk_count = 0
        fatal_error = ""
        for section_code in missing_sections:
            try:
                drafts = chunker.chunk(
                    KnowledgeSectionInput(
                        source_document_version_id=version.pk,
                        business_type=BUSINESS_TYPE,
                        section_code=section_code,
                        blocks=blocks_for_section(parsed.blocks, section_code),
                        approval_status="approved",
                    )
                )
            except AgentError as exc:
                if exc.code == "KNOWLEDGE_SECTION_EMPTY":
                    empty_sections.append(section_code)
                    continue
                fatal_error = _error_reason(exc)
                break
            estimated_chunk_count += len(drafts)

        if fatal_error or estimated_chunk_count == 0:
            plans.append(
                _skipped_plan(
                    document=document,
                    version=version,
                    existing_sections=existing_sections,
                    empty_sections=empty_sections,
                    reason=fatal_error or "缺失章节没有可索引正文",
                )
            )
            continue
        plans.append(
            TechnicalSolutionCorpusPlan(
                document_id=document.pk,
                version_id=version.pk,
                filename=version.original_filename,
                section_codes=tuple(missing_sections),
                empty_section_codes=tuple(empty_sections),
                existing_section_codes=tuple(sorted(existing_sections)),
                estimated_chunk_count=estimated_chunk_count,
            )
        )
    return plans


def enqueue_technical_solution_corpus(
    *,
    actor: Any,
    plans: list[TechnicalSolutionCorpusPlan],
) -> list[KnowledgeCorpusUpload]:
    _ensure_system_admin(actor)
    created: list[KnowledgeCorpusUpload] = []
    for plan in plans:
        if not plan.should_queue:
            continue
        with transaction.atomic():
            version = DocumentVersion.objects.select_related("document").get(pk=plan.version_id)
            existing_sections = set(
                KnowledgeSection.objects.filter(
                    source_document_version__sha256=version.sha256,
                    section_code__in=plan.section_codes,
                    is_active=True,
                    approval_status=ApprovalStatus.APPROVED,
                ).values_list("section_code", flat=True)
            )
            reserved_sections: set[str] = set()
            for upload in KnowledgeCorpusUpload.objects.select_for_update().filter(
                source_document_version__sha256=version.sha256
            ):
                reserved_sections.update(upload.section_codes or [upload.section_code])
            section_codes = [
                code
                for code in plan.section_codes
                if code not in existing_sections and code not in reserved_sections
            ]
            if not section_codes:
                continue
            upload = KnowledgeCorpusUpload.objects.create(
                source_document_version=version,
                business_type=BUSINESS_TYPE,
                section_code=section_codes[0],
                section_codes=section_codes,
                fallback_to_full_document=False,
                created_by=actor,
            )
            audit_log(
                user=actor,
                action="document_generation.corpus.bulk_queue",
                resource=upload,
                result="success",
                after_data={
                    "document_id": version.document_id,
                    "document_version_id": version.pk,
                    "sha256": version.sha256,
                    "section_codes": section_codes,
                    "estimated_chunk_count": plan.estimated_chunk_count,
                },
            )
            created.append(upload)
        queue_knowledge_corpus_upload(str(upload.pk))
    return created


def _skipped_plan(
    *,
    document: Document,
    version: DocumentVersion,
    existing_sections: set[str],
    reason: str,
    empty_sections: list[str] | None = None,
) -> TechnicalSolutionCorpusPlan:
    return TechnicalSolutionCorpusPlan(
        document_id=document.pk,
        version_id=version.pk,
        filename=version.original_filename,
        empty_section_codes=tuple(empty_sections or ()),
        existing_section_codes=tuple(sorted(existing_sections)),
        skip_reason=reason,
    )


def _error_reason(exc: Exception) -> str:
    if isinstance(exc, AgentError):
        return f"{exc.code}: {exc}"
    return f"{type(exc).__name__}: {exc}"
