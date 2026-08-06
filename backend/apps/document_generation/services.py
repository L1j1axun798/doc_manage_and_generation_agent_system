from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from pathlib import PurePath
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import PermissionDenied

from apps.audit.services import audit_log
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import create_document
from apps.folders.defaults import ENTRY_PREPARATION_ROOT_CODE
from apps.folders.models import Folder, PersonnelProfile
from apps.folders.personnel import personnel_folders, personnel_profile_for
from apps.projects.models import Project
from common.storage import LocalDocumentStorage

from .engine.canonical_facts import (
    REQUIRED_FACT_LABELS,
    infer_method_codes,
    validate_required_fact_value,
)
from .engine.contracts import (
    ENTRY_PLAN_SECTION_CODES,
    FORBIDDEN_FACT_FIELD_PARTS,
    ConfirmedFact,
    ParsedBlock,
    ParsedDocument,
    RenderRequest,
    SourceDocument,
    SourceLocator,
    TemplateDocument,
)
from .engine.contracts import (
    GeneratedSection as ContractGeneratedSection,
)
from .engine.errors import AgentError
from .engine.facts import FactEvidenceGate
from .engine.parsing import EntrySourceParser
from .engine.rendering import DocxTemplateRenderer
from .exceptions import DocumentGenerationError
from .models import (
    BUSINESS_TYPE,
    DOCUMENT_PURPOSE,
    ApprovalStatus,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationSource,
    GenerationTask,
)
from .permissions import can_review_generation, can_use_generation
from .queues import stop_generation_job
from .revision import revision_required_literals
from .selectors import template_is_available_for_project, visible_source_version_for_user
from .workflow_events import TaskWorkflowRecorder

TECH_SOLUTION_CODE = "PUBLIC-TECH-SOLUTION"
EXPORT_FILE_EXTENSION = ".docx"
EXPORT_FILENAME_FORBIDDEN_CHARS = frozenset('\\/:*?"<>|')
BLOCKED_SOURCE_FOLDER_CODES = {
    "PUBLIC-REPORT-TEMPLATE",
    "PUBLIC-ARCHIVE",
}
BLOCKED_SOURCE_MARKERS = (
    "检测报告",
    "试验报告",
    "验收报告",
    "完工报告",
    "竣工资料",
    "报告模板",
)
CLIENT_TEMPLATE_DESCRIPTION_MARKER = "四措两案 Agent 甲方模板"
ACTIVE_TASK_STATUSES = frozenset(
    {
        GenerationTask.Status.EXTRACTING,
        GenerationTask.Status.QUEUED,
        GenerationTask.Status.GENERATING,
    }
)


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _self_service_template_storage_folder(project: Project) -> tuple[Folder, bool]:
    entry_folder = Folder.objects.filter(
        project=project,
        code=ENTRY_PREPARATION_ROOT_CODE,
        is_active=True,
    ).first()
    if entry_folder is not None:
        return entry_folder, True

    fallback = (
        Folder.objects.filter(project=project, code=TECH_SOLUTION_CODE, is_active=True).first()
        or Folder.objects.filter(project=project, is_active=True)
        .order_by("sort_order", "id")
        .first()
        or Folder.objects.filter(
            project__isnull=True,
            code=TECH_SOLUTION_CODE,
            is_active=True,
        ).first()
    )
    if fallback is None:
        raise DocumentGenerationError(
            "TEMPLATE_STORAGE_UNAVAILABLE",
            "当前没有可用于保存甲方模板的资料目录",
        )
    return fallback, False


def create_self_service_template(
    *,
    actor: Any,
    project: Project,
    uploaded_file: Any,
    request: Any = None,
) -> tuple[DocumentTemplate, bool]:
    original_filename = str(getattr(uploaded_file, "name", "")).strip()
    if PurePath(original_filename).suffix.lower() != ".docx":
        raise DocumentGenerationError("TEMPLATE_INVALID", "甲方模板仅支持 DOCX 文件")
    content = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    try:
        validation = DocxTemplateRenderer().preflight(
            TemplateDocument(
                template_id="self-service-upload",
                filename=original_filename,
                content=content,
            )
        )
    except AgentError as exc:
        raise DocumentGenerationError("TEMPLATE_INVALID", exc.message) from exc
    if not validation.valid:
        raise DocumentGenerationError("TEMPLATE_INVALID", "模板不是可用的 DOCX 文件")

    folder, synced_to_entry = _self_service_template_storage_folder(project)
    document = create_document(
        actor=actor,
        folder=folder,
        uploaded_file=SimpleUploadedFile(
            original_filename,
            content,
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        ),
        title=PurePath(original_filename).stem,
        description=f"{CLIENT_TEMPLATE_DESCRIPTION_MARKER}（用户自主选择，无需审核）。",
        source_type=(
            Document.SourceType.ENTRANCE_MATERIAL
            if synced_to_entry
            else Document.SourceType.PROJECT_UPLOAD
        ),
        request=request,
    )
    template = DocumentTemplate.objects.create(
        code=f"CLIENT-{project.pk}-{uuid.uuid4().hex[:12]}",
        client_name="甲方提供",
        business_type=BUSINESS_TYPE,
        version="自主上传",
        document_version=document.current_version,
        field_mapping={
            "template_name": document.title,
            "source_kind": "client_self_service",
            "self_service": True,
            "project_id": project.pk,
            "required_placeholders": [],
            "privacy_mode": "styles_and_page_setup_only",
        },
        section_order=list(ENTRY_PLAN_SECTION_CODES),
        required_fact_fields=list(REQUIRED_FACT_LABELS),
        is_active=True,
        approval_status=ApprovalStatus.DRAFT,
        created_by=actor,
    )
    audit_log(
        user=actor,
        action="document_generation.template.self_service_create",
        resource=template,
        result="success",
        request=request,
        after_data={
            "project_id": project.pk,
            "document_version_id": document.current_version_id,
            "synced_to_entry": synced_to_entry,
        },
    )
    return template, synced_to_entry


