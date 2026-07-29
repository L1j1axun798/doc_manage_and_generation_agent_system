from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from redis.exceptions import ConnectionError as RedisConnectionError

from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from apps.projects.models import Project

from ..engine.errors import AgentError
from ..exceptions import DocumentGenerationError
from ..jobs import _record_failure
from ..models import (
    ApprovalStatus,
    DocumentTemplate,
    GeneratedSection,
    GenerationTask,
    GenerationTraceEvent,
)
from ..queues import queue_generation_task, stop_generation_job
from ..recovery import recover_generation_tasks

User = get_user_model()


def make_task(status: str) -> GenerationTask:
    admin = User.objects.create_user(
        username=f"admin-{status}",
        password="Password123!",
        real_name="admin",
        role=User.Role.SYSTEM_ADMIN,
    )
    project = Project.objects.create(name="项目", code=f"P-{status}", created_by=admin)
    folder = Folder.objects.create(project=project, name="技术方案", created_by=admin)
    document = Document.objects.create(
        project=project,
        folder=folder,
        title="模板",
        created_by=admin,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="template.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=1,
        sha256="0" * 64,
        storage_path=f"{status}.bin",
        uploaded_by=admin,
    )
    template = DocumentTemplate.objects.create(
        code=f"T-{status}",
        version="v1",
        document_version=version,
        section_order=["overview"],
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
        approved_by=admin,
        created_by=admin,
    )
    return GenerationTask.objects.create(
        project=project,
        template=template,
        status=status,
        idempotency_key=f"idem-{status}",
        request_fingerprint="1" * 64,
        created_by=admin,
    )


class FakeJob:
    def __init__(self, status="finished"):
        self.status = status
        self.cancelled = False

    def get_status(self, refresh=True):
        return self.status

    def delete(self):
        return None

    def cancel(self):
        self.cancelled = True


class FakeQueue:
    def __init__(self):
        self.args = None
        self.connection = object()
        self.job = FakeJob()

    def fetch_job(self, job_id):
        return self.job

    def enqueue(self, function, *args, **kwargs):
        self.args = (function, args, kwargs)
        return "job"


@pytest.mark.django_db
def test_queue_payload_contains_only_task_uuid(monkeypatch):
    task = make_task(GenerationTask.Status.QUEUED)
    queue = FakeQueue()
    monkeypatch.setattr("apps.document_generation.queues.django_rq.get_queue", lambda name: queue)

    result = queue_generation_task(str(task.pk))

    assert result == "job"
    function, args, kwargs = queue.args
    assert function == "apps.document_generation.jobs.run_generation_task"
    assert args == (str(task.pk),)
    assert kwargs["job_id"] == str(task.pk)


def test_stop_generation_job_signals_started_rq_job(monkeypatch):
    queue = FakeQueue()
    queue.job = FakeJob(status="started")
    signals: list[tuple[object, str]] = []
    monkeypatch.setattr("apps.document_generation.queues.django_rq.get_queue", lambda name: queue)
    monkeypatch.setattr(
        "apps.document_generation.queues.send_stop_job_command",
        lambda connection, job_id: signals.append((connection, job_id)),
    )

    result = stop_generation_job("task-1")

    assert result == "stop_requested"
    assert signals == [(queue.connection, "task-1")]


def test_stop_generation_job_cancels_queued_rq_job(monkeypatch):
    queue = FakeQueue()
    queue.job = FakeJob(status="queued")
    monkeypatch.setattr("apps.document_generation.queues.django_rq.get_queue", lambda name: queue)

    result = stop_generation_job("task-1")

    assert result == "cancelled"
    assert queue.job.cancelled is True


@pytest.mark.django_db
def test_redis_failure_marks_only_generation_task_failed(monkeypatch):
    task = make_task(GenerationTask.Status.QUEUED)
    monkeypatch.setattr(
        "apps.document_generation.queues.django_rq.get_queue",
        lambda name: (_ for _ in ()).throw(RedisConnectionError("down")),
    )

    with pytest.raises(DocumentGenerationError) as captured:
        queue_generation_task(str(task.pk))

    task.refresh_from_db()
    assert captured.value.default_code == "QUEUE_UNAVAILABLE"
    assert task.status == GenerationTask.Status.FAILED
    assert task.error_code == "QUEUE_UNAVAILABLE"


@pytest.mark.django_db
def test_invalid_fact_evidence_falls_back_to_human_confirmation(monkeypatch):
    task = make_task(GenerationTask.Status.GENERATING)
    task.operation = GenerationTask.Operation.GENERATE
    task.progress = 45
    task.save(update_fields=["operation", "progress", "updated_at"])
    monkeypatch.setattr("apps.document_generation.jobs.get_current_job", lambda: None)

    _record_failure(
        str(task.pk),
        AgentError(
            "FACT_EVIDENCE_INVALID",
            "来源定位不存在",
            details={"fields": ["work_scope"]},
        ),
    )

    task.refresh_from_db()
    assert task.status == GenerationTask.Status.NEEDS_CONFIRMATION
    assert task.progress == 20
    assert task.error_code == "FACT_EVIDENCE_INVALID"
    assert task.fact_conflicts == [{"field": "work_scope", "reason": "evidence_invalid"}]


