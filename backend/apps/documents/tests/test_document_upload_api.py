from hashlib import sha256

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import document_storage_consistency
from apps.folders.models import Folder
from apps.projects.models import Project, ProjectMember
from common.validators import normalize_upload_filename

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
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
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
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"123"),
        },
    )

    assert response.status_code == 413
    assert Document.objects.count() == 0
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.django_db
def test_upload_rejects_public_qualification_roots_but_allows_child_folders(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    company_root = Folder.objects.create(
        name="公司资质",
        code="PUBLIC-COMPANY",
        is_system_root=True,
        created_by=admin,
    )
    company_folder = Folder.objects.create(
        parent=company_root,
        name="示例公司",
        created_by=admin,
    )
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    staff_folder = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    client.force_login(admin)

    company_root_response = client.post(
        "/api/v1/documents/",
        {
            "folder": company_root.id,
            "file": upload_file("certificate.pdf", b"root"),
        },
    )
    staff_root_response = client.post(
        "/api/v1/documents/",
        {
            "folder": staff_root.id,
            "file": upload_file("certificate.pdf", b"root"),
        },
    )
    company_folder_response = client.post(
        "/api/v1/documents/",
        {
            "folder": company_folder.id,
            "file": upload_file("certificate.pdf", b"company"),
        },
    )
    staff_folder_response = client.post(
        "/api/v1/documents/",
        {
            "folder": staff_folder.id,
            "file": upload_file("certificate.pdf", b"staff"),
        },
    )

    assert company_root_response.status_code == 400
    assert staff_root_response.status_code == 400
    assert company_folder_response.status_code == 201
    assert staff_folder_response.status_code == 201
    assert set(Document.objects.values_list("folder_id", flat=True)) == {
        company_folder.id,
        staff_folder.id,
    }


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
def test_authenticated_user_can_upload_to_public_child_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    client.force_login(operator)

    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content"),
        },
    )

    assert response.status_code == 201
    document = Document.objects.get()
    assert document.folder == folder
    assert document.created_by == operator


@pytest.mark.django_db
def test_non_admin_can_upload_only_to_own_public_staff_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = User.objects.create_user(
        username="operator",
        password="Password123!",
        real_name="张三",
        role=User.Role.DATA_OPERATOR,
    )
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    own_folder = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    other_folder = Folder.objects.create(parent=staff_root, name="李四", created_by=admin)
    client.force_login(operator)

    own_response = client.post(
        "/api/v1/documents/",
        {"folder": own_folder.id, "file": upload_file("own.pdf", b"own")},
    )
    other_response = client.post(
        "/api/v1/documents/",
        {"folder": other_folder.id, "file": upload_file("other.pdf", b"other")},
    )

    assert own_response.status_code == 201
    assert other_response.status_code == 403
    assert list(Document.objects.values_list("folder_id", flat=True)) == [own_folder.id]


