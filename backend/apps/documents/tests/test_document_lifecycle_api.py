import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditLog
from apps.documents.models import Document
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


def upload_file(name: str, content: bytes):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def create_document(
    client,
    *,
    folder: Folder,
    title: str = "检测报告",
    content: bytes = b"content",
):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": title,
            "access_level": Document.AccessLevel.INTERNAL,
            "file": upload_file(f"{title}.pdf", content),
        },
    )
    assert response.status_code == 201
    return response.json()


def expected(document_id: int) -> str:
    return Document.objects.get(pk=document_id).updated_at.isoformat()


@pytest.mark.django_db
def test_document_move_requires_same_project_and_updates_lock(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project_a = Project.objects.create(name="A", code="P001", created_by=admin)
    project_b = Project.objects.create(name="B", code="P002", created_by=admin)
    source = Folder.objects.create(project=project_a, name="源目录", created_by=admin)
    target = Folder.objects.create(project=project_a, name="目标目录", created_by=admin)
    other_project = Folder.objects.create(project=project_b, name="其他项目", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=source)

    moved = client.post(
        f"/api/v1/documents/{document['id']}/move/",
        {"folder": target.id, "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    rejected = client.post(
        f"/api/v1/documents/{document['id']}/move/",
        {"folder": other_project.id, "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert moved.status_code == 200
    assert moved.json()["folder"] == target.id
    assert moved.json()["lock_version"] == document["lock_version"] + 1
    assert rejected.status_code == 400
    assert AuditLog.objects.filter(action="document.move", result="success").exists()


@pytest.mark.django_db
def test_document_move_rejects_staff_root_but_allows_employee_folder(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    source = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    employee_folder = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=source)

    root_response = client.post(
        f"/api/v1/documents/{document['id']}/move/",
        {"folder": staff_root.id, "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    employee_response = client.post(
        f"/api/v1/documents/{document['id']}/move/",
        {"folder": employee_folder.id, "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert root_response.status_code == 400
    assert employee_response.status_code == 200
    assert employee_response.json()["folder"] == employee_folder.id


@pytest.mark.django_db
def test_document_move_allows_project_staff_root(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    source = Folder.objects.create(project=project, name="源目录", created_by=admin)
    staff_root = Folder.objects.create(
        project=project,
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=False,
        created_by=admin,
    )
    client.force_login(admin)
    document = create_document(client, folder=source)

    response = client.post(
        f"/api/v1/documents/{document['id']}/move/",
        {"folder": staff_root.id, "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["folder"] == staff_root.id


@pytest.mark.django_db
def test_document_update_rejects_stale_expected_updated_at(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    stale_updated_at = document["updated_at"]

    first = client.patch(
        f"/api/v1/documents/{document['id']}/",
        {"title": "第一次修改", "expected_updated_at": stale_updated_at},
        content_type="application/json",
    )
    conflict = client.patch(
        f"/api/v1/documents/{document['id']}/",
        {"title": "第二次修改", "expected_updated_at": stale_updated_at},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert Document.objects.get(pk=document["id"]).title == "第一次修改"


@pytest.mark.django_db
def test_soft_delete_hides_document_but_keeps_physical_file(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    version = Document.objects.get(pk=document["id"]).current_version
    assert version is not None
    physical_path = tmp_path / version.storage_path

    response = client.post(
        f"/api/v1/documents/{document['id']}/delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    list_response = client.get("/api/v1/documents/")
    trash_response = client.get("/api/v1/documents/trash/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert response.status_code == 204
    assert list_response.json()["count"] == 0
    assert trash_response.json()["count"] == 1
    assert download_response.status_code == 404
    assert physical_path.is_file()
    assert Document.objects.get(pk=document["id"]).deleted_at is not None
    assert AuditLog.objects.filter(action="document.delete", result="success").exists()


@pytest.mark.django_db
def test_restore_returns_document_to_normal_list(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    delete_response = client.post(
        f"/api/v1/documents/{document['id']}/delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    assert delete_response.status_code == 204

    restore_response = client.post(
        f"/api/v1/documents/{document['id']}/restore/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None
    assert client.get("/api/v1/documents/").json()["count"] == 1
    assert client.get("/api/v1/documents/trash/").json()["count"] == 0
    assert AuditLog.objects.filter(action="document.restore", result="success").exists()


@pytest.mark.django_db
def test_permanent_delete_requires_admin_and_removes_physical_files(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_delete=True, can_restore=True)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    version_response = client.post(
        f"/api/v1/documents/{document['id']}/versions/",
        {"file": upload_file("second.pdf", b"second")},
    )
    assert version_response.status_code == 201
    storage_paths = list(
        Document.objects.get(pk=document["id"]).versions.values_list("storage_path", flat=True)
    )
    client.post(
        f"/api/v1/documents/{document['id']}/delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    client.force_login(operator)
    denied = client.post(
        f"/api/v1/documents/{document['id']}/permanent-delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    client.force_login(admin)
    deleted = client.post(
        f"/api/v1/documents/{document['id']}/permanent-delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert denied.status_code == 403
    assert deleted.status_code == 204
    assert Document.objects.filter(pk=document["id"]).count() == 0
    assert all(not (tmp_path / storage_path).exists() for storage_path in storage_paths)
    assert AuditLog.objects.filter(action="document.permanent_delete", result="success").exists()


@pytest.mark.django_db
def test_project_member_delete_and_restore_permissions(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_delete=True, can_restore=True)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    client.force_login(operator)

    delete_response = client.post(
        f"/api/v1/documents/{document['id']}/delete/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )
    restore_response = client.post(
        f"/api/v1/documents/{document['id']}/restore/",
        {"expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert delete_response.status_code == 204
    assert restore_response.status_code == 200


@pytest.mark.django_db
def test_archived_project_rejects_document_mutations(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    project.status = Project.Status.ARCHIVED
    project.save(update_fields=["status", "updated_at"])

    response = client.patch(
        f"/api/v1/documents/{document['id']}/",
        {"title": "归档后修改", "expected_updated_at": expected(document["id"])},
        content_type="application/json",
    )

    assert response.status_code == 400
