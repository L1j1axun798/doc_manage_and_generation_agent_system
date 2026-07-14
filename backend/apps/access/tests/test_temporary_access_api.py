from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.access.models import TemporaryAccessGrant
from apps.access.temporary_services import consume_temporary_access_token
from apps.access.temporary_tokens import hash_temporary_access_token
from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
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


def create_document(client, *, folder: Folder, content: bytes = b"v1"):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": "检测报告",
            "file": upload_file("report.pdf", content),
        },
    )
    assert response.status_code == 201
    return response.json()


def create_version(client, *, document_id: int, content: bytes):
    response = client.post(
        f"/api/v1/documents/{document_id}/versions/",
        {"file": upload_file("report-version.pdf", content)},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.django_db
def test_temporary_access_list_searches_document_filename_and_creator(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin-search", User.Role.SYSTEM_ADMIN)
    admin.real_name = "安全管理员"
    admin.save(update_fields=["real_name"])
    project = Project.objects.create(name="项目", code="P-SEARCH-TEMP", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    create_response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": document["current_version"]["id"]},
        content_type="application/json",
    )

    title_response = client.get("/api/v1/temporary-access-grants/?search=检测报告")
    filename_response = client.get("/api/v1/temporary-access-grants/?search=report.pdf")
    creator_response = client.get("/api/v1/temporary-access-grants/?search=安全管理员")
    missing_response = client.get("/api/v1/temporary-access-grants/?search=不存在")

    assert create_response.status_code == 201
    assert title_response.json()["count"] == 1
    assert filename_response.json()["count"] == 1
    assert creator_response.json()["count"] == 1
    assert missing_response.json()["count"] == 0


@pytest.mark.django_db
def test_create_temporary_access_returns_token_once_and_stores_hash(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)

    response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": document["current_version"]["id"]},
        content_type="application/json",
    )
    token = response.json()["token"]
    list_response = client.get("/api/v1/temporary-access-grants/")

    grant = TemporaryAccessGrant.objects.get()
    assert response.status_code == 201
    assert token
    assert response.json()["download_url"] == f"/share#token={token}"
    assert grant.token_hash == hash_temporary_access_token(token)
    assert token not in grant.token_hash
    assert "token" not in list_response.json()["results"][0]
    assert AuditLog.objects.filter(action="temporary_access.create", result="success").exists()


@pytest.mark.django_db
def test_temporary_access_downloads_specific_version_once(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder, content=b"version-one")
    create_version(client, document_id=document["id"], content=b"version-two")
    first_version = DocumentVersion.objects.get(version_number=1)
    token_response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": first_version.id},
        content_type="application/json",
    )
    token = token_response.json()["token"]
    client.logout()

    first_download = client.post(
        "/api/v1/temporary-access/download/",
        {"token": token},
        content_type="application/json",
    )
    second_download = client.post(
        "/api/v1/temporary-access/download/",
        {"token": token},
        content_type="application/json",
    )

    grant = TemporaryAccessGrant.objects.get()
    assert first_download.status_code == 200
    assert b"".join(first_download.streaming_content) == b"version-one"
    assert second_download.status_code == 403
    assert grant.used_count == 1
    assert grant.remaining_downloads == 0
    assert AuditLog.objects.filter(action="temporary_access.download", result="success").exists()
    assert AuditLog.objects.filter(action="temporary_access.download", result="denied").exists()


@pytest.mark.django_db
def test_temporary_access_respects_max_downloads(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder, content=b"limited")
    token_response = client.post(
        "/api/v1/temporary-access-grants/",
        {
            "document_version": document["current_version"]["id"],
            "max_downloads": 2,
        },
        content_type="application/json",
    )
    token = token_response.json()["token"]
    client.logout()

    responses = [
        client.post(
            "/api/v1/temporary-access/download/",
            {"token": token},
            content_type="application/json",
        )
        for _ in range(3)
    ]

    assert [response.status_code for response in responses] == [200, 200, 403]
    assert TemporaryAccessGrant.objects.get().used_count == 2


