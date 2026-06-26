from hashlib import sha256

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


def upload_file(name: str, content: bytes, content_type: str = "application/pdf"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def create_document_via_api(
    client,
    *,
    folder: Folder,
    title: str,
    content: bytes,
    access_level: str = Document.AccessLevel.INTERNAL,
):
    response = client.post(
        "/api/v1/documents/",
        {
            "folder": folder.id,
            "title": title,
            "access_level": access_level,
            "file": upload_file(f"{title}.pdf", content),
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.django_db
def test_document_list_is_paginated_searchable_and_filtered_by_visibility(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    visible_project = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    hidden_project = Project.objects.create(name="隐藏项目", code="P002", created_by=admin)
    visible_folder = Folder.objects.create(
        project=visible_project,
        name="过程资料",
        created_by=admin,
    )
    hidden_folder = Folder.objects.create(project=hidden_project, name="隐藏资料", created_by=admin)
    ProjectMember.objects.create(project=visible_project, user=operator, can_upload=True)
    client.force_login(admin)
    create_document_via_api(client, folder=visible_folder, title="风机检测报告", content=b"visible")
    create_document_via_api(client, folder=hidden_folder, title="隐藏报告", content=b"hidden")
    client.force_login(operator)

    response = client.get("/api/v1/documents/?search=检测")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "风机检测报告"


@pytest.mark.django_db
def test_temporary_user_cannot_search_or_download_regular_documents(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    temporary_user = make_user("temp", User.Role.TEMPORARY_USER)
    folder = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)
    document = create_document_via_api(
        client,
        folder=folder,
        title="安全生产许可证",
        content=b"public internal document",
    )
    client.force_login(temporary_user)

    list_response = client.get("/api/v1/documents/?search=许可证")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 0
    assert download_response.status_code == 404


@pytest.mark.django_db
def test_internal_document_current_version_downloads_and_writes_audit(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_upload=True)
    content = b"download content"
    client.force_login(operator)
    document = create_document_via_api(
        client,
        folder=folder,
        title="检测报告",
        content=content,
    )

    response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == content
    assert response["Content-Length"] == str(len(content))
    assert "filename*=UTF-8" in response["Content-Disposition"]
    assert AuditLog.objects.filter(action="document.download", result="success").exists()


@pytest.mark.django_db
def test_restricted_document_is_hidden_and_download_denied_without_permission(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator)
    client.force_login(admin)
    document = create_document_via_api(
        client,
        folder=folder,
        title="受限报告",
        content=b"restricted",
        access_level=Document.AccessLevel.RESTRICTED,
    )
    client.force_login(operator)

    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 0
    assert download_response.status_code == 403
    assert AuditLog.objects.filter(action="document.download", result="denied").exists()


@pytest.mark.django_db
def test_restricted_document_download_allowed_with_member_flag(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_download_restricted=True)
    content = b"restricted content"
    client.force_login(admin)
    document = create_document_via_api(
        client,
        folder=folder,
        title="受限报告",
        content=content,
        access_level=Document.AccessLevel.RESTRICTED,
    )
    client.force_login(operator)

    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert download_response.status_code == 200
    assert b"".join(download_response.streaming_content) == content


@pytest.mark.django_db
def test_guessing_document_id_outside_project_scope_returns_404(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    visible_project = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    hidden_project = Project.objects.create(name="隐藏项目", code="P002", created_by=admin)
    visible_folder = Folder.objects.create(
        project=visible_project,
        name="过程资料",
        created_by=admin,
    )
    hidden_folder = Folder.objects.create(project=hidden_project, name="隐藏资料", created_by=admin)
    ProjectMember.objects.create(project=visible_project, user=operator)
    client.force_login(admin)
    hidden_document = create_document_via_api(
        client,
        folder=hidden_folder,
        title="隐藏报告",
        content=b"hidden",
    )
    client.force_login(operator)

    detail_response = client.get(f"/api/v1/documents/{hidden_document['id']}/")
    download_response = client.get(f"/api/v1/documents/{hidden_document['id']}/download/")

    assert detail_response.status_code == 404
    assert download_response.status_code == 404
    assert Document.objects.filter(folder=visible_folder).count() == 0


@pytest.mark.django_db
def test_document_list_filter_by_folder_and_access_level(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder_a = Folder.objects.create(project=project, name="A", created_by=admin)
    folder_b = Folder.objects.create(project=project, name="B", created_by=admin)
    client.force_login(admin)
    create_document_via_api(
        client,
        folder=folder_a,
        title="内部报告",
        content=b"internal",
    )
    create_document_via_api(
        client,
        folder=folder_b,
        title="受限报告",
        content=b"restricted",
        access_level=Document.AccessLevel.RESTRICTED,
    )

    response = client.get(
        f"/api/v1/documents/?folder={folder_b.id}&access_level={Document.AccessLevel.RESTRICTED}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "受限报告"
    assert payload["results"][0]["current_version"]["sha256"] == sha256(b"restricted").hexdigest()


@pytest.mark.django_db
def test_public_root_folder_filter_includes_matching_project_folders(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    public_root = Folder.objects.create(
        name="竣工档案资料",
        code="PUBLIC-COMPLETION",
        is_system_root=True,
        created_by=admin,
    )
    project_root = Folder.objects.create(
        project=project,
        name="竣工档案资料",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    legacy_project_folder = Folder.objects.create(
        project=project,
        name="检测报告",
        code="REPORT",
        created_by=admin,
    )
    client.force_login(admin)
    create_document_via_api(client, folder=project_root, title="标准目录报告", content=b"standard")
    create_document_via_api(
        client,
        folder=legacy_project_folder,
        title="历史目录报告",
        content=b"legacy",
    )

    response = client.get(f"/api/v1/documents/?folder={public_root.id}")

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["results"]}
    assert {"标准目录报告", "历史目录报告"} <= titles
