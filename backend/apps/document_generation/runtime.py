from __future__ import annotations

from typing import Any

import django_rq

from .models import ApprovalStatus, ClauseBlock, DocumentTemplate, KnowledgeSection
from .providers.embedding import OpenAICompatibleEmbeddingProvider
from .providers.health import check_providers
from .providers.llm import OpenAICompatibleLLMProvider
from .queues import QUEUE_NAME


def check_document_agent_runtime(*, call_providers: bool) -> dict[str, Any]:
    llm = OpenAICompatibleLLMProvider.from_env()
    embedding = OpenAICompatibleEmbeddingProvider.from_env()
    templates = DocumentTemplate.objects.filter(
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
    ).count()
    clauses = ClauseBlock.objects.filter(
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
    ).count()
    knowledge = KnowledgeSection.objects.filter(
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
        embedding_model_alias=embedding.model_alias,
        embedding_dimension=embedding.dimension,
    ).count()
    if templates < 1:
        raise ValueError("没有已批准且启用的Document Agent模板")
    if clauses < 1:
        raise ValueError("没有已批准且启用的Document Agent条款")
    if knowledge < 1:
        raise ValueError("没有与当前Embedding配置匹配的已批准RAG知识")
    connection = django_rq.get_queue(QUEUE_NAME).connection
    if connection.ping() is not True:
        raise ValueError("Document Agent Redis队列健康检查失败")
    result: dict[str, Any] = {
        "templates": templates,
        "clauses": clauses,
        "knowledge": knowledge,
        "queue": QUEUE_NAME,
        "redis": "ok",
        "llm_model": llm.model_alias,
        "embedding_model": embedding.model_alias,
        "embedding_dimension": embedding.dimension,
        "provider_calls": call_providers,
    }
    if call_providers:
        result.update(
            check_providers(
                llm_provider=llm,
                embedding_provider=embedding,
            )
        )
    return result
