import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.documents.models import Document, DocumentVersion
from apps.folders.models import Folder
from apps.projects.models import Project, ProjectMember
from apps.projects.services import create_project

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


@pytest.mark.django_db
def test_system_admin_can_create_project_and_manager_membership(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    client.force_login(admin)

    response = client.post(
        "/api/v1/projects/",
        {
            "name": "风场检测",
            "code": "P001",
            "description": "一期",
            "manager": manager.id,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    project = Project.objects.get(code="P001")
    membership = ProjectMember.objects.get(project=project, user=manager)
    assert project.created_by == admin
    assert membership.role == ProjectMember.Role.MANAGER
    assert membership.can_manage_permission is True
    assert list(
        Folder.objects.filter(project=project, parent__isnull=True)
        .order_by("sort_order")
        .values_list(
            "name",
            flat=True,
        )
    ) == [
        "竣工资料档案",
        "公司资质",
        "技术方案",
        "报告模板",
        "工器具及年检资质",
        "仪器仪表设备年检资质",
        "车辆年检资质",
        "人员资质",
        "人员保险单",
        "个人防护用品",
    ]
    assert AuditLog.objects.filter(action="project.create", result="success").exists()


@pytest.mark.django_db
def test_non_admin_cannot_create_project(client):
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    client.force_login(manager)

    response = client.post(
        "/api/v1/projects/",
        {"name": "风场检测", "code": "P001"},
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_project_list_is_filtered_by_membership(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    other = make_user("other", User.Role.DATA_OPERATOR)
    visible = Project.objects.create(name="可见项目", code="P001", created_by=admin)
    Project.objects.create(name="不可见项目", code="P002", created_by=admin)
    ProjectMember.objects.create(project=visible, user=operator, role=ProjectMember.Role.VIEWER)
    client.force_login(operator)

    response = client.get("/api/v1/projects/")

    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["results"]}
    assert codes == {"P001"}
    client.force_login(other)
    assert client.get("/api/v1/projects/").json()["results"] == []


@pytest.mark.django_db
def test_project_manager_can_update_only_authorized_project(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="授权项目", code="P001", created_by=admin)
    other_project = Project.objects.create(name="未授权项目", code="P002", created_by=admin)
    ProjectMember.objects.create(
        project=project,
        user=manager,
        role=ProjectMember.Role.MANAGER,
        can_manage_permission=True,
    )
    client.force_login(manager)

    ok_response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"description": "已修改"},
        content_type="application/json",
    )
    hidden_response = client.patch(
        f"/api/v1/projects/{other_project.id}/",
        {"description": "越权修改"},
        content_type="application/json",
    )

    project.refresh_from_db()
    other_project.refresh_from_db()
    assert ok_response.status_code == 200
    assert project.description == "已修改"
    assert hidden_response.status_code == 404
    assert other_project.description == ""


@pytest.mark.django_db
def test_only_system_admin_can_delete_project(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    project = create_project(actor=admin, data={"name": "授权项目", "code": "P001"})
    ProjectMember.objects.create(
        project=project,
        user=manager,
        role=ProjectMember.Role.MANAGER,
    )
    client.force_login(manager)

    denied_response = client.delete(f"/api/v1/projects/{project.id}/")
    client.force_login(admin)
    deleted_response = client.delete(f"/api/v1/projects/{project.id}/")

    assert denied_response.status_code == 403
    assert deleted_response.status_code == 204
    assert not Project.objects.filter(pk=project.pk).exists()
    assert AuditLog.objects.filter(action="project.delete", result="success").exists()


@pytest.mark.django_db
def test_system_admin_can_delete_empty_project_with_nested_folders(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = create_project(actor=admin, data={"name": "空项目", "code": "P001"})
    root_folder = Folder.objects.filter(project=project, parent__isnull=True).first()
    child_folder = Folder.objects.create(project=project, parent=root_folder, name="空子目录")
    Folder.objects.create(project=project, parent=child_folder, name="空孙目录")
    client.force_login(admin)

    response = client.delete(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 204
    assert not Project.objects.filter(pk=project.pk).exists()
    assert not Folder.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_system_admin_cannot_delete_project_with_documents(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = create_project(actor=admin, data={"name": "含资料项目", "code": "P001"})
    folder = Folder.objects.filter(project=project, parent__isnull=True).first()
    Document.objects.create(project=project, folder=folder, title="检测报告", created_by=admin)
    client.force_login(admin)

    response = client.delete(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 400
    assert "请先归档项目" in response.json()["message"]
    assert Project.objects.filter(pk=project.pk).exists()
    assert Document.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_system_admin_cannot_delete_project_when_folder_contains_document(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = create_project(actor=admin, data={"name": "目录含资料项目", "code": "P001"})
    other_project = create_project(actor=admin, data={"name": "其他项目", "code": "P002"})
    folder = Folder.objects.filter(project=project, parent__isnull=True).first()
    Document.objects.create(
        project=other_project,
        folder=folder,
        title="错挂资料",
        created_by=admin,
    )
    client.force_login(admin)

    response = client.delete(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 400
    assert "项目中仍有资料" in response.json()["message"]
    assert Project.objects.filter(pk=project.pk).exists()


@pytest.mark.django_db
def test_system_admin_can_delete_project_with_only_removed_documents(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = create_project(actor=admin, data={"name": "已清空项目", "code": "P001"})
    folder = Folder.objects.filter(project=project, parent__isnull=True).first()
    document = Document.objects.create(
        project=project,
        folder=folder,
        title="已删除资料",
        created_by=admin,
        deleted_at=timezone.now(),
        deleted_by=admin,
    )
    version = DocumentVersion.objects.create(
        document=document,
        version_number=1,
        original_filename="removed.pdf",
        content_type="application/pdf",
        file_size=1,
        sha256="0" * 64,
        storage_path="removed.pdf",
        uploaded_by=admin,
    )
    document.current_version = version
    document.save(update_fields=["current_version", "updated_at"])
    client.force_login(admin)

    response = client.delete(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 204
    assert not Project.objects.filter(pk=project.pk).exists()
    assert not Document.objects.filter(pk=document.pk).exists()
    assert not DocumentVersion.objects.filter(pk=version.pk).exists()


@pytest.mark.django_db
def test_only_system_admin_can_manage_project_members(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    viewer = make_user("viewer", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    ProjectMember.objects.create(
        project=project,
        user=manager,
        role=ProjectMember.Role.MANAGER,
        can_manage_permission=True,
    )
    ProjectMember.objects.create(project=project, user=viewer, role=ProjectMember.Role.VIEWER)
    client.force_login(viewer)
    viewer_denied_response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"user": operator.id, "role": ProjectMember.Role.OPERATOR},
        content_type="application/json",
    )
    client.force_login(manager)
    manager_denied_response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"user": operator.id, "role": ProjectMember.Role.OPERATOR},
        content_type="application/json",
    )
    client.force_login(admin)
    allowed_response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {
            "user": operator.id,
            "role": ProjectMember.Role.OPERATOR,
        },
        content_type="application/json",
    )

    assert viewer_denied_response.status_code == 403
    assert manager_denied_response.status_code == 403
    assert allowed_response.status_code == 201
    assert "can_upload" not in allowed_response.json()
    assert AuditLog.objects.filter(action="permission.denied", result="denied").exists()


@pytest.mark.django_db
def test_duplicate_project_member_returns_400(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    ProjectMember.objects.create(project=project, user=operator, role=ProjectMember.Role.VIEWER)
    client.force_login(admin)

    response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"user": operator.id, "role": ProjectMember.Role.OPERATOR},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_hidden_project_members_endpoint_returns_404(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    operator = make_user("operator", User.Role.DATA_OPERATOR)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    client.force_login(operator)

    response = client.get(f"/api/v1/projects/{project.id}/members/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_archive_and_unarchive_rules(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(name="项目", code="P001", created_by=admin)
    ProjectMember.objects.create(project=project, user=manager, role=ProjectMember.Role.MANAGER)
    client.force_login(manager)

    archive_response = client.post(f"/api/v1/projects/{project.id}/archive/")
    unarchive_denied_response = client.post(f"/api/v1/projects/{project.id}/unarchive/")
    client.force_login(admin)
    unarchive_response = client.post(f"/api/v1/projects/{project.id}/unarchive/")

    project.refresh_from_db()
    assert archive_response.status_code == 200
    assert unarchive_denied_response.status_code == 403
    assert unarchive_response.status_code == 200
    assert project.status == Project.Status.ACTIVE


@pytest.mark.django_db
def test_archive_project_groups_folders_by_archive_year(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(name="风场检测", code="P001", created_by=admin)
    root_folder = Folder.objects.create(project=project, name="检测报告", created_by=admin)
    child_folder = Folder.objects.create(
        project=project,
        parent=root_folder,
        name="叶片检测",
        created_by=admin,
    )
    document = Document.objects.create(
        project=project,
        folder=child_folder,
        title="检测报告",
        created_by=admin,
    )
    client.force_login(admin)

    response = client.post(f"/api/v1/projects/{project.id}/archive/")

    project.refresh_from_db()
    year = project.archived_at.year
    archive_root = Folder.objects.get(project=None, parent=None, name="已归档文件")
    archive_year = Folder.objects.get(project=None, parent=archive_root, name=f"{year}年归档资料")
    project_container = Folder.objects.get(project=project, code=f"PROJECT-ARCHIVE-{project.id}")
    root_folder.refresh_from_db()
    child_folder.refresh_from_db()
    document.refresh_from_db()
    document_list_response = client.get(f"/api/v1/documents/?folder={archive_root.id}")

    assert response.status_code == 200
    assert archive_root.is_system_root is True
    assert archive_year.is_system_root is False
    assert project_container.parent == archive_year
    assert root_folder.parent == project_container
    assert child_folder.parent == root_folder
    assert document.project == project
    assert document_list_response.status_code == 200
    assert document_list_response.json()["count"] == 1
    assert document_list_response.json()["results"][0]["id"] == document.id


@pytest.mark.django_db
def test_archived_project_rejects_non_admin_update(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    manager = make_user("manager", User.Role.PROJECT_MANAGER)
    project = Project.objects.create(
        name="项目",
        code="P001",
        created_by=admin,
        status=Project.Status.ARCHIVED,
    )
    ProjectMember.objects.create(project=project, user=manager, role=ProjectMember.Role.MANAGER)
    client.force_login(manager)

    response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"description": "归档后修改"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_archived_project_rejects_admin_update(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    project = Project.objects.create(
        name="项目",
        code="P001",
        created_by=admin,
        status=Project.Status.ARCHIVED,
    )
    client.force_login(admin)

    response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"description": "管理员直接修改"},
        content_type="application/json",
    )

    project.refresh_from_db()
    assert response.status_code == 400
    assert project.description == ""
