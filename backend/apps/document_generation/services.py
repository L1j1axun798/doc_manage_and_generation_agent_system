from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import PermissionDenied

from apps.audit.services import audit_log
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import create_document
from apps.folders.defaults import ENTRY_PREPARATION_ROOT_CODE
from apps.folders.models import Folder
from apps.projects.models import Project
from common.storage import LocalDocumentStorage

from .engine.canonical_facts import REQUIRED_FACT_LABELS, validate_required_fact_value
from .engine.contracts import (
    FORBIDDEN_FACT_FIELD_PARTS,
    ConfirmedFact,
    RenderRequest,
    TemplateDocument,
)
from .engine.contracts import (
    GeneratedSection as ContractGeneratedSection,
)
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
from .selectors import visible_source_version_for_user
from .workflow_events import TaskWorkflowRecorder

TECH_SOLUTION_CODE = "PUBLIC-TECH-SOLUTION"
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


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _task_snapshot(task: GenerationTask) -> dict[str, Any]:
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
    if (
        not template.is_active
        or template.approval_status != ApprovalStatus.APPROVED
        or template.business_type != BUSINESS_TYPE
    ):
        raise DocumentGenerationError("TEMPLATE_INVALID", "模板未批准或未启用")
    normalized_facts = _normalize_initial_facts(initial_facts)
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
            actor=actor,
        )
        transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))
        audit_log(
            user=actor,
            action="document_generation.section.regenerate",
            resource=section,
            result="success",
            request=request,
            after_data={"task_id": str(locked.pk)},
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
    folder = Folder.objects.filter(
        project=locked.project,
        code=TECH_SOLUTION_CODE,
        is_active=True,
    ).first()
    if folder is None:
        raise DocumentGenerationError(
            "EXPORT_FOLDER_MISSING",
            "当前项目缺少“技术方案”目录",
        )
    upload = SimpleUploadedFile(
        name=f"{locked.project.code}-四措两案-{str(locked.pk)[:8]}.docx",
        content=artifact.content,
        content_type=artifact.media_type,
    )
    output_document = create_document(
        actor=actor,
        folder=folder,
        uploaded_file=upload,
        title=f"{locked.project.name} 入场四措两案",
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
