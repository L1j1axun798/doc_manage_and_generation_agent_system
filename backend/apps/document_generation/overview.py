from __future__ import annotations

from typing import Any

import django_rq
from django.db.models import Count, Max
from rq import Worker

from .models import BUSINESS_TYPE, ApprovalStatus, KnowledgeCorpusUpload, KnowledgeSection
from .providers.embedding import OpenAICompatibleEmbeddingProvider
from .queues import QUEUE_NAME


def get_rag_overview(*, include_operations: bool) -> dict[str, Any]:
    embedding = OpenAICompatibleEmbeddingProvider.from_env()
    knowledge = KnowledgeSection.objects.filter(
        business_type=BUSINESS_TYPE,
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
        embedding_model_alias=embedding.model_alias,
        embedding_dimension=embedding.dimension,
    )
    aggregate = knowledge.aggregate(
        knowledge_chunks=Count("id"),
        source_documents=Count("source_document_version_id", distinct=True),
        last_indexed_at=Max("updated_at"),
    )
    section_counts = {
        row["section_code"]: row["chunk_count"]
        for row in knowledge.values("section_code").annotate(chunk_count=Count("id"))
    }
    section_coverage = [
        {
            "code": code,
            "name": name,
            "chunk_count": section_counts.get(code, 0),
        }
        for code, name in KnowledgeCorpusUpload.SectionCode.choices
    ]
    covered_section_count = sum(
        1 for section in section_coverage if section["chunk_count"] > 0
    )
    knowledge_chunks = aggregate["knowledge_chunks"] or 0

    return {
        "knowledge_status": "ready" if knowledge_chunks > 0 else "empty",
        "knowledge_chunks": knowledge_chunks,
        "source_documents": aggregate["source_documents"] or 0,
        "covered_section_count": covered_section_count,
        "total_section_count": len(section_coverage),
        "section_coverage": section_coverage,
        "last_indexed_at": aggregate["last_indexed_at"],
        "embedding_model_alias": embedding.model_alias,
        "embedding_dimension": embedding.dimension,
        "operations": _get_rag_operations() if include_operations else None,
    }


def _get_rag_operations() -> dict[str, Any]:
    uploads = KnowledgeCorpusUpload.objects.filter(business_type=BUSINESS_TYPE)
    processing_uploads = uploads.filter(
        status__in=[
            KnowledgeCorpusUpload.Status.QUEUED,
            KnowledgeCorpusUpload.Status.PROCESSING,
        ]
    ).count()
    failed_uploads = uploads.filter(
        status=KnowledgeCorpusUpload.Status.FAILED
    ).count()
    latest_upload = uploads.order_by("-updated_at").first()

    redis_status = "unavailable"
    worker_status = "unknown"
    queue_depth = 0
    try:
        queue = django_rq.get_queue(QUEUE_NAME)
        connection = queue.connection
        if connection.ping() is True:
            redis_status = "ok"
            queue_depth = queue.count
            worker_states = {
                worker.get_state()
                for worker in Worker.all(connection=connection, queue=queue)
            }
            if "busy" in worker_states:
                worker_status = "busy"
            elif "idle" in worker_states:
                worker_status = "idle"
            elif worker_states:
                worker_status = "unknown"
            else:
                worker_status = "offline"
    except Exception:
        worker_status = "unknown"

    if redis_status != "ok" or worker_status in {"offline", "unknown"} or failed_uploads:
        status = "attention"
    elif queue_depth > 0 or processing_uploads > 0 or worker_status == "busy":
        status = "processing"
    else:
        status = "healthy"

    return {
        "status": status,
        "redis_status": redis_status,
        "worker_status": worker_status,
        "queue_depth": queue_depth,
        "processing_uploads": processing_uploads,
        "failed_uploads": failed_uploads,
        "latest_upload_status": latest_upload.status if latest_upload else None,
        "latest_upload_at": latest_upload.updated_at if latest_upload else None,
    }
