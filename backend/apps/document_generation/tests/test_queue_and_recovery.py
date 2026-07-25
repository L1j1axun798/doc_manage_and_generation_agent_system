from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from redis.exceptions import ConnectionError as RedisConnectionError

from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from apps.projects.models import Project

from ..exceptions import DocumentGenerationError
from ..models import ApprovalStatus, DocumentTemplate, GenerationTask
from ..queues import queue_generation_task
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
    def get_status(self, refresh=True):
        return "finished"

    def delete(self):
        return None


class FakeQueue:
    def __init__(self):
        self.args = None

    def fetch_job(self, job_id):
        return FakeJob()

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
