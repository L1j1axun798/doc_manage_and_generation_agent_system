from __future__ import annotations

import hashlib
from typing import Any

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import create_document
from apps.folders.models import Folder

from .models import (
    BUSINESS_TYPE,
    ApprovalStatus,
    KnowledgeCorpusUpload,
    KnowledgeSection,
)
from .queues import queue_knowledge_corpus_upload

CORPUS_FOLDER_CODE = "PUBLIC-TECH-SOLUTION"


def create_knowledge_corpus_upload(
    *,
    actor: Any,
    uploaded_file: Any,
    section_codes: list[str],
    request: Any = None,
) -> KnowledgeCorpusUpload:
    _ensure_system_admin(actor)
    normalized_section_codes = _normalize_section_codes(section_codes)
    content_sha256 = _uploaded_file_sha256(uploaded_file)
    existing_uploads = list(
        KnowledgeCorpusUpload.objects.select_related("source_document_version")
        .filter(
            source_document_version__sha256=content_sha256,
        )
        .order_by("-created_at")
    )
    requested = set(normalized_section_codes)
    overlapping_upload = next(
        (
            upload
            for upload in existing_uploads
            if requested & set(upload.section_codes or [upload.section_code])
        ),
        None,
    )
    if overlapping_upload is not None:
        raise ValidationError(
            {
                "file": (
                    "该文件的部分所选章节已经上传，当前处理状态为"
                    f"“{overlapping_upload.get_status_display()}”"
                )
            }
        )
    indexed_sections = set(
        KnowledgeSection.objects.filter(
            source_document_version__sha256=content_sha256,
            section_code__in=normalized_section_codes,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        ).values_list("section_code", flat=True)
    )
    if indexed_sections:
        labels = dict(KnowledgeCorpusUpload.SectionCode.choices)
        names = "、".join(
            labels[code] for code in normalized_section_codes if code in indexed_sections
        )
        raise ValidationError({"file": f"该文件的以下章节已经存在于RAG知识库：{names}"})
    existing = existing_uploads[0] if existing_uploads else None
    folder = None
    if existing is None:
        folder = (
            Folder.objects.filter(
                project__isnull=True,
                is_active=True,
            )
            .filter(Q(code=CORPUS_FOLDER_CODE) | Q(name="技术方案"))
            .order_by("id")
            .first()
        )
    if existing is None and folder is None:
        raise ValidationError("系统公共“技术方案”目录不存在，暂时无法保存RAG来源文件")

    storage_path = ""
    try:
        with transaction.atomic():
            version: DocumentVersion
            if existing is not None:
                version = existing.source_document_version
            else:
                assert folder is not None
                document = create_document(
                    actor=actor,
                    folder=folder,
                    uploaded_file=uploaded_file,
                    title=getattr(uploaded_file, "name", ""),
                    description="四措两案 Agent 管理员上传的 RAG 语料来源",
                    access_level=Document.AccessLevel.RESTRICTED,
                    source_type=Document.SourceType.PROJECT_UPLOAD,
                    request=request,
                )
                created_version = document.current_version
                if created_version is None:
                    raise ValidationError("RAG来源文件版本创建失败")
                version = created_version
                storage_path = version.storage_path
            upload = KnowledgeCorpusUpload.objects.create(
                source_document_version=version,
                business_type=BUSINESS_TYPE,
                section_code=normalized_section_codes[0],
                section_codes=normalized_section_codes,
                fallback_to_full_document=len(normalized_section_codes) == 1,
                created_by=actor,
            )
            audit_log(
                user=actor,
                action="document_generation.corpus.upload",
                resource=upload,
                result="success",
                request=request,
                after_data={
                    "document_version_id": version.pk,
                    "sha256": version.sha256,
                    "section_codes": upload.section_codes,
                    "status": upload.status,
                },
            )
            upload_id = str(upload.pk)

            def enqueue_upload() -> None:
                queue_knowledge_corpus_upload(upload_id)

            transaction.on_commit(enqueue_upload)
            return upload
    except Exception:
        if storage_path:
            from common.storage import LocalDocumentStorage

            LocalDocumentStorage().delete(storage_path)
        raise


def retry_knowledge_corpus_upload(
    *,
    actor: Any,
    upload: KnowledgeCorpusUpload,
    request: Any = None,
) -> KnowledgeCorpusUpload:
    _ensure_system_admin(actor)
    with transaction.atomic():
        locked = KnowledgeCorpusUpload.objects.select_for_update().get(pk=upload.pk)
        if locked.status != KnowledgeCorpusUpload.Status.FAILED:
            raise ValidationError("只有处理失败的RAG语料才能重新处理")
        locked.status = KnowledgeCorpusUpload.Status.QUEUED
        locked.error_code = ""
        locked.error_message = ""
        locked.started_at = None
        locked.completed_at = None
        locked.chunk_count = 0
        locked.indexed_section_codes = []
        locked.skipped_section_codes = []
        locked.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                "started_at",
                "completed_at",
                "chunk_count",
                "indexed_section_codes",
                "skipped_section_codes",
                "updated_at",
            ]
        )
        audit_log(
            user=actor,
            action="document_generation.corpus.retry",
            resource=locked,
            result="success",
            request=request,
            after_data={"status": locked.status},
        )
        upload_id = str(locked.pk)

        def enqueue_retry() -> None:
            queue_knowledge_corpus_upload(upload_id)

        transaction.on_commit(enqueue_retry)
        return locked


def _ensure_system_admin(actor: Any) -> None:
    if not getattr(actor, "is_system_admin", False):
        raise PermissionDenied("仅系统管理员可以维护RAG语料")


def _normalize_section_codes(section_codes: list[str]) -> list[str]:
    valid_codes = {value for value, _label in KnowledgeCorpusUpload.SectionCode.choices}
    normalized: list[str] = []
    for code in section_codes:
        if code in valid_codes and code not in normalized:
            normalized.append(code)
    if not normalized:
        raise ValidationError({"section_codes": "请至少选择一个适用章节"})
    return normalized


def _uploaded_file_sha256(uploaded_file: Any) -> str:
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()
