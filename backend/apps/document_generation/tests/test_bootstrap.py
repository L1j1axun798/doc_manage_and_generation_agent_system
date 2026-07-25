from __future__ import annotations

import hashlib
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder

from ..bootstrap import BootstrapPaths, bootstrap_document_agent
from ..models import ClauseBlock, DocumentTemplate, KnowledgeSection

User = get_user_model()


@pytest.mark.django_db
def test_bootstrap_is_validated_idempotent_and_supports_dry_run(tmp_path) -> None:
    actor = User.objects.create_user(
        username="approver",
        password="Password123!",
        real_name="approver",
        role=User.Role.SYSTEM_ADMIN,
    )
    folder = Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        created_by=actor,
    )
    content = b"safe-template-style-baseline"
    template_path = tmp_path / "template.docx"
    template_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    document = Document.objects.create(
        folder=folder,
        title="四措两案模板",
        created_by=actor,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="template.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=len(content),
        sha256=digest,
        storage_path="template.docx",
        uploaded_by=actor,
    )

    template_csv = tmp_path / "templates.csv"
    template_csv.write_text(
        "template_id,document_version_id,business_type_code,client_code,template_name,"
        "source_kind,sha256,required_placeholders_verified,minimum_render_verified,"
        "approval_status\n"
        f"T001,{version.pk},wind_turbine_inspection_four_measures_two_plans,GENERAL,"
        f"通用模板,批准基线,{digest},yes,yes,approved\n",
        encoding="utf-8",
    )
    matrix_csv = tmp_path / "matrix.csv"
    matrix_csv.write_text(
        "matrix_id,risk_code,section_code,clause_code,clause_version,approval_status\n"
        "M001,high_altitude,safety_measures,SAFE-001,v1,approved\n",
        encoding="utf-8",
    )
    clauses_csv = tmp_path / "clauses.csv"
    clauses_csv.write_text(
        "matrix_id,clause_code,clause_version,section_code,text,approval_status\n"
        "M001,SAFE-001,v1,safety_measures,高处作业必须使用防坠落装备,approved\n",
        encoding="utf-8",
    )
    knowledge_json = tmp_path / "knowledge.json"
    knowledge_json.write_text(
        json.dumps(
            [
                {
                    "chunk_id": "chunk-001",
                    "source_document_version_id": version.pk,
                    "business_type": "wind_turbine_inspection_four_measures_two_plans",
                    "section_code": "safety_measures",
                    "heading_path": ["安全措施"],
                    "paragraph_start": 0,
                    "paragraph_end": 1,
                    "text": "高处作业必须使用防坠落装备。",
                    "approval_status": "approved",
                    "content_sha256": "1" * 64,
                    "embedding": [1.0, 0.0],
                    "embedding_model_alias": "embedding-v1",
                    "embedding_dimension": 2,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    paths = BootstrapPaths(
        template_inventory=template_csv,
        clause_matrix=matrix_csv,
        clause_blocks=clauses_csv,
        knowledge_index=knowledge_json,
    )

    with override_settings(FILE_STORAGE_ROOT=tmp_path):
        dry_run = bootstrap_document_agent(actor=actor, paths=paths, dry_run=True)
        assert dry_run.templates_created == 1
        assert DocumentTemplate.objects.count() == 0

        first = bootstrap_document_agent(actor=actor, paths=paths)
        second = bootstrap_document_agent(actor=actor, paths=paths)

    assert first.templates_created == 1
    assert first.clauses_created == 1
    assert first.knowledge_created == 1
    assert second.templates_updated == 1
    assert second.clauses_updated == 1
    assert second.knowledge_updated == 1
    assert DocumentTemplate.objects.count() == 1
    assert ClauseBlock.objects.count() == 1
    assert KnowledgeSection.objects.count() == 1
    assert AuditLog.objects.filter(action="document_generation.bootstrap").count() == 2