def sync_template_to_project_entry(
    *,
    actor: Any,
    project: Project,
    template: DocumentTemplate,
    request: Any = None,
) -> str:
    entry_folder = Folder.objects.filter(
        project=project,
        code=ENTRY_PREPARATION_ROOT_CODE,
        is_active=True,
    ).first()
    if entry_folder is None:
        return "folder_missing"

    source_version = template.document_version
    source_document = source_version.document
    if source_document.folder_id == entry_folder.pk:
        return "already_present"
    if Document.objects.filter(
        folder=entry_folder,
        deleted_at__isnull=True,
        current_version__sha256=source_version.sha256,
    ).exists():
        return "already_present"

    filename = source_version.original_filename
    title = source_document.title
    if Document.objects.filter(
        folder=entry_folder,
        deleted_at__isnull=True,
    ).filter(Q(title=title) | Q(current_version__original_filename=filename)).exists():
        path = PurePath(filename)
        filename = f"{path.stem}-{template.code}{path.suffix}"
        title = f"{title}-{template.code}"
    storage = LocalDocumentStorage()
    template_path = storage.resolve(source_version.storage_path)
    if not template_path.is_file():
        raise DocumentGenerationError("TEMPLATE_INVALID", "模板物理文件不存在")
    create_document(
        actor=actor,
        folder=entry_folder,
        uploaded_file=SimpleUploadedFile(
            filename,
            template_path.read_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
        ),
        title=title,
        description=f"{CLIENT_TEMPLATE_DESCRIPTION_MARKER}同步副本，请勿作为生成来源资料。",
        source_type=Document.SourceType.ENTRANCE_MATERIAL,
        request=request,
    )
    return "synced"


def _task_snapshot(task: GenerationTask) -> dict[str, Any]:
    personnel = (task.conversation_context or {}).get("personnel", [])
    return {
        "id": str(task.pk),
        "project_id": task.project_id,
        "template_id": task.template_id,
        "document_purpose": task.document_purpose,
        "business_type": task.business_type,
        "status": task.status,
        "operation": task.operation,
        "progress": task.progress,
        "error_code": task.error_code,
        "output_document_version_id": task.output_document_version_id,
        "personnel_count": len(personnel) if isinstance(personnel, list) else 0,
        "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
    }


def _ensure_active_project(project: Project) -> None:
    if project.status != Project.Status.ACTIVE:
        raise DocumentGenerationError(
            "PROJECT_ARCHIVED",
            "项目已归档，不能编制入场资料",
        )


def _ensure_task_user(actor: Any, task: GenerationTask) -> None:
    if not can_use_generation(actor, task.project):
        raise PermissionDenied("无权操作该项目的入场资料编制任务")


def _canonicalize_confirmed_fact_evidence(
    task: GenerationTask,
    facts: list[ConfirmedFact],
) -> list[ConfirmedFact]:
    storage = LocalDocumentStorage()
    source_documents: list[SourceDocument] = []
    for source in task.sources.select_related("document_version").all():
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
        source_documents.append(
            SourceDocument(
                document_version_id=version.pk,
                filename=version.original_filename,
                mime_type=version.content_type or "application/octet-stream",
                content=content,
            )
        )

    parser = EntrySourceParser()
    documents = tuple(parser.parse(source) for source in source_documents)
    documents_by_id = {document.document_version_id: document for document in documents}
    canonicalized: list[ConfirmedFact] = []
    for fact in facts:
        document = documents_by_id.get(fact.source_document_version_id)
        block = _canonical_evidence_block(fact, document) if document is not None else None
        canonicalized.append(
            fact.model_copy(update={"locator": block.locator}) if block is not None else fact
        )
    return list(FactEvidenceGate().validate(canonicalized, documents=documents))


def _canonical_evidence_block(
    fact: ConfirmedFact,
    document: ParsedDocument,
) -> ParsedBlock | None:
    expected = fact.locator

    # Prefer a fully matching structural locator. A model may occasionally return
    # both a paragraph and table index for text that is actually represented by
    # one table block, so a failed exact match is not sufficient to reject the
    # evidence.
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
        if not _block_supports_fact_value(fact, block):
            continue
        return block

    # Fall back to source text only after the structural locator fails. This
    # repairs contradictory paragraph/table metadata while still requiring the
    # quoted text to exist in the selected source document.
    quote = _normalize_evidence_text(expected.text_quote or "")
    if len(quote) >= 6:
        for block in document.blocks:
            block_text = _normalize_evidence_text(block.text)
            if (
                quote in block_text or (len(block_text) >= 6 and block_text in quote)
            ) and _block_supports_fact_value(fact, block):
                return block

    # Detection methods are an enumerated fact. When the model's quote is also
    # shortened or reformatted, infer the selected method codes from the actual
    # parsed source block and only repair the locator if every selected code is
    # explicitly supported there.
    if fact.field == "inspection_method_codes" and isinstance(fact.value, list):
        expected_codes = {str(value).strip().upper() for value in fact.value if str(value).strip()}
        if expected_codes:
            method_blocks = [
                block for block in document.blocks if _block_supports_fact_value(fact, block)
            ]
            if method_blocks:
                return max(
                    method_blocks,
                    key=lambda block: _evidence_locator_similarity(expected, block),
                )
    return None


def _normalize_evidence_text(value: str) -> str:
    return "".join(value.split()).replace("|", "")


def _block_supports_fact_value(fact: ConfirmedFact, block: ParsedBlock) -> bool:
    if fact.field != "inspection_method_codes" or not isinstance(fact.value, list):
        return True
    expected_codes = {str(value).strip().upper() for value in fact.value if str(value).strip()}
    return bool(expected_codes) and expected_codes.issubset(set(infer_method_codes(block.text)))


def _evidence_locator_similarity(expected: SourceLocator, block: ParsedBlock) -> int:
    actual = block.locator
    score = 0
    if expected.table_index is not None and actual.table_index == expected.table_index:
        score += 4
    if expected.paragraph_index is not None and actual.paragraph_index == expected.paragraph_index:
        score += 4
    if expected.page is not None and actual.page == expected.page:
        score += 3
    if expected.heading_path and actual.heading_path == expected.heading_path:
        score += 2
    quote = _normalize_evidence_text(expected.text_quote or "")
    block_text = _normalize_evidence_text(block.text)
    if quote and (quote in block_text or block_text in quote):
        score += 8
    return score


def _fact_evidence_api_error(exc: AgentError) -> DocumentGenerationError:
    if exc.code == "FACT_EVIDENCE_INVALID":
        fields = [
            REQUIRED_FACT_LABELS.get(str(field), str(field))
            for field in exc.details.get("fields", [])
        ]
        suffix = f"：{'、'.join(fields)}" if fields else ""
        return DocumentGenerationError(
            exc.code,
            f"系统已尝试自动修复来源定位，但仍未在所选资料中找到对应依据{suffix}。"
            "请检查该项选择，或重新指定包含原文的来源",
        )
    return DocumentGenerationError(exc.code, exc.message)


