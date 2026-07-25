from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from docx import Document as DocxDocument

from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from apps.projects.models import Project, ProjectMember
from common.storage import LocalDocumentStorage

from ..jobs import run_generation_task
from ..models import (
    ApprovalStatus,
    DocumentTemplate,
    GeneratedSection,
    GenerationReview,
    GenerationTask,
)

User = get_user_model()
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


def docx_bytes(*paragraphs: str) -> bytes:
    document = DocxDocument()
    for value in paragraphs:
        document.add_paragraph(value)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def create_stored_version(
    *,
    root,
    actor,
    project,
    folder,
    title: str,
    filename: str,
    content: bytes,
) -> DocumentVersion:
    storage = LocalDocumentStorage(root=root)
    stored = storage.save_uploaded_file(
        SimpleUploadedFile(filename, content, content_type=DOCX_MIME)
    )
    document = Document.objects.create(
        project=project,
        folder=folder,
        title=title,
        created_by=actor,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename=filename,
        content_type=DOCX_MIME,
        file_size=stored.size,
        sha256=stored.sha256,
        storage_path=stored.relative_path,
        uploaded_by=actor,
    )
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    return version


def setup_generation_case(tmp_path):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    viewer = make_user("viewer", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="风场入场项目", code="ENTRY-001", created_by=admin)
    ProjectMember.objects.create(
        project=project,
        user=manager,
        role=ProjectMember.Role.MANAGER,
        can_upload=True,
        can_download_restricted=True,
    )
    ProjectMember.objects.create(
        project=project,
        user=viewer,
        role=ProjectMember.Role.VIEWER,
    )
    technical_folder = Folder.objects.create(
        project=project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    report_folder = Folder.objects.create(
        project=project,
        name="报告模板",
        code="PUBLIC-REPORT-TEMPLATE",
        created_by=admin,
    )
    template_version = create_stored_version(
        root=tmp_path,
        actor=admin,
        project=project,
        folder=technical_folder,
        title="四措两案样式基线",
        filename="template.docx",
        content=docx_bytes("四措两案样式基线"),
    )
    source_version = create_stored_version(
        root=tmp_path,
        actor=manager,
        project=project,
        folder=technical_folder,
        title="入场任务通知",
        filename="entry-notice.docx",
        content=docx_bytes("项目名称：风场入场项目", "计划检测数量：12"),
    )
    report_version = create_stored_version(
        root=tmp_path,
        actor=manager,
        project=project,
        folder=report_folder,
        title="检测报告模板",
        filename="report-template.docx",
        content=docx_bytes("报告模板"),
    )
    template = DocumentTemplate.objects.create(
        code="T001",
        version="v1",
        document_version=template_version,
        section_order=["overview"],
        required_fact_fields=["project_name"],
        is_active=True,
        approval_status=ApprovalStatus.APPROVED,
        approved_by=admin,
        created_by=admin,
    )
    return {
        "admin": admin,
        "manager": manager,
        "viewer": viewer,
        "project": project,
        "template": template,
        "source_version": source_version,
        "report_version": report_version,
        "technical_folder": technical_folder,
    }


def create_task_via_api(client, case):
    response = client.post(
        "/api/v1/document-generation/tasks/",
        {
            "project_id": case["project"].pk,
            "template_id": case["template"].pk,
            "idempotency_key": "create-001",
            "facts": [
                {
                    "field": "project_name",
                    "value": "风场入场项目",
                    "value_type": "string",
                }
            ],
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    return GenerationTask.objects.get(pk=response.json()["id"])


@pytest.mark.django_db
def test_create_is_idempotent_and_project_isolation_is_enforced(client, tmp_path):
    case = setup_generation_case(tmp_path)
    client.force_login(case["manager"])
    task = create_task_via_api(client, case)

    same = client.post(
        "/api/v1/document-generation/tasks/",
        {
            "project_id": case["project"].pk,
            "template_id": case["template"].pk,
            "idempotency_key": "create-001",
            "facts": [
                {
                    "field": "project_name",
                    "value": "风场入场项目",
                    "value_type": "string",
                }
            ],
        },
        content_type="application/json",
    )
    conflict = client.post(
        "/api/v1/document-generation/tasks/",
        {
            "project_id": case["project"].pk,
            "template_id": case["template"].pk,
            "idempotency_key": "create-001",
            "facts": [
                {
                    "field": "project_name",
                    "value": "另一个项目",
                    "value_type": "string",
                }
            ],
        },
        content_type="application/json",
    )
    client.force_login(case["viewer"])
    hidden = client.get(f"/api/v1/document-generation/tasks/{task.pk}/")

    assert same.status_code == 200
    assert same.json()["id"] == str(task.pk)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert hidden.status_code == 200
    assert AuditLog.objects.filter(action="document_generation.task.create").count() == 1


@pytest.mark.django_db
def test_viewer_cannot_create_and_report_source_is_rejected(client, tmp_path):
    case = setup_generation_case(tmp_path)
    client.force_login(case["viewer"])
    denied = client.post(
        "/api/v1/document-generation/tasks/",
        {
            "project_id": case["project"].pk,
            "template_id": case["template"].pk,
            "idempotency_key": "viewer-create",
        },
        content_type="application/json",
    )
    client.force_login(case["manager"])
    task = create_task_via_api(client, case)
    blocked = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/sources/",
        {"document_version_ids": [case["report_version"].pk]},
        content_type="application/json",
    )

    assert denied.status_code == 404
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "SOURCE_PURPOSE_MISMATCH"


@pytest.mark.django_db(transaction=True)
def test_full_generation_review_and_export_workflow(client, tmp_path, monkeypatch):
    case = setup_generation_case(tmp_path)
    client.force_login(case["manager"])
    task = create_task_via_api(client, case)
    source_response = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/sources/",
        {"document_version_ids": [case["source_version"].pk]},
        content_type="application/json",
    )
    queued_ids: list[str] = []
    monkeypatch.setattr(
        "apps.document_generation.queues.queue_generation_task",
        lambda task_id: queued_ids.append(task_id),
    )
    extract_response = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/extract/",
        content_type="application/json",
    )
    with override_settings(FILE_STORAGE_ROOT=tmp_path):
        assert run_generation_task(str(task.pk)) == "extracted"
    task.refresh_from_db()
    assert task.status == GenerationTask.Status.NEEDS_CONFIRMATION
    assert task.facts_snapshot[0]["evidence"]
    confirm_response = client.put(
        f"/api/v1/document-generation/tasks/{task.pk}/facts/confirm/",
        {
            "facts": [
                {
                    "field": "project_name",
                    "value": "风场入场项目",
                    "value_type": "string",
                    "source_document_version_id": case["source_version"].pk,
                    "locator": {
                        "paragraph_index": 0,
                        "text_quote": "项目名称：风场入场项目",
                    },
                    "confidence": 1,
                }
            ]
        },
        content_type="application/json",
    )
    queued_ids.clear()
    generate_response = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/generate/",
        content_type="application/json",
    )
    task.refresh_from_db()

    assert source_response.status_code == 200
    assert extract_response.status_code == 202
    assert extract_response.json()["status"] == GenerationTask.Status.EXTRACTING
    assert confirm_response.json()["status"] == GenerationTask.Status.READY
    assert generate_response.status_code == 202
    assert task.status == GenerationTask.Status.QUEUED
    assert queued_ids == [str(task.pk)]

    with override_settings(FILE_STORAGE_ROOT=tmp_path):
        assert run_generation_task(str(task.pk)) == "completed"
        assert run_generation_task(str(task.pk)) == "skipped"
    task.refresh_from_db()
    section = GeneratedSection.objects.get(task=task, section_code="overview")
    assert task.status == GenerationTask.Status.REVIEW_REQUIRED
    assert task.generation_attempts == 2
    assert section.content
    assert (tmp_path / task.draft_storage_path).is_file()

    lock_response = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/sections/overview/lock/",
        {"locked": True},
        content_type="application/json",
    )
    approve_response = client.post(
        f"/api/v1/document-generation/tasks/{task.pk}/approve/",
        {"comment": "技术负责人确认"},
        content_type="application/json",
    )
    with override_settings(FILE_STORAGE_ROOT=tmp_path):
        export_response = client.post(
            f"/api/v1/document-generation/tasks/{task.pk}/export/",
            {"idempotency_key": "export-001"},
            content_type="application/json",
        )
        repeated_export = client.post(
            f"/api/v1/document-generation/tasks/{task.pk}/export/",
            {"idempotency_key": "export-001"},
            content_type="application/json",
        )
    task.refresh_from_db()
    output = task.output_document_version.document

    assert lock_response.status_code == 200
    assert approve_response.status_code == 200
    assert export_response.status_code == 200
    assert repeated_export.status_code == 200
    assert task.status == GenerationTask.Status.EXPORTED
    assert output.project == case["project"]
    assert output.folder == case["technical_folder"]
    assert "不是检测报告或完工报告" in output.description
    assert (
        GenerationReview.objects.filter(
            task=task,
            action=GenerationReview.Action.EXPORTED,
        ).count()
        == 1
    )


@pytest.mark.django_db
@override_settings(DOCUMENT_AGENT_ENABLED=False)
def test_feature_flag_off_leaves_api_unavailable(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    client.force_login(admin)

    response = client.get("/api/v1/document-generation/templates/")

    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_AGENT_DISABLED"


@pytest.mark.django_db
@override_settings(DOCUMENT_AGENT_ENABLED=True, DOCUMENT_AGENT_PHASE5_APPROVED=False)
def test_phase5_gate_blocks_accidental_api_activation(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    client.force_login(admin)

    response = client.get("/api/v1/document-generation/templates/")

    assert response.status_code == 503
    assert response.json()["code"] == "PHASE5_GATE_NOT_APPROVED"
