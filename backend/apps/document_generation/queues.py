from __future__ import annotations

from typing import Any

import django_rq
from django.conf import settings
from redis.exceptions import RedisError
from rq import Retry
from rq.command import send_stop_job_command
from rq.exceptions import InvalidJobOperation

from apps.audit.services import audit_log

from .exceptions import DocumentGenerationError
from .models import GenerationTask, KnowledgeCorpusUpload

QUEUE_NAME = "document-generation"
RETRY_INTERVALS = [60, 300]


def queue_generation_task(task_id: str) -> Any:
    try:
        queue = django_rq.get_queue(QUEUE_NAME)
        existing = queue.fetch_job(task_id)
        if existing is not None:
            status = str(existing.get_status(refresh=True)).lower()
            if any(value in status for value in ("queued", "started", "deferred", "scheduled")):
                return existing
            existing.delete()
        return queue.enqueue(
            "apps.document_generation.jobs.run_generation_task",
            task_id,
            job_id=task_id,
            job_timeout=settings.DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS,
            retry=Retry(max=2, interval=RETRY_INTERVALS),
            result_ttl=86400,
            failure_ttl=604800,
        )
    except (RedisError, OSError, ConnectionError) as exc:
        task = GenerationTask.objects.filter(pk=task_id).select_related("created_by").first()
        if task is not None:
            task.status = GenerationTask.Status.FAILED
            task.error_code = "QUEUE_UNAVAILABLE"
            task.error_message = "任务队列暂时不可用，请稍后重试"
            task.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            audit_log(
                user=task.created_by,
                action="document_generation.queue.failed",
                resource=task,
                result="failed",
                error_message=task.error_message,
            )
        raise DocumentGenerationError(
            "QUEUE_UNAVAILABLE",
            "任务队列暂时不可用，原资料管理功能不受影响",
            status_code=503,
        ) from exc


def queue_knowledge_corpus_upload(upload_id: str) -> Any | None:
    job_id = f"knowledge-corpus-{upload_id}"
    try:
        queue = django_rq.get_queue(QUEUE_NAME)
        existing = queue.fetch_job(job_id)
        if existing is not None:
            status = str(existing.get_status(refresh=True)).lower()
            if any(value in status for value in ("queued", "started", "deferred", "scheduled")):
                return existing
            existing.delete()
        return queue.enqueue(
            "apps.document_generation.jobs.run_knowledge_corpus_upload",
            upload_id,
            job_id=job_id,
            job_timeout=settings.DOCUMENT_AGENT_JOB_TIMEOUT_SECONDS,
            retry=Retry(max=2, interval=RETRY_INTERVALS),
            result_ttl=86400,
            failure_ttl=604800,
        )
    except (RedisError, OSError, ConnectionError):
        upload = (
            KnowledgeCorpusUpload.objects.filter(pk=upload_id)
            .select_related("created_by")
            .first()
        )
        if upload is not None:
            upload.status = KnowledgeCorpusUpload.Status.FAILED
            upload.error_code = "QUEUE_UNAVAILABLE"
            upload.error_message = "任务队列暂时不可用，请稍后重新处理"
            upload.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            audit_log(
                user=upload.created_by,
                action="document_generation.corpus.queue.failed",
                resource=upload,
                result="failed",
                error_message=upload.error_message,
            )
        return None


def stop_generation_job(task_id: str) -> str:
    """Best-effort RQ cancellation; the database task status remains authoritative."""
    try:
        queue = django_rq.get_queue(QUEUE_NAME)
        job = queue.fetch_job(task_id)
        if job is None:
            return "missing"
        job_status = str(job.get_status(refresh=True)).lower()
        if "started" in job_status:
            send_stop_job_command(queue.connection, task_id)
            return "stop_requested"
        if any(value in job_status for value in ("queued", "deferred", "scheduled")):
            job.cancel()
            return "cancelled"
        return "already_finished"
    except (RedisError, OSError, ConnectionError, InvalidJobOperation):
        return "signal_failed"