def _ensure_review_user(actor: Any, task: GenerationTask) -> None:
    if not can_review_generation(actor, task.project):
        raise PermissionDenied("仅项目负责人或系统管理员可以审核入场资料")


def _ensure_status(task: GenerationTask, allowed: Iterable[str]) -> None:
    allowed_values = set(allowed)
    if task.status not in allowed_values:
        raise DocumentGenerationError(
            "INVALID_TASK_TRANSITION",
            f"当前状态 {task.status} 不允许执行此操作",
            status_code=409,
        )


def _normalize_initial_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(facts):
        field = str(item.get("field", "")).strip().lower()
        if not field:
            raise DocumentGenerationError(
                "FACTS_INCOMPLETE",
                f"第{index + 1}个事实缺少字段名",
            )
        if field in seen:
            raise DocumentGenerationError(
                "FACTS_CONFLICT",
                f"事实字段 {field} 重复",
            )
        if any(part in field for part in FORBIDDEN_FACT_FIELD_PARTS):
            raise DocumentGenerationError(
                "RESULT_CONTENT_FORBIDDEN",
                "入场资料不得包含实测结果、检测结论或完工结果字段",
            )
        seen.add(field)
        normalized.append(
            {
                "field": field,
                "value": item.get("value"),
                "value_type": str(item.get("value_type", "string")).strip() or "string",
            }
        )
    return normalized


def _normalize_conversation_context(
    *,
    project: Project,
    template: DocumentTemplate,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_context = context or {}
    initial_message = str(raw_context.get("initial_message", "")).strip()
    selected_ids = list(dict.fromkeys(raw_context.get("selected_personnel_ids", [])))
    folders = {
        folder.pk: folder
        for folder in personnel_folders().filter(pk__in=selected_ids)
    }
    missing_ids = [personnel_id for personnel_id in selected_ids if personnel_id not in folders]
    if missing_ids:
        raise DocumentGenerationError(
            "PERSONNEL_INVALID",
            "所选人员不在“人员资质”名单中或已停用，请刷新人员列表后重试",
        )
    personnel = []
    for personnel_id in selected_ids:
        folder = folders[personnel_id]
        profile = personnel_profile_for(folder)
        phone = profile.phone if profile else ""
        personnel.append(
            {
                "id": str(folder.pk),
                "name": folder.name.strip(),
                "gender": profile.gender if profile else PersonnelProfile.Gender.UNKNOWN,
                "id_card_number": profile.id_card_number if profile else "",
                "phone": phone,
                "job_title": "",
                "department": "",
                "contact": phone,
                "certifications": [],
                "certificate_valid_until": None,
                "additional_info": {
                    "personnel_folder_id": folder.pk,
                    "profile_complete": bool(
                        profile
                        and profile.gender != PersonnelProfile.Gender.UNKNOWN
                        and profile.id_card_number
                        and profile.phone
                    ),
                },
            }
        )
    return {
        "initial_message": initial_message,
        "personnel": personnel,
        "template": {
            "id": str(template.pk),
            "code": template.code,
            "name": str(template.field_mapping.get("template_name") or template.client_name).strip()
            or template.document_version.original_filename,
            "filename": template.document_version.original_filename,
            "version": template.version,
            "document_version_id": template.document_version_id,
            "format_locked": True,
            "constraints": {
                "preserve_section_order": True,
                "preserve_heading_levels": True,
                "preserve_tables": True,
                "preserve_headers_and_footers": True,
                "preserve_typography_and_numbering": True,
                "fill_only_allowed_positions": True,
            },
        },
    }


@transaction.atomic
def create_generation_task(
    *,
    actor: Any,
    project: Project,
    template: DocumentTemplate,
    document_purpose: str,
    business_type: str,
    idempotency_key: str,
    initial_facts: list[dict[str, Any]],
    conversation_context: dict[str, Any] | None = None,
    request: Any = None,
) -> tuple[GenerationTask, bool]:
    if not can_use_generation(actor, project):
        raise PermissionDenied("无权在该项目中编制入场资料")
    _ensure_active_project(project)
    if document_purpose != DOCUMENT_PURPOSE:
        raise DocumentGenerationError(
            "DOCUMENT_PURPOSE_INVALID",
            "文档用途只能是入场四措两案",
        )
    if business_type != BUSINESS_TYPE:
        raise DocumentGenerationError(
            "BUSINESS_TYPE_INVALID",
            "一期仅支持风电机组检测四措两案编制",
        )
    if not template_is_available_for_project(template, project_id=project.pk):
        raise DocumentGenerationError("TEMPLATE_INVALID", "模板不可用于当前项目")
    normalized_facts = _normalize_initial_facts(initial_facts)
    normalized_context = _normalize_conversation_context(
        project=project,
        template=template,
        context=conversation_context,
    )
    clean_key = idempotency_key.strip()
    if not clean_key:
        raise DocumentGenerationError("IDEMPOTENCY_KEY_REQUIRED", "缺少创建幂等键")
    request_fingerprint = _fingerprint(
        {
            "project_id": project.pk,
            "template_id": template.pk,
            "document_purpose": document_purpose,
            "business_type": business_type,
            "facts": normalized_facts,
            "conversation_context": normalized_context,
        }
    )
    existing = GenerationTask.objects.filter(
        created_by=actor,
        idempotency_key=clean_key,
    ).first()
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise DocumentGenerationError(
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键对应了不同创建参数",
                status_code=409,
            )
        return existing, False
    try:
        task = GenerationTask.objects.create(
            project=project,
            template=template,
            document_purpose=document_purpose,
            business_type=business_type,
            idempotency_key=clean_key,
            request_fingerprint=request_fingerprint,
            conversation_context=normalized_context,
            facts_snapshot=normalized_facts,
            pending_section_codes=list(template.section_order),
            created_by=actor,
        )
    except IntegrityError as exc:
        existing = GenerationTask.objects.get(
            created_by=actor,
            idempotency_key=clean_key,
        )
        if existing.request_fingerprint != request_fingerprint:
            raise DocumentGenerationError(
                "IDEMPOTENCY_CONFLICT",
                "同一幂等键对应了不同创建参数",
                status_code=409,
            ) from exc
        return existing, False
    audit_log(
        user=actor,
        action="document_generation.task.create",
        resource=task,
        result="success",
        request=request,
        after_data=_task_snapshot(task),
    )
    return task, True


@transaction.atomic
def add_generation_sources(
    *,
    actor: Any,
    task: GenerationTask,
    document_version_ids: list[int],
    request: Any = None,
) -> GenerationTask:
    locked = (
        GenerationTask.objects.select_for_update()
        .select_related("project", "template")
        .get(pk=task.pk)
    )
    _ensure_task_user(actor, locked)
    _ensure_active_project(locked.project)
    _ensure_status(locked, {GenerationTask.Status.DRAFT})
    unique_ids = list(dict.fromkeys(document_version_ids))
    if not unique_ids:
        raise DocumentGenerationError("SOURCE_REQUIRED", "至少选择一份已有项目资料")
    for version_id in unique_ids:
        version = visible_source_version_for_user(
            actor,
            project_id=locked.project_id,
            version_id=version_id,
        )
        if version is None:
            raise PermissionDenied("来源文档不存在或当前用户无权查看")
        _ensure_entry_source(version)
        GenerationSource.objects.get_or_create(
            task=locked,
            document_version=version,
            defaults={"file_sha256": version.sha256},
        )
    audit_log(
        user=actor,
        action="document_generation.source.add",
        resource=locked,
        result="success",
        request=request,
        after_data={"document_version_ids": unique_ids},
    )
    return locked


def _ensure_entry_source(version: DocumentVersion) -> None:
    document = version.document
    if (
        version.generation_templates.exists()
        or CLIENT_TEMPLATE_DESCRIPTION_MARKER in document.description
    ):
        raise DocumentGenerationError(
            "SOURCE_PURPOSE_MISMATCH",
            "甲方模板不能同时作为四措两案生成来源资料",
        )
    if document.source_type != Document.SourceType.ENTRANCE_MATERIAL:
        raise DocumentGenerationError(
            "SOURCE_PURPOSE_MISMATCH",
            "只能选择当前项目“入场前置资料”中的文件",
        )

    folder: Folder | None = document.folder
    is_entry_preparation_folder = False
    while folder is not None:
        if folder.code == ENTRY_PREPARATION_ROOT_CODE:
            is_entry_preparation_folder = True
        if folder.code in BLOCKED_SOURCE_FOLDER_CODES or folder.code.startswith("PROJECT-ARCHIVE-"):
            raise DocumentGenerationError(
                "SOURCE_PURPOSE_MISMATCH",
                "报告模板、竣工资料或归档资料不能作为四措两案生成来源",
            )
        folder = folder.parent
    if not is_entry_preparation_folder:
        raise DocumentGenerationError(
            "SOURCE_PURPOSE_MISMATCH",
            "入场前置资料的目录归属不正确",
        )
    names = f"{document.title} {version.original_filename}"
    if any(marker in names for marker in BLOCKED_SOURCE_MARKERS):
        raise DocumentGenerationError(
            "SOURCE_PURPOSE_MISMATCH",
            "明显属于报告或完工成果的文件不能作为生成来源",
        )


def prepare_fact_confirmation(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
) -> GenerationTask:
    from .queues import queue_generation_task

    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        _ensure_active_project(locked.project)
        _ensure_status(locked, {GenerationTask.Status.DRAFT})
        if not locked.sources.exists():
            raise DocumentGenerationError("SOURCE_REQUIRED", "请先选择已有项目资料")
        before = _task_snapshot(locked)
        locked.status = GenerationTask.Status.EXTRACTING
        locked.operation = GenerationTask.Operation.EXTRACT
        locked.progress = 10
        locked.save(update_fields=["status", "operation", "progress", "updated_at"])
        source_count = locked.sources.count()
        TaskWorkflowRecorder(str(locked.pk)).emit(
            stage="initialized",
            tool="queue_fact_extraction",
            status="succeeded",
            detail=f"已选择{source_count}份当前项目入场前置资料",
            metadata={"source_count": source_count},
        )
        transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))
        audit_log(
            user=actor,
            action="document_generation.facts.queue",
            resource=locked,
            result="success",
            request=request,
            before_data=before,
            after_data=_task_snapshot(locked),
        )
    return locked


