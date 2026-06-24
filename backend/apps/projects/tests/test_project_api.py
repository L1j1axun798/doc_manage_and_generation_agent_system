import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog
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
def test_project_member_permissions_control_member_management(client):
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
    denied_response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"user": operator.id, "role": ProjectMember.Role.OPERATOR},
        content_type="application/json",
    )
    client.force_login(manager)
    allowed_response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {
            "user": operator.id,
            "role": ProjectMember.Role.OPERATOR,
            "can_upload": True,
        },
        content_type="application/json",
    )

    assert denied_response.status_code == 403
    assert allowed_response.status_code == 201
    assert ProjectMember.objects.get(project=project, user=operator).can_upload is True
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
