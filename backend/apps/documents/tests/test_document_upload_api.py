from hashlib import sha256

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import document_storage_consistency
from apps.folders.models import Folder
from apps.projects.models import Project, ProjectMember

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


def upload_file(name: str, content: bytes, content_type: str = "application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db
def test_project_member_can_upload_document_and_sha256(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_upload=True)
    content = b"%PDF-1.4 wind doc"
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": "检测报告",
            "file": upload_file("report.pdf", content),
        },
    )

    assert response.status_code == 201
    document = Document.objects.get()
    version = DocumentVersion.objects.get()
    document.refresh_from_db()
    assert document.current_version == version
    assert version.version_number == 1
    assert version.sha256 == sha256(content).hexdigest()
    assert (tmp_path / version.storage_path).is_file()
    assert AuditLog.objects.filter(action="document.create", result="success").exists()


@pytest.mark.django_db
def test_upload_rejects_disallowed_extension(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": root.id,
            "file": upload_file("malware.exe", b"bad", "application/octet-stream"),
        },
    )

    assert response.status_code == 400
    assert Document.objects.count() == 0
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_upload_rejects_oversized_file_with_413(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    settings.MAX_UPLOAD_SIZE_BYTES = 2
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": root.id,
            "file": upload_file("report.pdf", b"123"),
        },
    )

    assert response.status_code == 413
    assert Document.objects.count() == 0
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_upload_rejects_staff_root_but_allows_employee_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    employee_folder = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    client.force_login(admin)

    root_response = client.post(
        "/api/v1/documents/",
        {
            "folder": staff_root.id,
            "file": upload_file("certificate.pdf", b"root"),
        },
    )
    employee_response = client.post(
        "/api/v1/documents/",
        {
            "folder": employee_folder.id,
            "file": upload_file("certificate.pdf", b"employee"),
        },
    )

    assert root_response.status_code == 400
    assert employee_response.status_code == 201
    assert Document.objects.count() == 1
    assert Document.objects.get().folder == employee_folder


@pytest.mark.django_db
def test_upload_allows_project_staff_root(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    staff_root = Folder.objects.create(
        project=project,
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=False,
        created_by=admin,
    )
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": staff_root.id,
            "file": upload_file("certificate.pdf", b"project staff root"),
        },
    )

    assert response.status_code == 201
    assert Document.objects.get().folder == staff_root


@pytest.mark.django_db
def test_member_without_upload_permission_is_denied(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_upload=False)
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content"),
        },
    )

    assert response.status_code == 403
    assert Document.objects.count() == 0
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_archived_project_rejects_document_upload(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(
        name="项目",
        code="P001",
        created_by=admin,
        status=Project.Status.ARCHIVED,
    )
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content"),
        },
    )

    assert response.status_code == 400
    assert Document.objects.count() == 0
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_create_document_version_locks_document_and_updates_current_version(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)
    create_response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"v1"),
        },
    )
    document_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/documents/{document_id}/versions/",
        {"file": upload_file("report-v2.pdf", b"v2")},
    )

    assert response.status_code == 201
    document = Document.objects.get(pk=document_id)
    versions = list(document.versions.order_by("version_number"))
    assert [version.version_number for version in versions] == [1, 2]
    assert document.current_version == versions[-1]
    assert versions[-1].sha256 == sha256(b"v2").hexdigest()


@pytest.mark.django_db
def test_database_failure_cleans_saved_physical_file(client, tmp_path, settings, monkeypatch):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    def fail_create(*args, **kwargs):
        raise RuntimeError("db failed")

    monkeypatch.setattr(Document.objects, "create", fail_create)

    with pytest.raises(RuntimeError, match="db failed"):
        client.post(
            "/api/v1/documents/",
            {
                "folder": folder.id,
                "file": upload_file("report.pdf", b"content"),
            },
        )

    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


@pytest.mark.django_db
def test_document_storage_consistency_reports_missing_file(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    folder = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content"),
        },
    )
    document = Document.objects.get(pk=response.json()["id"])
    version = document.current_version
    assert version is not None
    (tmp_path / version.storage_path).unlink()

    result = document_storage_consistency(document=document)

    assert result == {"missing_files": [version.storage_path]}