@transaction.atomic
def start_compilation_pipeline(
    *,
    actor: Any,
    project: Project,
    template: DocumentTemplate,
    document_version_ids: list[int],
    document_purpose: str,
    business_type: str,
    idempotency_key: str,
    initial_facts: list[dict[str, Any]],
    conversation_context: dict[str, Any] | None = None,
    request: Any = None,
) -> tuple[GenerationTask, bool]:
    """Create, bind sources and queue extraction as one database operation."""
    task, created = create_generation_task(
        actor=actor,
        project=project,
        template=template,
        document_purpose=document_purpose,
        business_type=business_type,
        idempotency_key=idempotency_key,
        initial_facts=initial_facts,
        conversation_context=conversation_context,
        request=request,
    )
    if not created and task.status != GenerationTask.Status.DRAFT:
        return task, False
    task = add_generation_sources(
        actor=actor,
        task=task,
        document_version_ids=document_version_ids,
        request=request,
    )
    prepared = prepare_fact_confirmation(
        actor=actor,
        task=task,
        request=request,
    )
    return prepared, created


@transaction.atomic
def confirm_generation_facts(
    *,
    actor: Any,
    task: GenerationTask,
    facts: list[dict[str, Any]],
    request: Any = None,
) -> GenerationTask:
    locked = (
        GenerationTask.objects.select_for_update()
        .select_related("project", "template")
        .get(pk=task.pk)
    )
    _ensure_task_user(actor, locked)
    _ensure_active_project(locked.project)
    _ensure_status(locked, {GenerationTask.Status.NEEDS_CONFIRMATION})
    source_ids = set(locked.sources.values_list("document_version_id", flat=True))
    confirmed: list[ConfirmedFact] = []
    try:
        for item in facts:
            payload = dict(item)
            payload["confirmed_by"] = actor.pk
            fact = ConfirmedFact.model_validate(payload)
            if fact.source_document_version_id not in source_ids:
                raise DocumentGenerationError(
                    "FACT_SOURCE_INVALID",
                    f"事实 {fact.field} 引用了未选择的来源文档",
                )
            if (
                fact.locator.paragraph_index is None
                and fact.locator.table_index is None
                and fact.locator.page is None
                and not fact.locator.text_quote
            ):
                raise DocumentGenerationError(
                    "FACT_SOURCE_INVALID",
                    f"事实 {fact.field} 缺少可核验的页码、段落、表格或引文定位",
                )
            confirmed.append(fact)
    except PydanticValidationError as exc:
        raise DocumentGenerationError(
            "FACTS_INCOMPLETE",
            "确认事实的字段、类型或来源格式不完整",
        ) from exc
    fields = {fact.field for fact in confirmed}
    missing = [field for field in locked.template.required_fact_fields if field not in fields]
    if missing:
        missing_labels = [REQUIRED_FACT_LABELS.get(field, field) for field in missing]
        raise DocumentGenerationError(
            "FACTS_INCOMPLETE",
            f"缺少必填事实：{'、'.join(missing_labels)}",
        )
    invalid_messages = [
        message
        for fact in confirmed
        if fact.field in locked.template.required_fact_fields
        if (message := validate_required_fact_value(fact.field, fact.value)) is not None
    ]
    if invalid_messages:
        raise DocumentGenerationError(
            "FACTS_INVALID",
            "；".join(invalid_messages),
        )
    try:
        confirmed = _canonicalize_confirmed_fact_evidence(locked, confirmed)
    except AgentError as exc:
        raise _fact_evidence_api_error(exc) from exc
    before = _task_snapshot(locked)
    locked.facts_snapshot = [fact.model_dump(mode="json") for fact in confirmed]
    locked.risk_profile = _risk_profile_from_facts(confirmed)
    locked.fact_conflicts = []
    locked.status = GenerationTask.Status.READY
    locked.progress = 30
    locked.error_code = ""
    locked.error_message = ""
    locked.save(
        update_fields=[
            "facts_snapshot",
            "risk_profile",
            "fact_conflicts",
            "status",
            "progress",
            "error_code",
            "error_message",
            "updated_at",
        ]
    )
    GenerationReview.objects.create(
        task=locked,
        action=GenerationReview.Action.FACTS_CONFIRMED,
        actor=actor,
    )
    audit_log(
        user=actor,
        action="document_generation.facts.confirm",
        resource=locked,
        result="success",
        request=request,
        before_data=before,
        after_data=_task_snapshot(locked),
    )
    return locked


