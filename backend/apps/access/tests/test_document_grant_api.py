from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.access.models import DocumentGrant
from apps.audit.models import AuditLog
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


def create_restricted_document(client, *, folder: Folder, title: str = "受限报告"):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": title,
            "access_level": "restricted",
            "file": upload_file(f"{title}.pdf", title.encode("utf-8")),
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.django_db
def test_document_grant_list_searches_document_and_user(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin-search", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient-search", User.Role.DATA_OPERATOR)
    recipient.real_name = "张三"
    recipient.save(update_fields=["real_name"])
    project = Project.objects.create(name="项目", code="P-SEARCH-GRANT", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder, title="专项验收报告")
    create_response = client.post(
        "/api/v1/document-grants/",
        {"document": document["id"], "user": recipient.id, "can_view": True},
        content_type="application/json",
    )

    user_response = client.get("/api/v1/document-grants/?search=张三")
    document_response = client.get("/api/v1/document-grants/?search=专项验收")
    missing_response = client.get("/api/v1/document-grants/?search=不存在")

    assert create_response.status_code == 201
    assert user_response.json()["count"] == 1
    assert document_response.json()["count"] == 1
    assert missing_response.json()["count"] == 0


@pytest.mark.django_db
def test_admin_can_grant_restricted_download_to_non_member(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)

    grant_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_view": True,
            "can_download": True,
        },
        content_type="application/json",
    )
    client.force_login(recipient)
    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert grant_response.status_code == 201
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert download_response.status_code == 200
    assert b"".join(download_response.streaming_content) == "受限报告".encode()
    assert AuditLog.objects.filter(action="document.grant.create", result="success").exists()


@pytest.mark.django_db
def test_download_grant_allows_download_without_uploader_match(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_view": True,
            "can_download": True,
        },
        content_type="application/json",
    )
    client.force_login(recipient)

    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert grant_response.status_code == 201
    assert download_response.status_code == 200
    assert b"".join(download_response.streaming_content) == "受限报告".encode()


@pytest.mark.django_db
def test_download_grant_without_view_allows_download_but_hides_list(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_download": True,
        },
        content_type="application/json",
    )
    client.force_login(recipient)

    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert grant_response.status_code == 201
    assert list_response.json()["count"] == 0
    assert download_response.status_code == 200


@pytest.mark.django_db
def test_expired_grant_does_not_allow_view_or_download(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant = DocumentGrant.objects.create(
        document_id=document["id"],
        user=recipient,
        can_view=True,
        can_download=True,
        expires_at=timezone.now() - timedelta(minutes=1),
        created_by=admin,
    )
    client.force_login(recipient)

    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert grant.is_expired is True
    assert list_response.json()["count"] == 0
    assert download_response.status_code == 404


@pytest.mark.django_db
def test_revoked_grant_no_longer_allows_download(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_download": True,
        },
        content_type="application/json",
    )
    grant_id = grant_response.json()["id"]
    revoke_response = client.post(f"/api/v1/document-grants/{grant_id}/revoke/")
    client.force_login(recipient)

    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert revoke_response.status_code == 200
    assert download_response.status_code == 404
    assert AuditLog.objects.filter(action="document.grant.revoke", result="success").exists()


@pytest.mark.django_db
def test_user_without_manage_permission_cannot_create_grant(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_upload=True)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    client.force_login(operator)

    response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_view": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert DocumentGrant.objects.count() == 0


@pytest.mark.django_db
def test_delegated_manage_grant_can_manage_other_grants_for_same_document(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.DATA_OPERATOR)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    DocumentGrant.objects.create(
        document_id=document["id"],
        user=manager,
        can_manage=True,
        created_by=admin,
    )
    client.force_login(manager)

    response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_view": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert DocumentGrant.objects.filter(user=recipient, can_view=True).exists()


@pytest.mark.django_db
def test_grant_update_cannot_change_document_or_user(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
    other_user = make_user("other", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    other_document = create_restricted_document(client, folder=folder, title="其他受限报告")
    grant = DocumentGrant.objects.create(
        document_id=document["id"],
        user=recipient,
        can_view=True,
        created_by=admin,
    )

    response = client.patch(
        f"/api/v1/document-grants/{grant.id}/",
        {
            "document": other_document["id"],
            "user": other_user.id,
            "can_download": True,
        },
        content_type="application/json",
    )

    grant.refresh_from_db()
    assert response.status_code == 400
    assert grant.document_id == document["id"]
    assert grant.user == recipient
    assert grant.can_download is False


@pytest.mark.django_db
def test_project_permission_can_query_manageable_grants(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=manager, can_manage_permission=True)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": manager.id,
            "can_view": True,
        },
        content_type="application/json",
    )
    client.force_login(manager)

    response = client.get("/api/v1/document-grants/")

    assert response.status_code == 200
    assert grant_response.status_code == 201
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_grant_requires_at_least_one_action_and_future_expiry(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)

    no_action_response = client.post(
        "/api/v1/document-grants/",
        {"document": document["id"], "user": recipient.id},
        content_type="application/json",
    )
    expired_response = client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": recipient.id,
            "can_view": True,
            "expires_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        },
        content_type="application/json",
    )

    assert no_action_response.status_code == 400
    assert expired_response.status_code == 400


@pytest.mark.django_db
def test_document_grant_delete_endpoint_is_disabled(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin-delete-grant", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient-delete-grant", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P-DELETE-GRANT", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    grant = DocumentGrant.objects.create(
        document_id=document["id"],
        user=recipient,
        can_view=True,
        created_by=admin,
    )

    response = client.delete(f"/api/v1/document-grants/{grant.pk}/")

    assert response.status_code == 405
    assert DocumentGrant.objects.filter(pk=grant.pk).exists()
