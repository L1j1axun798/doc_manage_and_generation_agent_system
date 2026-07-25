from __future__ import annotations

from typing import Any

import django_rq
from django.conf import settings
from redis.exceptions import RedisError
from rq import Retry

from apps.audit.services import audit_log

from .exceptions import DocumentGenerationError
from .models import GenerationTask

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