@transaction.atomic
def confirm_and_request_generation(
    *,
    actor: Any,
    task: GenerationTask,
    facts: list[dict[str, Any]],
    request: Any = None,
) -> GenerationTask:
    confirmed = confirm_generation_facts(
        actor=actor,
        task=task,
        facts=facts,
        request=request,
    )
    return request_generation(
        actor=actor,
        task=confirmed,
        request=request,
    )


def _risk_profile_from_facts(facts: list[ConfirmedFact]) -> dict[str, Any]:
    risk_codes: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for fact in facts:
        if fact.field != "risk_evidence_items" or not isinstance(fact.value, list):
            continue
        for item in fact.value:
            if not isinstance(item, dict):
                continue
            risk_code = item.get("risk_code")
            explanation = item.get("evidence")
            if isinstance(risk_code, str) and risk_code.strip():
                risk_codes.add(risk_code.strip())
                evidence.append(
                    {
                        "risk_code": risk_code.strip(),
                        "evidence": str(explanation or "").strip(),
                        "source_document_version_id": fact.source_document_version_id,
                        "locator": fact.locator.model_dump(mode="json"),
                    }
                )
    return {"risk_codes": sorted(risk_codes), "evidence": evidence}


def request_generation(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
) -> GenerationTask:
    from .queues import queue_generation_task

    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        _ensure_active_project(locked.project)
        _ensure_status(locked, {GenerationTask.Status.READY})
        before = _task_snapshot(locked)
        locked.status = GenerationTask.Status.QUEUED
        locked.operation = GenerationTask.Operation.GENERATE
        locked.progress = 35
        locked.completed_at = None
        locked.error_code = ""
        locked.error_message = ""
        locked.save(
            update_fields=[
                "status",
                "operation",
                "progress",
                "completed_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))
        audit_log(
            user=actor,
            action="document_generation.generate.queue",
            resource=locked,
            result="success",
            request=request,
            before_data=before,
            after_data=_task_snapshot(locked),
        )
    return locked


def retry_generation_task(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
) -> GenerationTask:
    from .queues import queue_generation_task

    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        _ensure_active_project(locked.project)
        _ensure_status(locked, {GenerationTask.Status.FAILED})
        if locked.operation == GenerationTask.Operation.GENERATE and (
            not locked.facts_snapshot or not locked.sources.exists()
        ):
            raise DocumentGenerationError(
                "FACTS_INCOMPLETE",
                "任务缺少已确认事实或来源，不能重试",
            )
        before = _task_snapshot(locked)
        recovered_fact_evidence = False
        if (
            locked.operation == GenerationTask.Operation.GENERATE
            and locked.error_code == "FACT_EVIDENCE_INVALID"
        ):
            try:
                confirmed = [ConfirmedFact.model_validate(value) for value in locked.facts_snapshot]
                confirmed = _canonicalize_confirmed_fact_evidence(locked, confirmed)
            except PydanticValidationError as exc:
                raise DocumentGenerationError(
                    "FACTS_INCOMPLETE",
                    "已确认事实格式不完整，请重新核对项目事实",
                ) from exc
            except AgentError as exc:
                if exc.code != "FACT_EVIDENCE_INVALID":
                    raise _fact_evidence_api_error(exc) from exc
                invalid_fields = sorted({str(field) for field in exc.details.get("fields", [])})
                locked.status = GenerationTask.Status.NEEDS_CONFIRMATION
                locked.progress = 20
                locked.fact_conflicts = [
                    {"field": field, "reason": "evidence_invalid"} for field in invalid_fields
                ]
                locked.error_message = "部分项目事实的来源已失效，请重新核对标记项后再次提交"
                locked.save(
                    update_fields=[
                        "status",
                        "progress",
                        "fact_conflicts",
                        "error_message",
                        "updated_at",
                    ]
                )
                GenerationReview.objects.create(
                    task=locked,
                    action=GenerationReview.Action.RETRIED,
                    actor=actor,
                    comment="来源证据无法自动修复，已回退到人工事实核对",
                )
                audit_log(
                    user=actor,
                    action="document_generation.facts.recovery_required",
                    resource=locked,
                    result="success",
                    request=request,
                    before_data=before,
                    after_data=_task_snapshot(locked),
                )
                return locked
            locked.facts_snapshot = [fact.model_dump(mode="json") for fact in confirmed]
            locked.fact_conflicts = []
            recovered_fact_evidence = True
        locked.status = (
            GenerationTask.Status.EXTRACTING
            if locked.operation == GenerationTask.Operation.EXTRACT
            else GenerationTask.Status.QUEUED
        )
        locked.progress = 10 if locked.operation == GenerationTask.Operation.EXTRACT else 35
        locked.completed_at = None
        locked.error_code = ""
        locked.error_message = ""
        locked.save(
            update_fields=[
                "status",
                "progress",
                "completed_at",
                "error_code",
                "error_message",
                *(["facts_snapshot", "fact_conflicts"] if recovered_fact_evidence else []),
                "updated_at",
            ]
        )
        GenerationReview.objects.create(
            task=locked,
            action=GenerationReview.Action.RETRIED,
            actor=actor,
        )
        transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))
        audit_log(
            user=actor,
            action="document_generation.generate.retry",
            resource=locked,
            result="success",
            request=request,
            before_data=before,
            after_data=_task_snapshot(locked),
        )
    return locked