@pytest.mark.django_db
def test_entry_material_upload_requires_project_entry_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="入场项目", code="ENTRY-001", created_by=admin)
    entry_folder = Folder.objects.create(
        project=project,
        name="入场前置资料",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    ordinary_folder = Folder.objects.create(
        project=project,
        name="项目资料",
        code="PROJECT-DOCUMENTS",
        created_by=admin,
    )
    client.force_login(admin)

    entry_response = client.post(
        "/api/v1/documents/",
        {
            "folder": entry_folder.id,
            "source_type": Document.SourceType.ENTRANCE_MATERIAL,
            "file": upload_file("entry.pdf", b"entry"),
        },
    )
    ordinary_to_entry_response = client.post(
        "/api/v1/documents/",
        {
            "folder": entry_folder.id,
            "file": upload_file("ordinary.pdf", b"ordinary"),
        },
    )
    entry_to_ordinary_response = client.post(
        "/api/v1/documents/",
        {
            "folder": ordinary_folder.id,
            "source_type": Document.SourceType.ENTRANCE_MATERIAL,
            "file": upload_file("wrong-entry.pdf", b"wrong"),
        },
    )

    assert entry_response.status_code == 201
    assert entry_response.json()["project"] == project.pk
    assert entry_response.json()["source_type"] == Document.SourceType.ENTRANCE_MATERIAL
    assert ordinary_to_entry_response.status_code == 400
    assert entry_to_ordinary_response.status_code == 400
    assert Document.objects.count() == 1


@pytest.mark.django_db
def test_entry_material_filter_is_project_scoped(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="入场项目", code="ENTRY-001", created_by=admin)
    other_project = Project.objects.create(
        name="其他项目",
        code="ENTRY-002",
        created_by=admin,
    )
    entry_folder = Folder.objects.create(
        project=project,
        name="入场前置资料",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    other_entry_folder = Folder.objects.create(
        project=other_project,
        name="入场前置资料",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    ordinary_folder = Folder.objects.create(
        project=project,
        name="项目资料",
        code="PROJECT-DOCUMENTS",
        created_by=admin,
    )
    client.force_login(admin)

    entry = client.post(
        "/api/v1/documents/",
        {
            "folder": entry_folder.id,
            "source_type": Document.SourceType.ENTRANCE_MATERIAL,
            "file": upload_file("entry.pdf", b"entry"),
        },
    ).json()
    client.post(
        "/api/v1/documents/",
        {
            "folder": ordinary_folder.id,
            "file": upload_file("ordinary.pdf", b"ordinary"),
        },
    )
    client.post(
        "/api/v1/documents/",
        {
            "folder": other_entry_folder.id,
            "source_type": Document.SourceType.ENTRANCE_MATERIAL,
            "file": upload_file("other-entry.pdf", b"other-entry"),
        },
    )

    response = client.get(
        "/api/v1/documents/",
        {
            "project": project.pk,
            "source_type": Document.SourceType.ENTRANCE_MATERIAL,
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [entry["id"]]


@pytest.mark.django_db
def test_upload_rejects_same_name_and_duplicate_content_in_same_folder(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    other_folder = Folder.objects.create(parent=root, name="其他公司", created_by=admin)
    client.force_login(admin)
    first = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content-a"),
        },
    )

    same_name = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("report.pdf", b"content-b"),
        },
    )
    same_content = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "file": upload_file("copy.pdf", b"content-a"),
        },
    )
    other_folder_same_name = client.post(
        "/api/v1/documents/",
        {
            "folder": other_folder.id,
            "file": upload_file("report.pdf", b"content-c"),
        },
    )

    assert first.status_code == 201
    assert same_name.status_code == 400
    assert same_content.status_code == 400
    assert other_folder_same_name.status_code == 201
    assert Document.objects.count() == 2


@pytest.mark.django_db
def test_project_member_without_upload_permission_cannot_upload(client, tmp_path, settings):
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
    assert not Document.objects.exists()


@pytest.mark.django_db
def test_user_outside_project_cannot_upload_to_project_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
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
def test_archive_root_and_year_reject_document_upload(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    archive_root = Folder.objects.create(
        name="已归档文件",
        code="PUBLIC-ARCHIVE",
        is_system_root=True,
        created_by=admin,
    )
    archive_year = Folder.objects.create(
        parent=archive_root,
        name="2026年归档资料",
        code="PUBLIC-ARCHIVE-2026",
        created_by=admin,
    )
    client.force_login(admin)

    root_response = client.post(
        "/api/v1/documents/",
        {
            "folder": archive_root.id,
            "file": upload_file("root.pdf", b"root"),
        },
    )
    year_response = client.post(
        "/api/v1/documents/",
        {
            "folder": archive_year.id,
            "file": upload_file("year.pdf", b"year"),
        },
    )

    assert root_response.status_code == 400
    assert year_response.status_code == 400
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
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
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
def test_public_viewer_cannot_replace_document_current_version(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin-version", User.Role.SYSTEM_ADMIN)
    viewer = make_user("viewer-version", User.Role.DATA_OPERATOR)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    client.force_login(admin)
    created = client.post(
        "/api/v1/documents/",
        {"folder": folder.id, "file": upload_file("report.pdf", b"v1")},
    )
    document = Document.objects.get(pk=created.json()["id"])
    original_version_id = document.current_version_id
    client.force_login(viewer)

    response = client.post(
        f"/api/v1/documents/{document.pk}/versions/",
        {"file": upload_file("report-v2.pdf", b"v2")},
    )

    document.refresh_from_db()
    assert response.status_code == 403
    assert document.current_version_id == original_version_id
    assert document.versions.count() == 1


@pytest.mark.django_db
def test_upload_rejects_spoofed_signature_and_path_filename(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    settings.VALIDATE_UPLOAD_FILE_SIGNATURES = True
    admin = make_user("admin-signature", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
    client.force_login(admin)

    spoofed = client.post(
        "/api/v1/documents/",
        {"folder": folder.id, "file": upload_file("fake.pdf", b"not-a-pdf")},
    )
    assert spoofed.status_code == 400
    with pytest.raises(ValidationError):
        normalize_upload_filename("..\\escape.pdf")
    assert Document.objects.count() == 0


@pytest.mark.django_db
def test_database_failure_cleans_saved_physical_file(client, tmp_path, settings, monkeypatch):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
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
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="示例公司", created_by=admin)
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