@pytest.mark.django_db
def test_expired_temporary_access_is_denied(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    token = "expired-token-that-is-long-enough"
    TemporaryAccessGrant.objects.create(
        document_version_id=document["current_version"]["id"],
        token_hash=hash_temporary_access_token(token),
        expires_at=timezone.now() - timedelta(minutes=1),
        created_by=admin,
    )
    client.logout()

    response = client.post(
        "/api/v1/temporary-access/download/",
        {"token": token},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert TemporaryAccessGrant.objects.get().used_count == 0


@pytest.mark.django_db
def test_revoked_temporary_access_is_denied(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_document(client, folder=folder)
    token_response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": document["current_version"]["id"]},
        content_type="application/json",
    )
    token = token_response.json()["token"]
    revoke_response = client.post(
        f"/api/v1/temporary-access-grants/{token_response.json()['id']}/revoke/"
    )
    client.logout()

    response = client.post(
        "/api/v1/temporary-access/download/",
        {"token": token},
        content_type="application/json",
    )

    assert revoke_response.status_code == 200
    assert response.status_code == 403
    assert TemporaryAccessGrant.objects.get().revoked_at is not None
    assert AuditLog.objects.filter(action="temporary_access.revoke", result="success").exists()


@pytest.mark.django_db
def test_deleted_document_revokes_temporary_access_permanently(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin-delete-token", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P-DELETE-TOKEN", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document_payload = create_document(client, folder=folder)
    token_response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": document_payload["current_version"]["id"]},
        content_type="application/json",
    )
    token = token_response.json()["token"]
    deleted = client.post(
        f"/api/v1/documents/{document_payload['id']}/delete/",
        {"expected_updated_at": document_payload["updated_at"]},
        content_type="application/json",
    )
    document = Document.objects.get(pk=document_payload["id"])
    restored = client.post(
        f"/api/v1/documents/{document.pk}/restore/",
        {"expected_updated_at": document.updated_at.isoformat().replace("+00:00", "Z")},
        content_type="application/json",
    )
    client.logout()

    download = client.post(
        "/api/v1/temporary-access/download/",
        {"token": token},
        content_type="application/json",
    )

    assert deleted.status_code == 204
    assert restored.status_code == 200
    assert download.status_code == 403
    assert TemporaryAccessGrant.objects.get().revoked_at is not None


@pytest.mark.django_db
def test_user_with_manage_permission_can_create_temporary_access(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(
        project=project,
        user=operator,
        can_upload=True,
        can_manage_permission=True,
    )
    client.force_login(admin)
    document = create_document(client, folder=folder)
    client.force_login(operator)

    response = client.post(
        "/api/v1/temporary-access-grants/",
        {"document_version": document["current_version"]["id"]},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert TemporaryAccessGrant.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_temporary_access_consumption_succeeds_once(tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    document = Document.objects.create(
        project=project,
        folder=folder,
        title="检测报告",
        created_by=admin,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="report.pdf",
        content_type="application/pdf",
        file_size=7,
        sha256="0" * 64,
        storage_path="report.pdf",
        uploaded_by=admin,
    )
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    (tmp_path / "report.pdf").write_bytes(b"content")
    token = "concurrent-token"
    TemporaryAccessGrant.objects.create(
        document_version=version,
        token_hash=hash_temporary_access_token(token),
        expires_at=timezone.now() + timedelta(hours=1),
        created_by=admin,
    )

    def consume_once() -> tuple[bool, str]:
        try:
            file_handle, _ = consume_temporary_access_token(token=token)
            file_handle.close()
            return True, ""
        except Exception as exc:
            return False, repr(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume_once(), range(2)))

    assert [result[0] for result in results].count(True) == 1, results
    assert TemporaryAccessGrant.objects.get().used_count == 1
