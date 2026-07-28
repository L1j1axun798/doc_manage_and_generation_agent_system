from __future__ import annotations

import hashlib
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
from .engine.canonical_facts import enrich_required_fact_candidates
from .engine.contracts import (
    ConfirmedFact,
    FactCandidate,
    GenerationRequest,
    ParsedDocument,
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
from .engine.rag import RagRetriever
from .engine.rendering import DocxTemplateRenderer
from .engine.validation import ControlledSectionValidator
from .models import GenerationSource, GenerationTask
from .providers.embedding import OpenAICompatibleEmbeddingProvider
from .providers.llm import OpenAICompatibleLLMProvider
from .repositories import ORMClauseRepository, ORMKnowledgeRepository, ORMSectionRepository
from .risk import ORMRiskProfiler
from .workflow_events import TaskWorkflowRecorder


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
        GenerationSource.objects.filter(task=task).update(
            parse_status=GenerationSource.ParseStatus.PENDING,
            parse_error="",
        )
    try:
        request = _build_request(task_id)
        orchestrator, provider_alias, model_alias = _build_orchestrator(task_id)
        orchestrator.run(request)
    except Exception as exc:
        _record_failure(task_id, exc)
        raise
    with transaction.atomic():
        task = GenerationTask.objects.select_for_update().get(pk=task_id)
        if task.status != GenerationTask.Status.GENERATING:
            return "superseded"
        task.status = GenerationTask.Status.REVIEW_REQUIRED
        task.progress = 90
        task.provider_alias = provider_alias
        task.model_alias = model_alias
        task.prompt_version = "section_generation/v2"
        task.chunk_rule_version = "phase3-v1"
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
        llm_provider, provider_alias = _build_llm_provider()
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
        candidates = enrich_required_fact_candidates(candidates, parsed_documents)
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
        .prefetch_related("sources__document_version")
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
    section_codes = tuple(task.pending_section_codes or task.template.section_order)
    force_regenerate_section_codes = (
        section_codes
        if len(section_codes) == 1
        and task.sections.filter(section_code=section_codes[0]).exists()
        else ()
    )
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
        required_fact_fields=tuple(task.template.required_fact_fields),
        section_codes=section_codes,
        force_regenerate_section_codes=force_regenerate_section_codes,
    )


def _build_orchestrator(
    task_id: str,
) -> tuple[GenerationOrchestrator, str, str]:
    llm_provider, provider_alias = _build_llm_provider()
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


def _build_llm_provider() -> tuple[LLMProvider, str]:
    if settings.DOCUMENT_AGENT_ALLOW_FAKE_PROVIDER:
        return FakeLLMProvider(), "fake"
    return OpenAICompatibleLLMProvider.from_env(), "openai-compatible"


def _load_source_documents(task_id: str) -> tuple[SourceDocument, ...]:
    task = GenerationTask.objects.prefetch_related("sources__document_version").get(pk=task_id)
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
    return tuple(sources)


def _record_failure(task_id: str, exc: Exception) -> None:
    current_job = get_current_job()
    retries_left = int(getattr(current_job, "retries_left", 0) or 0)
    error_code = exc.code if isinstance(exc, AgentError) else "GENERATION_FAILED"
    message = _public_failure_message(exc)
    with transaction.atomic():
        task = (
            GenerationTask.objects.select_for_update().select_related("created_by").get(pk=task_id)
        )
        if retries_left > 0:
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
                "updated_at",
            ]
        )
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
            after_data={"will_retry": retries_left > 0},
        )


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
