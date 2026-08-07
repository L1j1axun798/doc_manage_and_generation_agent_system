from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pydantic import JsonValue
from rq import get_current_job

from apps.audit.services import audit_log
from common.storage import LocalDocumentStorage

from .artifacts import TaskDraftArtifactStorage
from .conversation_sources import prompt_source_document
from .engine.canonical_facts import enrich_required_fact_candidates
from .engine.contracts import (
    AgentConversationContext,
    ConfirmedFact,
    FactCandidate,
    GenerationRequest,
    KnowledgeChunk,
    KnowledgeChunkDraft,
    KnowledgeSectionInput,
    ParsedDocument,
    RetrievedSection,
    SourceDocument,
    TemplateDocument,
)
from .engine.errors import AgentError, WorkflowExecutionError
from .engine.facts import FactMergeService
from .engine.fakes import (
    FakeLLMProvider,
    HashingEmbeddingProvider,
)
from .engine.orchestrator import GenerationOrchestrator
from .engine.parsing import EntrySourceParser
from .engine.ports import EmbeddingProvider, LLMProvider
from .engine.rag import RagRetriever, SectionChunker
from .engine.rendering import DocxTemplateRenderer, infer_template_section_order
from .engine.validation import ControlledSectionValidator
from .knowledge_sections import blocks_for_section
from .models import (
    ApprovalStatus,
    GenerationReview,
    GenerationSource,
    GenerationTask,
    KnowledgeCorpusUpload,
    KnowledgeSection,
)
from .providers.embedding import OpenAICompatibleEmbeddingProvider
from .providers.llm import OpenAICompatibleLLMProvider
from .repositories import ORMClauseRepository, ORMKnowledgeRepository, ORMSectionRepository
from .revision import is_revision_followup, revision_required_literals
from .risk import ORMRiskProfiler
from .workflow_events import TaskWorkflowRecorder


def run_knowledge_corpus_upload(upload_id: str) -> str:
    with transaction.atomic():
        upload = (
            KnowledgeCorpusUpload.objects.select_for_update()
            .select_related("source_document_version", "created_by")
            .get(pk=upload_id)
        )
        if upload.status not in {
            KnowledgeCorpusUpload.Status.QUEUED,
            KnowledgeCorpusUpload.Status.FAILED,
        }:
            return "skipped"
        upload.status = KnowledgeCorpusUpload.Status.PROCESSING
        upload.started_at = timezone.now()
        upload.completed_at = None
        upload.error_code = ""
        upload.error_message = ""
        upload.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
    try:
        source = _load_corpus_source(upload_id)
        upload = KnowledgeCorpusUpload.objects.get(pk=upload_id)
        parsed = EntrySourceParser().parse(source)
        section_codes = upload.section_codes or [upload.section_code]
        indexed_section_codes: list[str] = []
        skipped_section_codes: list[str] = []
        drafts: list[KnowledgeChunkDraft] = []
        chunker = SectionChunker()
        for section_code in section_codes:
            section_blocks = blocks_for_section(parsed.blocks, section_code)
            if not section_blocks and upload.fallback_to_full_document:
                section_blocks = parsed.blocks
            if not section_blocks:
                skipped_section_codes.append(section_code)
                continue
            try:
                section_drafts = chunker.chunk(
                    KnowledgeSectionInput(
                        source_document_version_id=source.document_version_id,
                        business_type=upload.business_type,
                        section_code=section_code,
                        blocks=section_blocks,
                        approval_status="approved",
                    )
                )
            except AgentError as exc:
                if exc.code != "KNOWLEDGE_SECTION_EMPTY":
                    raise
                skipped_section_codes.append(section_code)
                continue
            drafts.extend(section_drafts)
            indexed_section_codes.append(section_code)
        if not drafts:
            raise AgentError(
                "KNOWLEDGE_SECTIONS_NOT_FOUND",
                "没有从文件标题结构中识别出所选章节",
            )
        embedding_provider = _build_embedding_provider()
        vectors = tuple(embedding_provider.embed([draft.text for draft in drafts]))
        if len(vectors) != len(drafts):
            raise AgentError("EMBEDDING_RESPONSE_INVALID", "Embedding返回数量不一致")
        chunks = tuple(
            KnowledgeChunk(
                **draft.model_dump(),
                embedding=tuple(float(value) for value in vector),
                embedding_model_alias=embedding_provider.model_alias,
                embedding_dimension=embedding_provider.dimension,
            )
            for draft, vector in zip(drafts, vectors, strict=True)
        )
        _complete_corpus_upload(
            upload_id,
            chunks,
            indexed_section_codes=indexed_section_codes,
            skipped_section_codes=skipped_section_codes,
        )
    except Exception as exc:
        _fail_corpus_upload(upload_id, exc)
        raise
    return "completed"


