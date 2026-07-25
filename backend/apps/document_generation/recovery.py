from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import GenerationTask
from .queues import queue_generation_task


def recover_generation_tasks() -> dict[str, int]:
    stale_before = timezone.now() - timedelta(seconds=settings.DOCUMENT_AGENT_STALE_TASK_SECONDS)
    recovered_ids: list[str] = []
    with transaction.atomic():
        stale = GenerationTask.objects.select_for_update().filter(
            status=GenerationTask.Status.GENERATING,
            updated_at__lt=stale_before,
        )
        for task in stale:
            task.status = GenerationTask.Status.QUEUED
            task.error_code = "WORKER_INTERRUPTED"
            task.error_message = "检测到Worker中断，已重新排队"
            task.save(
                update_fields=[
                    "status",
                    "error_code",
                    "error_message",
                    "updated_at",
                ]
            )
            recovered_ids.append(str(task.pk))
        queued_ids = [
            str(value)
            for value in GenerationTask.objects.filter(
                status__in=[
                    GenerationTask.Status.QUEUED,
                    GenerationTask.Status.EXTRACTING,
                ],
            ).values_list("pk", flat=True)
        ]
    queued = 0
    failed = 0
    for task_id in dict.fromkeys([*recovered_ids, *queued_ids]):
        try:
            queue_generation_task(task_id)
            queued += 1
        except Exception:
            failed += 1
    return {
        "recovered": len(recovered_ids),
        "queued": queued,
        "queue_failures": failed,
    }
