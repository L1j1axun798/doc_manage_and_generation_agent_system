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


def make_user_with_real_name(username: str, real_name: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=real_name,
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
    source_type: str | None = None,
):
    payload = {
        "folder": folder.id,
        "title": title,
        "file": upload_file(f"{title}.pdf", content),
    }
    if source_type is not None:
        payload["source_type"] = source_type
    response = client.post(
        "/api/v1/documents/",
        payload,
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
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    folder = Folder.objects.create(parent=root, name="安全生产许可证", created_by=admin)
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
def test_non_admin_cannot_download_without_document_grant(
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

    assert response.status_code == 403
    assert AuditLog.objects.filter(action="document.download", result="denied").exists()


@pytest.mark.django_db
def test_project_document_is_visible_but_download_denied_without_grant(
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
        title="项目报告",
        content=b"project",
    )
    client.force_login(operator)

    list_response = client.get("/api/v1/documents/")
    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert download_response.status_code == 403
    assert AuditLog.objects.filter(action="document.download", result="denied").exists()


@pytest.mark.django_db
def test_admin_can_download_any_document(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    content = b"admin content"
    client.force_login(admin)
    document = create_document_via_api(
        client,
        folder=folder,
        title="报告",
        content=content,
    )

    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

    assert download_response.status_code == 200
    assert b"".join(download_response.streaming_content) == content


@pytest.mark.django_db
def test_document_download_allowed_with_document_grant(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    content = b"granted content"
    client.force_login(admin)
    document = create_document_via_api(
        client,
        folder=folder,
        title="授权报告",
        content=content,
    )
    client.post(
        "/api/v1/document-grants/",
        {
            "document": document["id"],
            "user": operator.id,
            "can_download": True,
        },
        content_type="application/json",
    )
    client.force_login(operator)

    download_response = client.get(f"/api/v1/documents/{document['id']}/download/")

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
def test_document_list_filter_by_folder(client, tmp_path, settings):
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
        title="B 报告",
        content=b"folder b",
    )

    response = client.get(f"/api/v1/documents/?folder={folder_b.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "B 报告"


@pytest.mark.django_db
def test_public_root_folder_filter_includes_matching_project_folders(client, tmp_path, settings):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    public_root = Folder.objects.create(
        name="竣工资料档案",
        code="PUBLIC-COMPLETION",
        is_system_root=True,
        created_by=admin,
    )
    project_root = Folder.objects.create(
        project=project,
        name="竣工资料档案",
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
    create_document_via_api(
        client,
        folder=project_root,
        title="标准目录报告",
        content=b"standard",
        source_type=Document.SourceType.ENTRANCE_MATERIAL,
    )
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


@pytest.mark.django_db
def test_public_technical_solution_lists_only_visible_project_documents(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    visible_project = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    hidden_project = Project.objects.create(name="隐藏项目", code="P002", created_by=admin)
    ProjectMember.objects.create(project=visible_project, user=operator)
    public_technical = Folder.objects.create(
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        is_system_root=True,
        created_by=admin,
    )
    visible_technical = Folder.objects.create(
        project=visible_project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    hidden_technical = Folder.objects.create(
        project=hidden_project,
        name="技术方案",
        code="PUBLIC-TECH-SOLUTION",
        created_by=admin,
    )
    visible_other = Folder.objects.create(
        project=visible_project,
        name="其他资料",
        code="PROJECT-OTHER",
        created_by=admin,
    )
    client.force_login(admin)
    create_document_via_api(
        client,
        folder=public_technical,
        title="公共技术方案",
        content=b"public",
    )
    visible_document = create_document_via_api(
        client,
        folder=visible_technical,
        title="可见项目四措两案",
        content=b"visible-agent-output",
    )
    create_document_via_api(
        client,
        folder=hidden_technical,
        title="隐藏项目四措两案",
        content=b"hidden-agent-output",
    )
    create_document_via_api(
        client,
        folder=visible_other,
        title="可见项目其他资料",
        content=b"visible-other",
    )
    client.force_login(operator)

    public_response = client.get(
        f"/api/v1/documents/?folder={public_technical.id}",
    )
    project_response = client.get(
        f"/api/v1/documents/?project={visible_project.id}",
    )

    assert public_response.status_code == 200
    assert {item["title"] for item in public_response.json()["results"]} == {
        "公共技术方案",
        "可见项目四措两案",
    }
    assert project_response.status_code == 200
    assert visible_document["id"] in {item["id"] for item in project_response.json()["results"]}


@pytest.mark.django_db
def test_public_staff_root_only_lists_current_users_documents_for_non_admin(
    client,
    tmp_path,
    settings,
):
    settings.FILE_STORAGE_ROOT = tmp_path
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    zhang = make_user_with_real_name("zhang", "张三", User.Role.DATA_OPERATOR)
    staff_root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    zhang_folder = Folder.objects.create(parent=staff_root, name="张三", created_by=admin)
    li_folder = Folder.objects.create(parent=staff_root, name="李四", created_by=admin)
    client.force_login(admin)
    zhang_document = create_document_via_api(
        client,
        folder=zhang_folder,
        title="张三资格证",
        content=b"zhang",
    )
    li_document = create_document_via_api(
        client,
        folder=li_folder,
        title="李四资格证",
        content=b"li",
    )

    admin_response = client.get(f"/api/v1/documents/?folder={staff_root.id}")
    client.force_login(zhang)
    root_response = client.get(f"/api/v1/documents/?folder={staff_root.id}")
    other_folder_response = client.get(f"/api/v1/documents/?folder={li_folder.id}")
    other_detail_response = client.get(f"/api/v1/documents/{li_document['id']}/")

    assert admin_response.status_code == 200
    assert admin_response.json()["count"] == 2
    assert root_response.status_code == 200
    assert root_response.json()["count"] == 1
    assert root_response.json()["results"][0]["id"] == zhang_document["id"]
    assert other_folder_response.status_code == 200
    assert other_folder_response.json()["count"] == 0
    assert other_detail_response.status_code == 404
