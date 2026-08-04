from types import SimpleNamespace

import pytest
from django.test import override_settings

from ..models import ApprovalStatus, KnowledgeSection
from .test_platform_api import setup_generation_case


def create_knowledge_section(
    *,
    chunk_id: str,
    source_document_version,
    section_code: str,
    model_alias: str = "test-embedding",
    dimension: int = 4,
    is_active: bool = True,
):
    return KnowledgeSection.objects.create(
        chunk_id=chunk_id,
        source_document_version=source_document_version,
        section_code=section_code,
        heading_path=[section_code],
        paragraph_start=0,
        paragraph_end=0,
        locator={"paragraph_index": 0},
        text=f"{section_code} knowledge",
        content_sha256=chunk_id.ljust(64, "0")[:64],
        embedding=[0.1] * dimension,
        embedding_model_alias=model_alias,
        embedding_dimension=dimension,
        is_active=is_active,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.mark.django_db
@override_settings(DOCUMENT_AGENT_ENABLED=True, DOCUMENT_AGENT_PHASE5_APPROVED=True)
def test_rag_overview_returns_matching_knowledge_and_admin_operations(
    client,
    tmp_path,
    monkeypatch,
):
    case = setup_generation_case(tmp_path)
    version = case["template"].document_version
    create_knowledge_section(
        chunk_id="overview-1",
        source_document_version=version,
        section_code="overview",
    )
    create_knowledge_section(
        chunk_id="technical-1",
        source_document_version=version,
        section_code="technical_measures",
    )
    create_knowledge_section(
        chunk_id="inactive-1",
        source_document_version=version,
        section_code="safety_measures",
        is_active=False,
    )
    create_knowledge_section(
        chunk_id="other-model-1",
        source_document_version=version,
        section_code="risk_identification",
        model_alias="other-embedding",
    )
    monkeypatch.setattr(
        "apps.document_generation.overview.OpenAICompatibleEmbeddingProvider.from_env",
        lambda: SimpleNamespace(model_alias="test-embedding", dimension=4),
    )
    monkeypatch.setattr(
        "apps.document_generation.overview._get_rag_operations",
        lambda: {
            "status": "healthy",
            "redis_status": "ok",
            "worker_status": "idle",
            "queue_depth": 0,
            "processing_uploads": 0,
            "failed_uploads": 0,
            "latest_upload_status": None,
            "latest_upload_at": None,
        },
    )
    client.force_login(case["admin"])

    response = client.get("/api/v1/document-generation/overview/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["knowledge_status"] == "ready"
    assert payload["knowledge_chunks"] == 2
    assert payload["source_documents"] == 1
    assert payload["covered_section_count"] == 2
    assert payload["total_section_count"] == 8
    assert payload["embedding_model_alias"] == "test-embedding"
    assert payload["embedding_dimension"] == 4
    assert payload["operations"]["worker_status"] == "idle"
    coverage = {row["code"]: row["chunk_count"] for row in payload["section_coverage"]}
    assert coverage["overview"] == 1
    assert coverage["technical_measures"] == 1
    assert coverage["safety_measures"] == 0


@pytest.mark.django_db
@override_settings(DOCUMENT_AGENT_ENABLED=True, DOCUMENT_AGENT_PHASE5_APPROVED=True)
def test_rag_overview_hides_operations_from_non_admin_users(
    client,
    tmp_path,
    monkeypatch,
):
    case = setup_generation_case(tmp_path)
    monkeypatch.setattr(
        "apps.document_generation.overview.OpenAICompatibleEmbeddingProvider.from_env",
        lambda: SimpleNamespace(model_alias="test-embedding", dimension=4),
    )
    monkeypatch.setattr(
        "apps.document_generation.overview._get_rag_operations",
        lambda: pytest.fail("ordinary users must not probe or receive runtime operations"),
    )
    client.force_login(case["manager"])

    response = client.get("/api/v1/document-generation/overview/")

    assert response.status_code == 200
    assert response.json()["knowledge_status"] == "empty"
    assert response.json()["operations"] is None


@pytest.mark.django_db
@override_settings(DOCUMENT_AGENT_ENABLED=False)
def test_rag_overview_respects_document_agent_feature_gate(client, tmp_path):
    case = setup_generation_case(tmp_path)
    client.force_login(case["admin"])

    response = client.get("/api/v1/document-generation/overview/")

    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_AGENT_DISABLED"
