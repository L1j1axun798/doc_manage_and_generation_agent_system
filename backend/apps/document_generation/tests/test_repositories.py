from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from apps.projects.models import Project

from ..engine.contracts import (
    KnowledgeChunk,
    RetrievalQuery,
    RiskProfile,
)
from ..models import ApprovalStatus, ClauseBlock
from ..repositories import ORMClauseRepository, ORMKnowledgeRepository

User = get_user_model()


@pytest.mark.django_db
def test_orm_knowledge_and_clause_repositories_filter_approved_content():
    admin = User.objects.create_user(
        username="admin",
        password="Password123!",
        real_name="admin",
        role=User.Role.SYSTEM_ADMIN,
    )
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="技术方案", created_by=admin)
    document = Document.objects.create(
        project=project,
        folder=folder,
        title="历史四措两案",
        created_by=admin,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="history.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=1,
        sha256="1" * 64,
        storage_path="history.bin",
        uploaded_by=admin,
    )
    repository = ORMKnowledgeRepository()
    chunk = KnowledgeChunk(
        chunk_id="chunk-001",
        source_document_version_id=version.pk,
        business_type="wind_turbine_inspection_four_measures_two_plans",
        section_code="safety_measures",
        heading_path=("安全措施",),
        paragraph_start=0,
        paragraph_end=1,
        text="高处作业必须执行防坠措施。",
        risk_tags=("high_altitude",),
        approval_status="approved",
        content_sha256="2" * 64,
        embedding=(1.0, 0.0),
        embedding_model_alias="embedding-v1",
        embedding_dimension=2,
    )

    assert repository.add((chunk,)) == 1
    assert repository.add((chunk,)) == 0
    candidates = repository.candidates(
        RetrievalQuery(
            business_type=chunk.business_type,
            section_code=chunk.section_code,
            query_text="高处安全措施",
        )
    )
    assert [item.chunk_id for item in candidates] == ["chunk-001"]

    ClauseBlock.objects.create(
        code="SAFE-001",
        version="v1",
        section_code="safety_measures",
        text="高处作业人员应正确使用防坠落装备。",
        risk_conditions=["high_altitude"],
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
        approved_by=admin,
        created_by=admin,
    )
    selected = ORMClauseRepository().select(
        RiskProfile(risk_codes=("high_altitude",)),
        "safety_measures",
    )
    assert [item.clause_code for item in selected] == ["SAFE-001"]