def stop_generation_task(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
) -> GenerationTask:
    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        _ensure_status(locked, ACTIVE_TASK_STATUSES)
        before = _task_snapshot(locked)
        locked.status = GenerationTask.Status.CANCELLED
        locked.completed_at = timezone.now()
        locked.error_code = ""
        locked.error_message = ""
        locked.save(
            update_fields=[
                "status",
                "completed_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        GenerationReview.objects.create(
            task=locked,
            action=GenerationReview.Action.STOPPED,
            actor=actor,
            comment="用户主动停止编制会话",
        )
        audit_log(
            user=actor,
            action="document_generation.task.stop",
            resource=locked,
            result="success",
            request=request,
            before_data=before,
            after_data=_task_snapshot(locked),
        )
        transaction.on_commit(
            lambda: _finish_stopping_generation_task(str(locked.pk)),
            robust=True,
        )
    return locked


def delete_generation_task(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> None:
    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        if locked.status in ACTIVE_TASK_STATUSES:
            raise DocumentGenerationError(
                "TASK_STILL_RUNNING",
                "会话仍在执行，请先停止会话后再删除",
                status_code=409,
            )
        if locked.deleted_at is not None:
            return
        before = _task_snapshot(locked)
        draft_storage_path = locked.draft_storage_path
        locked.deleted_at = timezone.now()
        locked.deleted_by = actor
        locked.save(update_fields=["deleted_at", "deleted_by", "updated_at"])
        audit_log(
            user=actor,
            action="document_generation.task.delete",
            resource=locked,
            result="success",
            request=request,
            before_data=before,
            after_data={
                "deleted_at": locked.deleted_at.isoformat(),
                "output_document_version_preserved": locked.output_document_version_id,
            },
        )
        if draft_storage_path:
            backend = storage or LocalDocumentStorage()
            transaction.on_commit(
                lambda: backend.delete(draft_storage_path),
                robust=True,
            )


def _finish_stopping_generation_task(task_id: str) -> None:
    try:
        TaskWorkflowRecorder(task_id).emit(
            stage="cancelled",
            tool="cancel_generation_task",
            status="succeeded",
            detail="用户主动停止，会话不会继续生成或进入审核",
        )
    finally:
        stop_generation_job(task_id)


@transaction.atomic
def edit_generated_section(
    *,
    actor: Any,
    task: GenerationTask,
    section_code: str,
    content: str,
    expected_revision: int,
    request: Any = None,
) -> GeneratedSection:
    locked_task = (
        GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
    )
    _ensure_task_user(actor, locked_task)
    _ensure_status(locked_task, {GenerationTask.Status.REVIEW_REQUIRED})
    section = GeneratedSection.objects.select_for_update().get(
        task=locked_task,
        section_code=section_code,
    )
    if section.is_locked:
        raise DocumentGenerationError("SECTION_LOCKED", "章节已锁定，不能修改", status_code=409)
    if section.revision != expected_revision:
        raise DocumentGenerationError(
            "SECTION_REVISION_CONFLICT",
            "章节已被其他操作更新，请刷新后重试",
            status_code=409,
        )
    clean_content = content.strip()
    if not clean_content:
        raise DocumentGenerationError("SECTION_EMPTY", "章节正文不能为空")
    section.content = clean_content
    section.revision += 1
    section.save(update_fields=["content", "revision", "updated_at"])
    GenerationReview.objects.create(
        task=locked_task,
        section=section,
        action=GenerationReview.Action.SECTION_EDITED,
        actor=actor,
        metadata={"revision": section.revision},
    )
    audit_log(
        user=actor,
        action="document_generation.section.edit",
        resource=section,
        result="success",
        request=request,
        after_data={"revision": section.revision, "task_id": str(locked_task.pk)},
    )
    return section


@transaction.atomic
def set_section_lock(
    *,
    actor: Any,
    task: GenerationTask,
    section_code: str,
    locked: bool,
    request: Any = None,
) -> GeneratedSection:
    locked_task = (
        GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
    )
    _ensure_task_user(actor, locked_task)
    _ensure_status(locked_task, {GenerationTask.Status.REVIEW_REQUIRED})
    section = GeneratedSection.objects.select_for_update().get(
        task=locked_task,
        section_code=section_code,
    )
    section.is_locked = locked
    section.save(update_fields=["is_locked", "updated_at"])
    action = (
        GenerationReview.Action.SECTION_LOCKED
        if locked
        else GenerationReview.Action.SECTION_UNLOCKED
    )
    GenerationReview.objects.create(
        task=locked_task,
        section=section,
        action=action,
        actor=actor,
    )
    audit_log(
        user=actor,
        action=f"document_generation.section.{'lock' if locked else 'unlock'}",
        resource=section,
        result="success",
        request=request,
        after_data={"is_locked": locked, "task_id": str(locked_task.pk)},
    )
    return section


def request_section_regeneration(
    *,
    actor: Any,
    task: GenerationTask,
    section_code: str,
    instruction: str,
    rag_chunk_ids: list[str] | None = None,
    request: Any = None,
) -> GenerationTask:
    from .queues import queue_generation_task

    with transaction.atomic():
        locked = (
            GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
        )
        _ensure_task_user(actor, locked)
        _ensure_active_project(locked.project)
        _ensure_status(locked, {GenerationTask.Status.REVIEW_REQUIRED})
        section = GeneratedSection.objects.select_for_update().get(
            task=locked,
            section_code=section_code,
        )
        if section.is_locked:
            raise DocumentGenerationError(
                "SECTION_LOCKED",
                "章节已锁定，不能重新生成",
                status_code=409,
            )
        clean_instruction = instruction.strip()
        if not clean_instruction:
            raise DocumentGenerationError(
                "REVISION_INSTRUCTION_REQUIRED",
                "请输入本章的修改要求",
                status_code=400,
            )
        requested_rag_chunk_ids = list(dict.fromkeys(rag_chunk_ids or []))
        required_literals = revision_required_literals(clean_instruction)
        available_rag_chunk_ids = {
            str(citation.get("chunk_id", "")).strip()
            for citation in section.citations
            if isinstance(citation, dict) and citation.get("chunk_id")
        }
        unavailable_rag_chunk_ids = sorted(set(requested_rag_chunk_ids) - available_rag_chunk_ids)
        if unavailable_rag_chunk_ids:
            raise DocumentGenerationError(
                "RAG_REFERENCE_INVALID",
                "所选RAG参考不属于本章当前已批准引用，请刷新后重试",
                status_code=400,
            )
        locked.pending_section_codes = [section_code]
        locked.status = GenerationTask.Status.QUEUED
        locked.operation = GenerationTask.Operation.GENERATE
        locked.progress = 35
        locked.save(
            update_fields=[
                "pending_section_codes",
                "status",
                "operation",
                "progress",
                "updated_at",
            ]
        )
        GenerationReview.objects.create(
            task=locked,
            section=section,
            action=GenerationReview.Action.SECTION_REGENERATED,
            comment=clean_instruction,
            metadata={
                "conversation_status": "queued",
                "assistant_message": (
                    "已收到修改要求，正在结合当前项目事实和已批准RAG重新生成本章。"
                ),
                "requested_rag_chunk_ids": requested_rag_chunk_ids,
                "required_literals": required_literals,
                "revision_before": section.revision,
            },
            actor=actor,
        )
        transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))
        audit_log(
            user=actor,
            action="document_generation.section.regenerate",
            resource=section,
            result="success",
            request=request,
            after_data={
                "task_id": str(locked.pk),
                "instruction_length": len(clean_instruction),
                "rag_reference_count": len(requested_rag_chunk_ids),
                "required_literal_count": len(required_literals),
            },
        )
    return locked