@pytest.mark.django_db
def test_cancelled_task_is_not_overwritten_by_late_worker_failure(monkeypatch):
    task = make_task(GenerationTask.Status.CANCELLED)
    monkeypatch.setattr("apps.document_generation.jobs.get_current_job", lambda: None)

    _record_failure(
        str(task.pk),
        AgentError("WORKFLOW_FAILED", "模型请求返回时会话已经停止"),
    )

    task.refresh_from_db()
    assert task.status == GenerationTask.Status.CANCELLED
    assert task.error_code == ""
    assert task.error_message == ""


@pytest.mark.django_db
def test_validation_failure_preserves_valid_sections_and_exposes_recovery(monkeypatch):
    task = make_task(GenerationTask.Status.GENERATING)
    task.operation = GenerationTask.Operation.GENERATE
    task.progress = 78
    task.template.section_order = ["overview", "risk_identification", "emergency_plan"]
    task.template.save(update_fields=["section_order", "updated_at"])
    task.save(update_fields=["operation", "progress", "updated_at"])
    GeneratedSection.objects.create(
        task=task,
        section_code="overview",
        title="工程概况",
        content="已通过确定性校验的工程概况",
        validation_issues=[],
    )
    monkeypatch.setattr("apps.document_generation.jobs.get_current_job", lambda: None)

    _record_failure(
        str(task.pk),
        AgentError(
            "VALIDATION_FAILED",
            "章节 risk_identification 未通过确定性校验",
            details={
                "section_code": "risk_identification",
                "issues": [
                    {
                        "code": "RISK_CONTROL_MISSING",
                        "message": "风险项缺少对应的预控措施",
                        "severity": "error",
                    }
                ],
            },
        ),
    )

    task.refresh_from_db()
    assert task.status == GenerationTask.Status.FAILED
    assert task.progress == 78
    assert task.error_code == "VALIDATION_FAILED"
    assert "风险项缺少对应的预控措施" in task.error_message
    assert task.pending_section_codes == ["risk_identification", "emergency_plan"]
    assert task.sections.filter(section_code="overview").exists()
    recovery_event = GenerationTraceEvent.objects.get(
        task=task,
        tool="validation_recovery_ready",
    )
    assert recovery_event.metadata["section_code"] == "risk_identification"
    assert recovery_event.metadata["pending_section_codes"] == [
        "risk_identification",
        "emergency_plan",
    ]
    assert recovery_event.metadata["will_retry"] is False


@pytest.mark.django_db
def test_validation_failure_auto_retry_resumes_from_failed_section(monkeypatch):
    task = make_task(GenerationTask.Status.GENERATING)
    task.operation = GenerationTask.Operation.GENERATE
    task.template.section_order = ["overview", "risk_identification"]
    task.template.save(update_fields=["section_order", "updated_at"])
    task.save(update_fields=["operation", "updated_at"])
    GeneratedSection.objects.create(
        task=task,
        section_code="overview",
        title="工程概况",
        content="已通过确定性校验的工程概况",
        validation_issues=[],
    )
    current_job = type("CurrentJob", (), {"retries_left": 1})()
    monkeypatch.setattr(
        "apps.document_generation.jobs.get_current_job",
        lambda: current_job,
    )

    _record_failure(
        str(task.pk),
        AgentError(
            "VALIDATION_FAILED",
            "章节 risk_identification 未通过确定性校验",
            details={
                "section_code": "risk_identification",
                "issues": [
                    {
                        "code": "RISK_CONTROL_MISSING",
                        "message": "风险项缺少对应的预控措施",
                        "severity": "error",
                    }
                ],
            },
        ),
    )

    task.refresh_from_db()
    assert task.status == GenerationTask.Status.QUEUED
    assert task.pending_section_codes == ["risk_identification"]
    assert (
        GenerationTraceEvent.objects.get(
            task=task,
            tool="validation_recovery_ready",
        ).metadata["will_retry"]
        is True
    )


@pytest.mark.django_db
def test_recovery_requeues_stale_generating_and_existing_queued_tasks(monkeypatch):
    stale = make_task(GenerationTask.Status.GENERATING)
    queued = make_task(GenerationTask.Status.QUEUED)
    GenerationTask.objects.filter(pk=stale.pk).update(
        updated_at=timezone.now() - timedelta(hours=2)
    )
    queued_ids: list[str] = []
    monkeypatch.setattr(
        "apps.document_generation.recovery.queue_generation_task",
        lambda task_id: queued_ids.append(task_id),
    )

    result = recover_generation_tasks()

    stale.refresh_from_db()
    assert stale.status == GenerationTask.Status.QUEUED
    assert stale.error_code == "WORKER_INTERRUPTED"
    assert set(queued_ids) == {str(stale.pk), str(queued.pk)}
    assert result == {"recovered": 1, "queued": 2, "queue_failures": 0}
