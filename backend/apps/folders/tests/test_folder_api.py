import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

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


@pytest.mark.django_db
def test_system_admin_can_create_public_child_folder(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/folders/",
        {"parent": root.id, "name": "营业执照", "code": "PUBLIC-CERT"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Folder.objects.filter(name="营业执照", parent=root).exists()
    assert AuditLog.objects.filter(action="folder.create", result="success").exists()


@pytest.mark.django_db
def test_system_admin_cannot_create_public_root_folder(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    client.force_login(admin)

    response = client.post(
        "/api/v1/folders/",
        {"name": "新根分类"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_non_admin_cannot_create_public_child_folder(client):
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    root = Folder.objects.create(name="公司资质", is_system_root=True)
    client.force_login(operator)

    response = client.post(
        "/api/v1/folders/",
        {"parent": root.id, "name": "营业执照"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_project_member_can_create_project_folder_with_permission(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_manage_folder=True)
    client.force_login(operator)

    response = client.post(
        "/api/v1/folders/",
        {"project": project.id, "name": "过程资料"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert Folder.objects.filter(project=project, name="过程资料").exists()


@pytest.mark.django_db
def test_folder_delete_endpoint_is_disabled(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    folder = Folder.objects.create(project=project, name="过程资料", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_manage_folder=True)
    client.force_login(operator)

    response = client.delete(f"/api/v1/folders/{folder.id}/")

    assert response.status_code == 405
    assert Folder.objects.filter(pk=folder.pk).exists()


@pytest.mark.django_db
def test_project_member_without_folder_permission_is_denied(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, can_manage_folder=False)
    client.force_login(operator)

    response = client.post(
        "/api/v1/folders/",
        {"project": project.id, "name": "过程资料"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_folder_tree_only_returns_visible_projects(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    visible_project = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    hidden_project = Project.objects.create(name="隐藏项目", code="P002", created_by=admin)
    ProjectMember.objects.create(project=visible_project, user=operator)
    public = Folder.objects.create(name="公共目录", is_system_root=True, created_by=admin)
    visible = Folder.objects.create(project=visible_project, name="可见目录", created_by=admin)
    Folder.objects.create(project=hidden_project, name="隐藏目录", created_by=admin)
    client.force_login(operator)

    response = client.get("/api/v1/folders/tree/")

    assert response.status_code == 200
    names = {node["name"] for node in response.json()}
    assert {public.name, visible.name}.issubset(names)
    assert "隐藏目录" not in names


@pytest.mark.django_db
def test_folder_tree_hides_invalid_public_roots(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    Folder.objects.create(name="误建根目录", created_by=admin)
    client.force_login(admin)

    response = client.get("/api/v1/folders/tree/")

    assert response.status_code == 200
    names = {node["name"] for node in response.json()}
    assert "公司资质" in names
    assert "误建根目录" not in names


@pytest.mark.django_db
def test_folder_parent_must_match_project(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project_a = Project.objects.create(name="A", code="P001", created_by=admin)
    project_b = Project.objects.create(name="B", code="P002", created_by=admin)
    parent = Folder.objects.create(project=project_a, name="父目录", created_by=admin)
    client.force_login(admin)

    response = client.post(
        "/api/v1/folders/",
        {"project": project_b.id, "parent": parent.id, "name": "子目录"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_folder_move_rejects_self_and_descendant(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    root = Folder.objects.create(project=project, name="根目录", created_by=admin)
    child = Folder.objects.create(project=project, parent=root, name="子目录", created_by=admin)
    client.force_login(admin)

    self_response = client.post(
        f"/api/v1/folders/{root.id}/move/",
        {"parent": root.id},
        content_type="application/json",
    )
    descendant_response = client.post(
        f"/api/v1/folders/{root.id}/move/",
        {"parent": child.id},
        content_type="application/json",
    )

    assert self_response.status_code == 400
    assert descendant_response.status_code == 400


@pytest.mark.django_db
def test_archived_project_rejects_folder_writes(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(
        name="项目",
        code="P001",
        created_by=admin,
        status=Project.Status.ARCHIVED,
    )
    client.force_login(admin)

    response = client.post(
        "/api/v1/folders/",
        {"project": project.id, "name": "过程资料"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_disable_folder_rejects_active_children(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    system_root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    root = Folder.objects.create(parent=system_root, name="根目录", created_by=admin)
    Folder.objects.create(parent=root, name="子目录", created_by=admin)
    client.force_login(admin)

    response = client.post(f"/api/v1/folders/{root.id}/disable/")

    assert response.status_code == 400
    root.refresh_from_db()
    assert root.is_active is True


@pytest.mark.django_db
def test_disable_folder_rejects_existing_documents(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    system_root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    company_folder = Folder.objects.create(parent=system_root, name="示例公司", created_by=admin)
    Document.objects.create(folder=company_folder, title="营业执照", created_by=admin)
    client.force_login(admin)

    response = client.post(f"/api/v1/folders/{company_folder.id}/disable/")

    assert response.status_code == 400
    company_folder.refresh_from_db()
    assert company_folder.is_active is True


@pytest.mark.django_db
def test_folder_list_searches_and_returns_parent_name(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(
        name="人员资质",
        code="PUBLIC-STAFF",
        is_system_root=True,
        created_by=admin,
    )
    Folder.objects.create(parent=root, name="张三", code="STAFF-ZS", created_by=admin)
    Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    response = client.get("/api/v1/folders/?search=张三&ordering=name")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["name"] == "张三"
    assert payload["results"][0]["parent_name"] == "人员资质"


@pytest.mark.django_db
def test_init_public_folders_command_creates_default_roots():
    call_command("init_public_folders")

    names = set(
        Folder.objects.filter(
            project__isnull=True,
            parent__isnull=True,
            is_system_root=True,
        ).values_list("name", flat=True)
    )

    assert (
        Folder.objects.filter(
            project__isnull=True,
            parent__isnull=True,
            is_system_root=True,
        ).count()
        == 11
    )
    assert {
        "入场前置资料",
        "公司资质",
        "技术方案",
        "报告模板",
        "工器具及年检资质",
        "仪器仪表设备年检资质",
        "车辆年检资质",
        "人员资质",
        "人员保险单",
        "个人防护用品",
        "已归档文件",
    } == names


@pytest.mark.django_db
def test_project_folder_tree_hides_legacy_project_folders(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    Folder.objects.create(
        project=project,
        name="竣工资料档案",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    Folder.objects.create(project=project, name="过程资料", created_by=admin)
    Folder.objects.create(project=project, name="检测报告", created_by=admin)
    client.force_login(admin)

    response = client.get(f"/api/v1/folders/tree/?project_id={project.id}")

    assert response.status_code == 200
    names = {node["name"] for node in response.json()}
    assert "竣工资料档案" in names
    assert "过程资料" not in names
    assert "检测报告" not in names


@pytest.mark.django_db
def test_project_folder_tree_does_not_create_missing_standard_roots(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    client.force_login(admin)

    response = client.get(f"/api/v1/folders/tree/?project_id={project.id}")

    assert response.status_code == 200
    assert response.json() == []
    assert not Folder.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_public_folder_tree_exposes_archive_years_without_project_containers(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    active_project = Project.objects.create(name="进行中项目", code="P001", created_by=admin)
    archived_project = Project.objects.create(name="归档项目", code="P002", created_by=admin)
    active_root = Folder.objects.create(
        project=active_project,
        name="竣工资料档案",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    archive_root = Folder.objects.create(
        project=None,
        parent=None,
        name="已归档文件",
        code="PUBLIC-ARCHIVE",
        is_system_root=True,
        sort_order=99,
        created_by=admin,
    )
    archive_year = Folder.objects.create(
        project=None,
        parent=archive_root,
        name="2026年归档资料",
        code="PUBLIC-ARCHIVE-2026",
        created_by=admin,
    )
    project_container = Folder.objects.create(
        project=archived_project,
        parent=archive_year,
        name="P002 归档项目",
        code=f"PROJECT-ARCHIVE-{archived_project.id}",
        created_by=admin,
    )
    archived_root = Folder.objects.create(
        project=archived_project,
        parent=project_container,
        name="竣工资料档案",
        code="PUBLIC-COMPLETION",
        created_by=admin,
    )
    client.force_login(admin)

    response = client.get("/api/v1/folders/tree/?project_id=public")

    assert response.status_code == 200
    payload = response.json()
    archive_payload = next(node for node in payload if node["id"] == archive_root.id)
    year_payload = archive_payload["children"][0]
    assert year_payload["id"] == archive_year.id
    assert year_payload["children"] == []
    assert project_container.id not in _tree_ids(payload)
    assert archived_root.id not in _tree_ids(payload)
    assert all(node["id"] != active_root.id for node in payload)


def _tree_ids(nodes):
    ids = []
    for node in nodes:
        ids.append(node["id"])
        ids.extend(_tree_ids(node["children"]))
    return ids


@pytest.mark.django_db
def test_system_root_folder_cannot_move_or_disable(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    root = Folder.objects.create(name="公司资质", is_system_root=True, created_by=admin)
    client.force_login(admin)

    move_response = client.post(
        f"/api/v1/folders/{root.id}/move/",
        {"parent": None},
        content_type="application/json",
    )
    disable_response = client.post(f"/api/v1/folders/{root.id}/disable/")

    root.refresh_from_db()
    assert move_response.status_code == 400
    assert disable_response.status_code == 400
    assert root.is_active is True