@transaction.atomic
def lock_all_valid_sections(
    *,
    actor: Any,
    task: GenerationTask,
    request: Any = None,
) -> GenerationTask:
    locked = GenerationTask.objects.select_for_update().select_related("project").get(pk=task.pk)
    _ensure_task_user(actor, locked)
    _ensure_status(locked, {GenerationTask.Status.REVIEW_REQUIRED})
    sections = list(locked.sections.select_for_update())
    blocking = [
        section.title
        for section in sections
        if any(
            isinstance(issue, dict) and issue.get("severity") == "error"
            for issue in section.validation_issues
        )
    ]
    if blocking:
        raise DocumentGenerationError(
            "SECTION_VALIDATION_FAILED",
            f"以下章节仍有阻断错误：{'、'.join(blocking)}",
            status_code=409,
        )
    GeneratedSection.objects.filter(task=locked).update(is_locked=True)
    GenerationReview.objects.create(
        task=locked,
        action=GenerationReview.Action.SECTION_LOCKED,
        actor=actor,
        metadata={"section_codes": [section.section_code for section in sections]},
    )
    audit_log(
        user=actor,
        action="document_generation.sections.lock_all",
        resource=locked,
        result="success",
        request=request,
        after_data={"section_count": len(sections)},
    )
    return locked


@transaction.atomic
def submit_generation_review(
    *,
    actor: Any,
    task: GenerationTask,
    comment: str = "",
    request: Any = None,
) -> GenerationTask:
    locked = (
        GenerationTask.objects.select_for_update()
        .select_related("project", "template")
        .get(pk=task.pk)
    )
    _ensure_task_user(actor, locked)
    _ensure_active_project(locked.project)
    _ensure_status(locked, {GenerationTask.Status.REVIEW_REQUIRED})
    sections = list(locked.sections.all())
    expected = set(locked.template.section_order)
    actual = {section.section_code for section in sections}
    if expected != actual or any(not section.is_locked for section in sections):
        raise DocumentGenerationError(
            "REVIEW_INCOMPLETE",
            "请先确认并锁定全部章节，再提交技术负责人批准",
        )
    locked.status = GenerationTask.Status.PENDING_APPROVAL
    locked.save(update_fields=["status", "updated_at"])
    GenerationReview.objects.create(
        task=locked,
        action=GenerationReview.Action.SUBMITTED,
        comment=comment.strip(),
        actor=actor,
    )
    audit_log(
        user=actor,
        action="document_generation.review.submit",
        resource=locked,
        result="success",
        request=request,
        after_data=_task_snapshot(locked),
    )
    return locked


@transaction.atomic
def approve_generation_task(
    *,
    actor: Any,
    task: GenerationTask,
    comment: str = "",
    request: Any = None,
) -> GenerationTask:
    locked = (
        GenerationTask.objects.select_for_update()
        .select_related("project", "template")
        .get(pk=task.pk)
    )
    _ensure_review_user(actor, locked)
    _ensure_active_project(locked.project)
    _ensure_status(locked, {GenerationTask.Status.PENDING_APPROVAL})
    sections = list(locked.sections.all())
    expected = set(locked.template.section_order)
    actual = {section.section_code for section in sections}
    if expected - actual:
        raise DocumentGenerationError(
            "SECTIONS_INCOMPLETE",
            "生成章节不完整，不能批准",
        )
    if any(not section.is_locked for section in sections):
        raise DocumentGenerationError(
            "SECTIONS_NOT_LOCKED",
            "批准前必须逐章确认并锁定",
        )
    if any(
        issue.get("severity") == "error"
        for section in sections
        for issue in section.validation_issues
        if isinstance(issue, dict)
    ):
        raise DocumentGenerationError(
            "VALIDATION_FAILED",
            "仍有错误级校验问题，不能批准",
        )
    before = _task_snapshot(locked)
    locked.status = GenerationTask.Status.APPROVED
    locked.progress = 95
    locked.reviewed_by = actor
    locked.approved_at = timezone.now()
    locked.save(
        update_fields=[
            "status",
            "progress",
            "reviewed_by",
            "approved_at",
            "updated_at",
        ]
    )
    GenerationReview.objects.create(
        task=locked,
        action=GenerationReview.Action.APPROVED,
        comment=comment.strip(),
        actor=actor,
    )
    audit_log(
        user=actor,
        action="document_generation.review.approve",
        resource=locked,
        result="success",
        request=request,
        before_data=before,
        after_data=_task_snapshot(locked),
    )
    return locked


