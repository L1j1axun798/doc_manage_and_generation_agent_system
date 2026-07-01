import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.audit.models import AuditLog

User = get_user_model()


@pytest.mark.django_db
def test_admin_can_create_user(client):
    admin = User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    client.force_login(admin)

    response = client.post(
        "/api/v1/users/",
        {
            "username": "operator",
            "password": "OperatorPass123!",
            "real_name": "资料员",
            "role": User.Role.DATA_OPERATOR,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    user = User.objects.get(username="operator")
    assert user.real_name == "资料员"
    assert user.check_password("OperatorPass123!")
    assert AuditLog.objects.filter(action="user.create", result="success").exists()


@pytest.mark.django_db
def test_admin_can_create_temporary_user(client):
    admin = User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    client.force_login(admin)

    response = client.post(
        "/api/v1/users/",
        {
            "username": "temp-user",
            "password": "TempUserPass123!",
            "real_name": "临时用户",
            "role": User.Role.TEMPORARY_USER,
            "must_change_password": False,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    user = User.objects.get(username="temp-user")
    assert user.role == User.Role.TEMPORARY_USER
    assert user.is_temporary_user is True
    assert user.check_password("TempUserPass123!")


@pytest.mark.django_db
def test_non_admin_cannot_create_user(client):
    user = User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )
    client.force_login(user)

    response = client.post(
        "/api/v1/users/",
        {
            "username": "other",
            "password": "OtherPass123!",
            "real_name": "其他人",
            "role": User.Role.DATA_OPERATOR,
        },
        content_type="application/json",
    )

    assert response.status_code == 403
    assert AuditLog.objects.filter(action="permission.denied", result="denied").exists()


@pytest.mark.django_db
def test_public_register_endpoint_does_not_exist(client):
    response = client.post(
        "/api/v1/auth/register/",
        {
            "username": "public",
            "password": "PublicPass123!",
            "real_name": "公开注册",
        },
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_user_list_can_order_active_users_first(client):
    admin = User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    inactive_user = User.objects.create_user(
        username="inactive",
        password="InactivePass123!",
        real_name="停用用户",
        role=User.Role.DATA_OPERATOR,
        is_active=False,
    )
    active_user = User.objects.create_user(
        username="active",
        password="ActivePass123!",
        real_name="启用用户",
        role=User.Role.DATA_OPERATOR,
    )
    client.force_login(admin)

    response = client.get("/api/v1/users/", {"ordering": "-is_active,id"})

    assert response.status_code == 200
    usernames = [item["username"] for item in response.json()["results"]]
    assert usernames.index(active_user.username) < usernames.index(inactive_user.username)


def test_user_required_fields_include_real_name() -> None:
    assert "real_name" in User.REQUIRED_FIELDS


@pytest.mark.django_db
def test_inactive_user_cannot_login(client):
    User.objects.create_user(
        username="inactive",
        password="InactivePass123!",
        real_name="停用用户",
        role=User.Role.DATA_OPERATOR,
        is_active=False,
    )

    response = client.post(
        reverse("auth-login"),
        {"username": "inactive", "password": "InactivePass123!"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert AuditLog.objects.filter(action="auth.login", result="failure").exists()


@pytest.mark.django_db
def test_login_logout_and_me(client):
    user = User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )

    login_response = client.post(
        reverse("auth-login"),
        {"username": "operator", "password": "OperatorPass123!"},
        content_type="application/json",
    )
    me_response = client.get(reverse("auth-me"))
    logout_response = client.post(reverse("auth-logout"))

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["id"] == user.id
    assert logout_response.status_code == 204
    assert AuditLog.objects.filter(action="auth.login", result="success").exists()
    assert AuditLog.objects.filter(action="auth.logout", result="success").exists()


@pytest.mark.django_db
def test_change_password_clears_must_change_password(client):
    user = User.objects.create_user(
        username="operator",
        password="OldPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
        must_change_password=True,
    )
    client.force_login(user)

    response = client.post(
        reverse("auth-change-password"),
        {"old_password": "OldPass123!", "new_password": "NewPass123!"},
        content_type="application/json",
    )

    user.refresh_from_db()
    assert response.status_code == 204
    assert user.must_change_password is False
    assert user.check_password("NewPass123!")


@pytest.mark.django_db
def test_admin_can_disable_and_reset_password(client):
    admin = User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    user = User.objects.create_user(
        username="operator",
        password="OldPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )
    client.force_login(admin)

    reset_response = client.post(
        f"/api/v1/users/{user.id}/reset-password/",
        {"new_password": "ResetPass123!"},
        content_type="application/json",
    )
    disable_response = client.post(f"/api/v1/users/{user.id}/disable/")

    user.refresh_from_db()
    assert reset_response.status_code == 200
    assert reset_response.json()["must_change_password"] is True
    assert user.check_password("ResetPass123!")
    assert user.is_active is False
    assert disable_response.status_code == 204
