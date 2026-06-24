from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.access.models import DocumentGrant
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


def create_restricted_document(client, *, folder: Folder, title: str = "受限报告"):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": title,
            "access_level": Document.AccessLevel.RESTRICTED,
            "file": upload_file(f"{title}.pdf", b"restricted content"),
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.django_db
def test_admin_can_grant_restricted_download_to_non_member(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
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
    assert b"".join(download_response.streaming_content) == b"restricted content"
    assert AuditLog.objects.filter(action="document.grant.create", result="success").exists()


@pytest.mark.django_db
def test_download_grant_without_view_allows_download_but_hides_list(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
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
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
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
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
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
def test_manage_grant_can_manage_other_grants_for_same_document(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.DATA_OPERATOR)
    recipient = make_user("recipient", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    client.force_login(admin)
    document = create_restricted_document(client, folder=folder)
    client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": manager.id,
            "can_manage": True,
        },
        content_type="application/json",
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
def test_grant_query_only_returns_manageable_documents(client, tmp_path, settings):
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

    assert grant_response.status_code == 201
    assert response.status_code == 200
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
    assert DocumentGrant.objects.count() == 0