@transaction.atomic
def export_generation_task(
    *,
    actor: Any,
    task: GenerationTask,
    idempotency_key: str,
    filename: str | None = None,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> GenerationTask:
    locked = (
        GenerationTask.objects.select_for_update()
        .select_related(
            "project",
            "template__document_version",
            "template__document_version__document",
            "output_document_version",
        )
        .get(pk=task.pk)
    )
    _ensure_review_user(actor, locked)
    _ensure_active_project(locked.project)
    clean_key = idempotency_key.strip()
    if not clean_key:
        raise DocumentGenerationError("IDEMPOTENCY_KEY_REQUIRED", "缺少导出幂等键")
    if locked.status == GenerationTask.Status.EXPORTED:
        if locked.export_idempotency_key != clean_key:
            raise DocumentGenerationError(
                "IDEMPOTENCY_CONFLICT",
                "任务已使用其他幂等键导出",
                status_code=409,
            )
        return locked
    _ensure_status(locked, {GenerationTask.Status.APPROVED})
    folder = _generation_export_folder(locked)
    export_filename = _normalize_export_filename(locked, filename)
    export_title = export_filename[: -len(EXPORT_FILE_EXTENSION)]
    existing_name = Document.objects.filter(
        folder=folder,
        deleted_at__isnull=True,
    ).filter(Q(title=export_title) | Q(current_version__original_filename=export_filename))
    if existing_name.exists():
        agent_count = _agent_generated_document_count(folder)
        raise DocumentGenerationError(
            "EXPORT_NAME_CONFLICT",
            (
                f"当前“技术方案”目录已有 {agent_count} 份 Agent 生成文件，"
                f"并且已存在同名文件“{export_filename}”，请修改文件名后重试。"
            ),
            status_code=409,
        )
    template_version = locked.template.document_version
    backend = storage or LocalDocumentStorage()
    template_path = backend.resolve(template_version.storage_path)
    if not template_path.is_file():
        raise DocumentGenerationError("TEMPLATE_INVALID", "模板物理文件不存在")
    try:
        confirmed_facts = tuple(
            ConfirmedFact.model_validate(value) for value in locked.facts_snapshot
        )
        rendered_sections = tuple(_section_for_export(section) for section in locked.sections.all())
        artifact = DocxTemplateRenderer().render(
            RenderRequest(
                template=TemplateDocument(
                    template_id=str(locked.template_id),
                    filename=template_version.original_filename,
                    content=template_path.read_bytes(),
                    required_placeholders=tuple(
                        locked.template.field_mapping.get("required_placeholders", [])
                    ),
                ),
                facts=confirmed_facts,
                sections=rendered_sections,
            )
        )
    except DocumentGenerationError:
        raise
    except Exception as exc:
        raise DocumentGenerationError("EXPORT_FAILED", "Word文档渲染失败") from exc
    upload = SimpleUploadedFile(
        name=export_filename,
        content=artifact.content,
        content_type=artifact.media_type,
    )
    output_document = create_document(
        actor=actor,
        folder=folder,
        uploaded_file=upload,
        title=export_title,
        description="由入场资料编制Agent生成并经人工审核批准；不是检测报告或完工报告。",
        access_level=Document.AccessLevel.INTERNAL,
        request=request,
        storage=backend,
    )
    before = _task_snapshot(locked)
    locked.status = GenerationTask.Status.EXPORTED
    locked.progress = 100
    locked.output_document_version = output_document.current_version
    locked.export_idempotency_key = clean_key
    locked.save(
        update_fields=[
            "status",
            "progress",
            "output_document_version",
            "export_idempotency_key",
            "updated_at",
        ]
    )
    GenerationReview.objects.create(
        task=locked,
        action=GenerationReview.Action.EXPORTED,
        actor=actor,
        metadata={"document_version_id": locked.output_document_version_id},
    )
    audit_log(
        user=actor,
        action="document_generation.export",
        resource=locked,
        result="success",
        request=request,
        before_data=before,
        after_data=_task_snapshot(locked),
    )
    return locked


def generation_export_info(task: GenerationTask) -> dict[str, Any]:
    folder = _generation_export_folder(task)
    return {
        "target_folder": folder.name,
        "agent_generated_count": _agent_generated_document_count(folder),
        "default_filename": _normalize_export_filename(task, None),
    }


def _generation_export_folder(task: GenerationTask) -> Folder:
    folder = Folder.objects.filter(
        project=task.project,
        code=TECH_SOLUTION_CODE,
        is_active=True,
    ).first()
    if folder is None:
        raise DocumentGenerationError(
            "EXPORT_FOLDER_MISSING",
            "当前项目缺少“技术方案”目录",
        )
    return folder


def _agent_generated_document_count(folder: Folder) -> int:
    return GenerationTask.objects.filter(
        status=GenerationTask.Status.EXPORTED,
        output_document_version__document__folder=folder,
        output_document_version__document__deleted_at__isnull=True,
    ).count()


def _normalize_export_filename(
    task: GenerationTask,
    filename: str | None,
) -> str:
    default_suffix = f" 入场四措两案-{str(task.pk)[:8]}"
    default_project_name = "".join(
        "-" if char in EXPORT_FILENAME_FORBIDDEN_CHARS or ord(char) < 32 else char
        for char in task.project.name.strip()
    )
    default_stem = f"{default_project_name[: 250 - len(default_suffix)]}{default_suffix}"
    clean_name = filename.strip() if filename is not None else default_stem
    if clean_name.lower().endswith(EXPORT_FILE_EXTENSION):
        clean_name = clean_name[: -len(EXPORT_FILE_EXTENSION)].strip()
    if not clean_name:
        raise DocumentGenerationError("EXPORT_FILENAME_REQUIRED", "请输入导出文件名")
    if (
        clean_name in {".", ".."}
        or clean_name.endswith(".")
        or any(char in EXPORT_FILENAME_FORBIDDEN_CHARS for char in clean_name)
        or any(ord(char) < 32 for char in clean_name)
    ):
        raise DocumentGenerationError(
            "EXPORT_FILENAME_INVALID",
            '文件名不能包含 \\ / : * ? " < > |，也不能以句点结尾',
        )
    export_filename = f"{clean_name}{EXPORT_FILE_EXTENSION}"
    if len(export_filename) > 255:
        raise DocumentGenerationError(
            "EXPORT_FILENAME_TOO_LONG",
            "导出文件名不能超过255个字符",
        )
    return export_filename


def _section_for_export(section: GeneratedSection) -> ContractGeneratedSection:
    try:
        original = ContractGeneratedSection.model_validate(section.structured_content)
    except PydanticValidationError:
        original = ContractGeneratedSection(
            section_code=section.section_code,
            title=section.title,
        )
    paragraphs = tuple(line.strip() for line in section.content.splitlines() if line.strip())
    return original.model_copy(
        update={
            "title": section.title,
            "paragraphs": paragraphs,
            "lists": (),
            "tables": (),
        }
    )