def run_generation_task(task_id: str) -> str:
    task = GenerationTask.objects.only("status", "operation").get(pk=task_id)
    if (
        task.operation == GenerationTask.Operation.EXTRACT
        and task.status == GenerationTask.Status.EXTRACTING
    ):
        return _run_fact_extraction(task_id)
    if (
        task.operation == GenerationTask.Operation.GENERATE
        and task.status == GenerationTask.Status.QUEUED
    ):
        return _run_document_generation(task_id)
    return "skipped"


def _load_corpus_source(upload_id: str) -> SourceDocument:
    upload = KnowledgeCorpusUpload.objects.select_related("source_document_version").get(
        pk=upload_id
    )
    version = upload.source_document_version
    path = LocalDocumentStorage().resolve(version.storage_path)
    if not path.is_file():
        raise AgentError("SOURCE_PARSE_FAILED", "RAG来源文档物理文件不存在")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != version.sha256:
        raise AgentError("SOURCE_INTEGRITY_FAILED", "RAG来源文档完整性校验失败")
    return SourceDocument(
        document_version_id=version.pk,
        filename=version.original_filename,
        mime_type=version.content_type,
        content=content,
    )


def _build_embedding_provider() -> EmbeddingProvider:
    if settings.DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:
        return HashingEmbeddingProvider()
    return OpenAICompatibleEmbeddingProvider.from_env()


def _complete_corpus_upload(
    upload_id: str,
    chunks: tuple[KnowledgeChunk, ...],
    *,
    indexed_section_codes: list[str],
    skipped_section_codes: list[str],
) -> None:
    if not chunks:
        raise AgentError("KNOWLEDGE_SECTION_EMPTY", "来源资料没有生成可用知识块")
    now = timezone.now()
    with transaction.atomic():
        upload = (
            KnowledgeCorpusUpload.objects.select_for_update()
            .select_related("created_by")
            .get(pk=upload_id)
        )
        if upload.status != KnowledgeCorpusUpload.Status.PROCESSING:
            return
        KnowledgeSection.objects.filter(
            source_document_version=upload.source_document_version,
            section_code__in=upload.section_codes or [upload.section_code],
        ).delete()
        KnowledgeSection.objects.bulk_create(
            [
                KnowledgeSection(
                    chunk_id=chunk.chunk_id,
                    source_document_version_id=chunk.source_document_version_id,
                    business_type=chunk.business_type,
                    client_code=chunk.client_code or "",
                    section_code=chunk.section_code,
                    heading_path=list(chunk.heading_path),
                    paragraph_start=chunk.paragraph_start,
                    paragraph_end=chunk.paragraph_end,
                    locator={
                        "heading_path": list(chunk.heading_path),
                        "paragraph_start": chunk.paragraph_start,
                        "paragraph_end": chunk.paragraph_end,
                    },
                    text=chunk.text,
                    content_sha256=chunk.content_sha256,
                    component_tags=list(chunk.component_tags),
                    method_tags=list(chunk.method_tags),
                    risk_tags=list(chunk.risk_tags),
                    embedding=list(chunk.embedding),
                    embedding_model_alias=chunk.embedding_model_alias,
                    embedding_dimension=chunk.embedding_dimension,
                    is_active=True,
                    approval_status=ApprovalStatus.APPROVED,
                    approved_by=upload.created_by,
                    approved_at=now,
                )
                for chunk in chunks
            ]
        )
        upload.status = KnowledgeCorpusUpload.Status.SUCCEEDED
        upload.chunk_count = len(chunks)
        upload.embedding_model_alias = chunks[0].embedding_model_alias
        upload.embedding_dimension = chunks[0].embedding_dimension
        upload.indexed_section_codes = indexed_section_codes
        upload.skipped_section_codes = skipped_section_codes
        upload.completed_at = now
        upload.error_code = ""
        upload.error_message = ""
        upload.save(
            update_fields=[
                "status",
                "chunk_count",
                "embedding_model_alias",
                "embedding_dimension",
                "indexed_section_codes",
                "skipped_section_codes",
                "completed_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        audit_log(
            user=upload.created_by,
            action="document_generation.corpus.index.complete",
            resource=upload,
            result="success",
            after_data={
                "chunk_count": upload.chunk_count,
                "embedding_model_alias": upload.embedding_model_alias,
                "embedding_dimension": upload.embedding_dimension,
                "indexed_section_codes": upload.indexed_section_codes,
                "skipped_section_codes": upload.skipped_section_codes,
            },
        )


def _fail_corpus_upload(upload_id: str, exc: Exception) -> None:
    error_code = exc.code if isinstance(exc, AgentError) else "CORPUS_PROCESSING_FAILED"
    error_message = (
        str(exc)
        if isinstance(exc, AgentError)
        else "RAG语料处理失败，请检查文件内容和Embedding服务后重试"
    )
    with transaction.atomic():
        upload = (
            KnowledgeCorpusUpload.objects.select_for_update()
            .select_related("created_by")
            .get(pk=upload_id)
        )
        upload.status = KnowledgeCorpusUpload.Status.FAILED
        upload.error_code = error_code[:80]
        upload.error_message = error_message[:500]
        upload.completed_at = timezone.now()
        upload.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                "completed_at",
                "updated_at",
            ]
        )
        audit_log(
            user=upload.created_by,
            action="document_generation.corpus.index.failed",
            resource=upload,
            result="failed",
            error_message=upload.error_message,
        )


def _run_document_generation(task_id: str) -> str:
    with transaction.atomic():
        task = (
            GenerationTask.objects.select_for_update()
            .select_related(
                "project",
                "template__document_version",
                "created_by",
            )
            .get(pk=task_id)
        )
        if task.status != GenerationTask.Status.QUEUED:
            return "skipped"
        if task.project.status != task.project.Status.ACTIVE:
            task.status = GenerationTask.Status.FAILED
            task.error_code = "PROJECT_ARCHIVED"
            task.error_message = "项目已归档，任务已停止"
            task.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            return "failed"
        task.status = GenerationTask.Status.GENERATING
        task.progress = 40
        task.generation_attempts += 1
        task.started_at = timezone.now()
        task.error_code = ""
        task.error_message = ""
        task.save(
            update_fields=[
                "status",
                "progress",
                "generation_attempts",
                "started_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        for review in task.reviews.filter(
            action=GenerationReview.Action.SECTION_REGENERATED,
            section__section_code__in=task.pending_section_codes,
        ):
            metadata = dict(review.metadata or {})
            if metadata.get("conversation_status") != "queued":
                continue
            metadata["conversation_status"] = "processing"
            metadata["assistant_message"] = (
                "正在理解你的修改要求，并重新检索本章可用的已批准RAG参考。"
            )
            review.metadata = metadata
            review.save(update_fields=["metadata"])
        GenerationSource.objects.filter(task=task).update(
            parse_status=GenerationSource.ParseStatus.PENDING,
            parse_error="",
        )
    try:
        request = _build_request(task_id)
        orchestrator, provider_alias, model_alias = _build_orchestrator(task_id)
        orchestrator.run(request)
    except Exception as exc:
        if _task_is_cancelled(task_id):
            return "cancelled"
        _record_failure(task_id, exc)
        if isinstance(exc, AgentError) and exc.code == "FACT_EVIDENCE_INVALID":
            return "needs_confirmation"
        if GenerationTask.objects.filter(
            pk=task_id,
            status=GenerationTask.Status.REVIEW_REQUIRED,
        ).exists():
            return "review_required"
        raise
    with transaction.atomic():
        task = GenerationTask.objects.select_for_update().get(pk=task_id)
        if task.status != GenerationTask.Status.GENERATING:
            return "superseded"
        task.status = GenerationTask.Status.REVIEW_REQUIRED
        task.progress = 90
        task.provider_alias = provider_alias
        task.model_alias = model_alias
        task.prompt_version = "section_generation/v4"
        task.chunk_rule_version = "phase3-v1"
        completed_section_codes = list(task.pending_section_codes)
        task.pending_section_codes = []
        task.completed_at = timezone.now()
        task.save(
            update_fields=[
                "status",
                "progress",
                "provider_alias",
                "model_alias",
                "prompt_version",
                "chunk_rule_version",
                "pending_section_codes",
                "completed_at",
                "updated_at",
            ]
        )
        revisions = {
            section.section_code: section.revision
            for section in task.sections.filter(section_code__in=completed_section_codes)
        }
        for review in task.reviews.filter(
            action=GenerationReview.Action.SECTION_REGENERATED,
            section__section_code__in=completed_section_codes,
        ):
            metadata = dict(review.metadata or {})
            if metadata.get("conversation_status") not in {"queued", "processing"}:
                continue
            revision = revisions.get(review.section.section_code) if review.section else None
            metadata.update(
                {
                    "conversation_status": "completed",
                    "assistant_message": (
                        f"本轮修改已写入正文并通过落地校验，当前为修订 {revision}。"
                        "请继续核对正文、事实和引用。"
                    ),
                    "revision_after": revision,
                }
            )
            review.metadata = metadata
            review.save(update_fields=["metadata"])
        GenerationSource.objects.filter(task=task).update(
            parse_status=GenerationSource.ParseStatus.PARSED,
            parse_error="",
        )
        audit_log(
            user=task.created_by,
            action="document_generation.generate.complete",
            resource=task,
            result="success",
            after_data={"status": task.status, "progress": task.progress},
        )
    return "completed"


def _run_fact_extraction(task_id: str) -> str:
    with transaction.atomic():
        task = (
            GenerationTask.objects.select_for_update()
            .select_related("project", "created_by")
            .get(pk=task_id)
        )
        if (
            task.status != GenerationTask.Status.EXTRACTING
            or task.operation != GenerationTask.Operation.EXTRACT
        ):
            return "skipped"
        if task.project.status != task.project.Status.ACTIVE:
            task.status = GenerationTask.Status.FAILED
            task.error_code = "PROJECT_ARCHIVED"
            task.error_message = "项目已归档，任务已停止"
            task.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            return "failed"
        task.generation_attempts += 1
        task.started_at = timezone.now()
        task.error_code = ""
        task.error_message = ""
        task.save(
            update_fields=[
                "generation_attempts",
                "started_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        initial_facts = list(task.facts_snapshot)
    recorder = TaskWorkflowRecorder(task_id)
    try:
        recorder.emit(
            stage="parsing",
            tool="load_source_documents",
            status="started",
        )
        source_documents = _load_source_documents(task_id)
        recorder.emit(
            stage="parsing",
            tool="load_source_documents",
            status="succeeded",
            detail=f"已读取{len(source_documents)}份当前项目资料",
            metadata={"source_count": len(source_documents)},
        )
        parser = EntrySourceParser()
        parsed_documents = tuple(parser.parse(source) for source in source_documents)
        recorder.emit(
            stage="parsing",
            tool="parse_source_document",
            status="succeeded",
            detail=f"已解析{len(parsed_documents)}份资料",
            metadata={"document_count": len(parsed_documents)},
        )
        llm_provider, provider_alias = _build_llm_provider(task.system_prompt_snapshot)
        recorder.emit(
            stage="extracting_facts",
            tool="extract_fact_candidates",
            status="started",
            detail=f"模型：{llm_provider.model_alias}",
            metadata={"model_alias": llm_provider.model_alias},
        )
        if settings.DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:
            candidates = _fake_candidates(initial_facts, parsed_documents)
        else:
            candidates = (
                *llm_provider.extract_facts(parsed_documents),
                *_anchored_initial_candidates(initial_facts, parsed_documents),
            )
        recorder.emit(
            stage="extracting_facts",
            tool="extract_fact_candidates",
            status="succeeded",
            detail=f"识别到{len(candidates)}条候选事实",
            metadata={"candidate_count": len(candidates)},
        )
        candidates = enrich_required_fact_candidates(
            candidates,
            parsed_documents,
            preferred_source_document_version_id=0,
        )
        merged = FactMergeService().merge(candidates)
        recorder.emit(
            stage="validating_facts",
            tool="merge_fact_candidates",
            status="succeeded",
            detail=f"保留{len(merged.merged)}条事实，发现{len(merged.conflicts)}组冲突",
            metadata={
                "fact_count": len(merged.merged),
                "conflict_count": len(merged.conflicts),
                "rejected_count": len(merged.rejected),
            },
        )
    except Exception as exc:
        if _task_is_cancelled(task_id):
            return "cancelled"
        recorder.emit(
            stage="failed",
            tool="stop_workflow",
            status="failed",
            detail=_public_failure_message(exc),
        )
        _record_failure(task_id, exc)
        raise
    proposals = [
        {
            "field": fact.field,
            "value": fact.value,
            "value_type": fact.value_type,
            "evidence": [evidence.model_dump(mode="json") for evidence in fact.evidence],
            "confidence": fact.confidence,
        }
        for fact in merged.merged
    ]
    with transaction.atomic():
        task = (
            GenerationTask.objects.select_for_update().select_related("created_by").get(pk=task_id)
        )
        if (
            task.status != GenerationTask.Status.EXTRACTING
            or task.operation != GenerationTask.Operation.EXTRACT
        ):
            return "superseded"
        task.facts_snapshot = proposals
        task.fact_conflicts = [conflict.model_dump(mode="json") for conflict in merged.conflicts]
        task.status = GenerationTask.Status.NEEDS_CONFIRMATION
        task.progress = 20
        task.provider_alias = provider_alias
        task.model_alias = llm_provider.model_alias
        task.prompt_version = "fact_extraction/v2"
        task.completed_at = timezone.now()
        task.save(
            update_fields=[
                "facts_snapshot",
                "fact_conflicts",
                "status",
                "progress",
                "provider_alias",
                "model_alias",
                "prompt_version",
                "completed_at",
                "updated_at",
            ]
        )
        GenerationSource.objects.filter(task=task).update(
            parse_status=GenerationSource.ParseStatus.PARSED,
            parse_error="",
        )
        audit_log(
            user=task.created_by,
            action="document_generation.facts.extracted",
            resource=task,
            result="success",
            after_data={
                "candidate_count": len(proposals),
                "conflict_count": len(merged.conflicts),
                "rejected_count": len(merged.rejected),
            },
        )
    recorder.emit(
        stage="completed",
        tool="wait_for_fact_confirmation",
        status="succeeded",
        detail="关键事实已整理，等待用户核对后开始逐章编制",
        metadata={
            "fact_count": len(proposals),
            "conflict_count": len(merged.conflicts),
        },
    )
    return "extracted"


def _fake_candidates(
    initial_facts: list[dict[str, object]],
    parsed_documents: tuple[ParsedDocument, ...],
) -> tuple[FactCandidate, ...]:
    if not parsed_documents:
        return ()
    document = parsed_documents[0]
    locator = document.blocks[0].locator
    return tuple(
        FactCandidate(
            field=str(item["field"]),
            value=cast(JsonValue, item.get("value")),
            value_type=str(item.get("value_type", "string")),
            source_document_version_id=document.document_version_id,
            locator=locator,
            confidence=1,
        )
        for item in initial_facts
        if item.get("field")
    )


def _anchored_initial_candidates(
    initial_facts: list[dict[str, object]],
    parsed_documents: tuple[ParsedDocument, ...],
) -> tuple[FactCandidate, ...]:
    anchored: list[FactCandidate] = []
    for item in initial_facts:
        field = str(item.get("field", "")).strip()
        value = cast(JsonValue, item.get("value"))
        if not field or isinstance(value, (dict, list, bool)) or value is None:
            continue
        exact_text = str(value).strip()
        if not exact_text:
            continue
        match = next(
            (
                (document, block)
                for document in parsed_documents
                for block in document.blocks
                if exact_text in block.text
            ),
            None,
        )
        if match is None:
            continue
        document, block = match
        anchored.append(
            FactCandidate(
                field=field,
                value=value,
                value_type=str(item.get("value_type", "string")),
                source_document_version_id=document.document_version_id,
                locator=block.locator,
                confidence=1,
            )
        )
    return tuple(anchored)


def _build_request(task_id: str) -> GenerationRequest:
    task = (
        GenerationTask.objects.select_related("template__document_version")
        .prefetch_related(
            "sources__document_version",
            "sections",
            "reviews__section",
        )
        .get(pk=task_id)
    )
    storage = LocalDocumentStorage()
    sources = _load_source_documents(task_id)
    template_version = task.template.document_version
    template_path = storage.resolve(template_version.storage_path)
    if not template_path.is_file():
        raise AgentError("TEMPLATE_INVALID", "模板物理文件不存在")
    template_content = template_path.read_bytes()
    if hashlib.sha256(template_content).hexdigest() != template_version.sha256:
        raise AgentError("TEMPLATE_INVALID", "模板哈希校验失败")
    facts = tuple(ConfirmedFact.model_validate(value) for value in task.facts_snapshot)
    template_section_order = (
        infer_template_section_order(template_content)
        or tuple(task.template.section_order)
    )
    pending_section_codes = tuple(task.pending_section_codes)
    section_codes = tuple(
        section_code
        for section_code in template_section_order
        if not pending_section_codes or section_code in pending_section_codes
    )
    if not section_codes:
        section_codes = tuple(task.template.section_order)
    force_regenerate_section_codes = (
        section_codes
        if len(section_codes) == 1 and task.sections.filter(section_code=section_codes[0]).exists()
        else ()
    )
    section_revision_instructions: dict[str, str] = {}
    section_revision_conversations: dict[str, tuple[str, ...]] = {}
    section_revision_required_literals: dict[str, tuple[str, ...]] = {}
    section_previous_contents: dict[str, str] = {}
    section_priority_references: dict[str, tuple[RetrievedSection, ...]] = {}
    sections_by_code = {section.section_code: section for section in task.sections.all()}
    for section_code in force_regenerate_section_codes:
        section_reviews = [
            candidate
            for candidate in task.reviews.all()
            if candidate.action == GenerationReview.Action.SECTION_REGENERATED
            and candidate.section is not None
            and candidate.section.section_code == section_code
        ]
        review = next(
            (
                candidate
                for candidate in reversed(section_reviews)
                if (candidate.metadata or {}).get("conversation_status") in {"queued", "processing"}
            ),
            None,
        )
        if review is None:
            continue
        metadata = dict(review.metadata or {})
        requested_chunk_ids = [
            str(chunk_id)
            for chunk_id in metadata.get("requested_rag_chunk_ids", [])
            if str(chunk_id).strip()
        ]
        instruction = review.comment.strip()
        if requested_chunk_ids:
            instruction += "\n重点参照以下已批准RAG片段：" + "、".join(requested_chunk_ids)
            rows = {
                row.chunk_id: row
                for row in KnowledgeSection.objects.filter(
                    chunk_id__in=requested_chunk_ids,
                    business_type=task.business_type,
                    is_active=True,
                    approval_status=ApprovalStatus.APPROVED,
                )
            }
            missing_chunk_ids = [
                chunk_id for chunk_id in requested_chunk_ids if chunk_id not in rows
            ]
            if missing_chunk_ids:
                raise AgentError(
                    "RAG_REFERENCE_UNAVAILABLE",
                    "用户指定的RAG参考已失效，请刷新章节后重新选择",
                    details={"chunk_ids": missing_chunk_ids},
                )
            section_priority_references[section_code] = tuple(
                RetrievedSection(
                    chunk_id=row.chunk_id,
                    source_document_version_id=row.source_document_version_id,
                    section_code=row.section_code,
                    heading_path=tuple(row.heading_path),
                    text=row.text,
                    similarity=1,
                    final_score=1,
                    client_code=row.client_code or None,
                    component_tags=tuple(row.component_tags),
                    method_tags=tuple(row.method_tags),
                    risk_tags=tuple(row.risk_tags),
                )
                for row in (rows[chunk_id] for chunk_id in requested_chunk_ids)
            )
        section_revision_instructions[section_code] = instruction
        required_literals = tuple(
            str(value).strip()
            for value in metadata.get("required_literals", [])
            if str(value).strip()
        ) or revision_required_literals(review.comment)
        if is_revision_followup(review.comment):
            for previous_review in reversed(section_reviews):
                if previous_review.pk == review.pk:
                    continue
                previous_metadata = dict(previous_review.metadata or {})
                previous_literals = tuple(
                    str(value).strip()
                    for value in previous_metadata.get("required_literals", [])
                    if str(value).strip()
                ) or revision_required_literals(previous_review.comment)
                if previous_literals:
                    required_literals = tuple(
                        dict.fromkeys((*previous_literals, *required_literals))
                    )
                    break
        section_revision_required_literals[section_code] = required_literals
        section_revision_conversations[section_code] = tuple(
            (
                f"审核人：{candidate.comment}\n"
                f"Agent：{str((candidate.metadata or {}).get('assistant_message', '')).strip()}"
            ).strip()
            for candidate in section_reviews[-6:]
        )
        existing_section = sections_by_code.get(section_code)
        if existing_section is not None:
            section_previous_contents[section_code] = existing_section.content
    return GenerationRequest(
        request_id=str(task.pk),
        idempotency_key=str(task.pk),
        business_type=task.business_type,
        template=TemplateDocument(
            template_id=str(task.template_id),
            filename=template_version.original_filename,
            content=template_content,
            required_placeholders=tuple(
                task.template.field_mapping.get("required_placeholders", [])
            ),
        ),
        sources=sources,
        confirmed_facts=facts,
        conversation_context=AgentConversationContext.model_validate(
            task.conversation_context or {}
        ),
        required_fact_fields=tuple(task.template.required_fact_fields),
        section_codes=section_codes,
        force_regenerate_section_codes=force_regenerate_section_codes,
        section_revision_instructions=section_revision_instructions,
        section_revision_conversations=section_revision_conversations,
        section_revision_required_literals=section_revision_required_literals,
        section_previous_contents=section_previous_contents,
        section_priority_references=section_priority_references,
    )


def _build_orchestrator(
    task_id: str,
) -> tuple[GenerationOrchestrator, str, str]:
    system_prompt = (
        GenerationTask.objects.filter(pk=task_id)
        .values_list("system_prompt_snapshot", flat=True)
        .first()
        or ""
    )
    llm_provider, provider_alias = _build_llm_provider(system_prompt)
    embedding_provider: EmbeddingProvider
    if settings.DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:
        embedding_provider = HashingEmbeddingProvider()
    else:
        embedding_provider = OpenAICompatibleEmbeddingProvider.from_env()
    retriever = RagRetriever(
        repository=ORMKnowledgeRepository(),  # type: ignore[arg-type]
        embedding_provider=embedding_provider,
    )
    orchestrator = GenerationOrchestrator(
        parser=EntrySourceParser(),
        llm_provider=llm_provider,
        risk_profiler=ORMRiskProfiler(),
        clause_repository=ORMClauseRepository(),
        retriever=retriever,
        section_validator=ControlledSectionValidator(),
        renderer=DocxTemplateRenderer(),
        storage=TaskDraftArtifactStorage(task_id=task_id),
        section_repository=ORMSectionRepository(),
        event_sink=TaskWorkflowRecorder(task_id),
    )
    return orchestrator, provider_alias, llm_provider.model_alias


def _build_llm_provider(system_prompt: str = "") -> tuple[LLMProvider, str]:
    if settings.DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:
        return FakeLLMProvider(), "fake"
    return OpenAICompatibleLLMProvider.from_env(system_prompt=system_prompt), "openai-compatible"


def _load_source_documents(task_id: str) -> tuple[SourceDocument, ...]:
    task = (
        GenerationTask.objects.select_related("project")
        .prefetch_related("sources__document_version")
        .get(pk=task_id)
    )
    storage = LocalDocumentStorage()
    sources: list[SourceDocument] = []
    for source in task.sources.all():
        version = source.document_version
        path = storage.resolve(version.storage_path)
        if not path.is_file():
            raise AgentError("SOURCE_PARSE_FAILED", "来源文档物理文件不存在")
        content = path.read_bytes()
        if (
            hashlib.sha256(content).hexdigest() != version.sha256
            or version.sha256 != source.file_sha256
        ):
            raise AgentError("SOURCE_INTEGRITY_FAILED", "来源文档哈希校验失败")
        sources.append(
            SourceDocument(
                document_version_id=version.pk,
                filename=version.original_filename,
                mime_type=version.content_type or _content_type(version.original_filename),
                content=content,
            )
        )
    prompt_source = prompt_source_document(task)
    if prompt_source is not None:
        sources.append(prompt_source)
    return tuple(sources)


def _validation_failure_context(
    exc: Exception,
) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(exc, AgentError) or exc.code != "VALIDATION_FAILED":
        return "", []
    section_code = str(exc.details.get("section_code", "")).strip()
    issues: list[dict[str, str]] = []
    raw_issues = exc.details.get("issues", [])
    if isinstance(raw_issues, list):
        for raw_issue in raw_issues:
            if not isinstance(raw_issue, Mapping):
                continue
            message = str(raw_issue.get("message", "")).strip()
            if not message:
                continue
            issues.append(
                {
                    "code": str(raw_issue.get("code", "")).strip(),
                    "message": message,
                    "severity": str(raw_issue.get("severity", "error")).strip(),
                }
            )
    return section_code, issues


def _validation_recovery_message(
    exc: Exception,
    *,
    section_code: str,
    issues: list[dict[str, str]],
) -> str:
    issue_summary = "；".join(issue["message"] for issue in issues[:3])
    subject = f"章节 {section_code}" if section_code else "生成章节"
    if not issue_summary and isinstance(exc, AgentError):
        issue_summary = exc.message
    return (
        f"{subject}未通过确定性校验：{issue_summary}。已保留通过校验的章节，可从失败章节继续生成。"
    )[:500]


def _pending_validation_sections(
    task: GenerationTask,
    *,
    failed_section_code: str,
) -> list[str]:
    persisted = {section.section_code: section for section in task.sections.all()}
    pending: list[str] = []
    for section_code in task.template.section_order:
        section = persisted.get(section_code)
        has_blocking_issue = section is not None and any(
            isinstance(issue, Mapping) and issue.get("severity") == "error"
            for issue in (section.validation_issues or [])
        )
        if section is None or not section.content.strip() or has_blocking_issue:
            pending.append(section_code)
    if failed_section_code and failed_section_code not in pending:
        pending.append(failed_section_code)
    return pending


def _record_failure(task_id: str, exc: Exception) -> None:
    current_job = get_current_job()
    retries_left = int(getattr(current_job, "retries_left", 0) or 0)
    error_code = exc.code if isinstance(exc, AgentError) else "GENERATION_FAILED"
    message = _public_failure_message(exc)
    validation_section_code, validation_issues = _validation_failure_context(exc)
    revision_recovery_required = error_code == "VALIDATION_FAILED" and any(
        issue["code"] in {"REVISION_CONTENT_UNCHANGED", "REVISION_LITERAL_MISSING"}
        for issue in validation_issues
    )
    validation_recovery_required = (
        error_code == "VALIDATION_FAILED" and not revision_recovery_required
    )
    with transaction.atomic():
        task = (
            GenerationTask.objects.select_for_update()
            .select_related("created_by", "template")
            .prefetch_related("sections")
            .get(pk=task_id)
        )
        if task.status == GenerationTask.Status.CANCELLED:
            return
        conversation_section_codes = list(task.pending_section_codes)
        evidence_recovery_required = error_code == "FACT_EVIDENCE_INVALID"
        if evidence_recovery_required:
            task.status = GenerationTask.Status.NEEDS_CONFIRMATION
            task.progress = 20
            invalid_fields = sorted(
                {
                    str(field)
                    for field in (
                        exc.details.get("fields", []) if isinstance(exc, AgentError) else []
                    )
                }
            )
            task.fact_conflicts = [
                {"field": field, "reason": "evidence_invalid"} for field in invalid_fields
            ]
            message = "部分项目事实的来源已失效，请重新核对标记项后再次提交"
        elif revision_recovery_required:
            issue_summary = "；".join(
                issue["message"]
                for issue in validation_issues
                if issue["code"] in {"REVISION_CONTENT_UNCHANGED", "REVISION_LITERAL_MISSING"}
            )
            task.status = GenerationTask.Status.REVIEW_REQUIRED
            task.progress = 90
            task.pending_section_codes = []
            message = (
                f"本次修改未能落实到正文：{issue_summary}。原章节已保留，请调整指令后重新发送。"
            )[:500]
        elif validation_recovery_required:
            task.pending_section_codes = _pending_validation_sections(
                task,
                failed_section_code=validation_section_code,
            )
            message = _validation_recovery_message(
                exc,
                section_code=validation_section_code,
                issues=validation_issues,
            )
            task.status = (
                GenerationTask.Status.QUEUED if retries_left > 0 else GenerationTask.Status.FAILED
            )
        elif retries_left > 0:
            task.status = (
                GenerationTask.Status.EXTRACTING
                if task.operation == GenerationTask.Operation.EXTRACT
                else GenerationTask.Status.QUEUED
            )
        else:
            task.status = GenerationTask.Status.FAILED
        task.error_code = error_code
        task.error_message = message
        task.save(
            update_fields=[
                "status",
                "error_code",
                "error_message",
                *(["progress", "fact_conflicts"] if evidence_recovery_required else []),
                *(["progress", "pending_section_codes"] if revision_recovery_required else []),
                *(["pending_section_codes"] if validation_recovery_required else []),
                "updated_at",
            ]
        )
        conversation_status = (
            "failed"
            if revision_recovery_required
            else ("processing" if retries_left > 0 else "failed")
        )
        assistant_message = (
            f"本次修改未完成：{message}"
            if revision_recovery_required
            else "本次修改遇到校验或服务异常，系统正在自动重试。"
            if retries_left > 0
            else f"本次修改未完成：{message}"
        )
        for review in task.reviews.filter(
            action=GenerationReview.Action.SECTION_REGENERATED,
            section__section_code__in=conversation_section_codes,
        ):
            metadata = dict(review.metadata or {})
            if metadata.get("conversation_status") not in {"queued", "processing"}:
                continue
            metadata["conversation_status"] = conversation_status
            metadata["assistant_message"] = assistant_message
            review.metadata = metadata
            review.save(update_fields=["metadata"])
        if error_code in {
            "SOURCE_UNSUPPORTED",
            "SOURCE_PARSE_FAILED",
            "SOURCE_PURPOSE_MISMATCH",
        }:
            GenerationSource.objects.filter(task=task).update(
                parse_status=GenerationSource.ParseStatus.FAILED,
                parse_error=message,
            )
        audit_log(
            user=task.created_by,
            action="document_generation.generate.failed",
            resource=task,
            result="failed",
            error_message=f"{error_code}: {message}",
            after_data={
                "will_retry": retries_left > 0 and not evidence_recovery_required,
                "requires_fact_confirmation": evidence_recovery_required,
                "validation_recovery_sections": (
                    task.pending_section_codes if validation_recovery_required else []
                ),
            },
        )
    if validation_recovery_required or revision_recovery_required:
        TaskWorkflowRecorder(task_id).emit(
            stage="validating_sections",
            tool="validation_recovery_ready",
            status="failed",
            title=(
                "本轮修改未落实，已保留原章节"
                if revision_recovery_required
                else "章节校验未通过，已保留恢复点"
            ),
            detail=message,
            metadata={
                "section_code": validation_section_code,
                "issues": validation_issues,
                "pending_section_codes": task.pending_section_codes,
                "will_retry": retries_left > 0 and not revision_recovery_required,
            },
        )


def _task_is_cancelled(task_id: str) -> bool:
    return GenerationTask.objects.filter(
        pk=task_id,
        status=GenerationTask.Status.CANCELLED,
    ).exists()


def _public_failure_message(exc: Exception) -> str:
    if isinstance(exc, WorkflowExecutionError):
        failed_stage = next(
            (
                event.stage.value
                for event in reversed(exc.trace.events)
                if event.status.value == "failed"
            ),
            "",
        )
        stage_messages = {
            "parsing": "入场前置资料解析失败，请检查文件是否完整且格式受支持",
            "validating_facts": "已确认事实未通过来源校验，请重新核对项目事实",
            "building_risk_profile": "当前项目风险画像构建失败，请重试",
            "selecting_clauses": "已批准条款匹配失败，请重试",
            "retrieving_references": "RAG参考资料检索失败，请检查模型服务后重试",
            "generating_sections": "模型编写章节失败，请检查模型服务后重试",
            "validating_sections": "生成章节未通过确定性校验，请查看工作流详情",
            "rendering": "Word版式渲染失败，请更换模板或联系管理员",
            "storing": "Word草稿保存失败，请检查文件存储后重试",
        }
        return stage_messages.get(failed_stage, exc.message)[:500]
    if isinstance(exc, AgentError):
        return exc.message[:500]
    return "编制任务发生未预期错误，请查看工作流详情或联系管理员"


def _content_type(filename: str) -> str:
    return {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
    }.get(Path(filename).suffix.lower(), "application/octet-stream")
