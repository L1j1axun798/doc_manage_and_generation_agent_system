from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import WebAuthnCredential, WebAuthnEnrollmentTicket
from apps.audit.models import AuditLog

User = get_user_model()


def create_webauthn_credential(user, credential_id: str = "credential-001") -> WebAuthnCredential:
    return WebAuthnCredential.objects.create(
        user=user,
        name="本人手机",
        credential_id=credential_id,
        public_key=b"public-key",
        sign_count=0,
        transports=["internal"],
        device_type="single_device",
    )


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
def test_user_delete_endpoint_is_disabled(client):
    admin = User.objects.create_user(
        username="admin-delete-disabled",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    target = User.objects.create_user(
        username="target-delete-disabled",
        password="TargetPass123!",
        real_name="目标用户",
    )
    client.force_login(admin)

    response = client.delete(f"/api/v1/users/{target.pk}/")

    assert response.status_code == 405
    assert User.objects.filter(pk=target.pk).exists()


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
@override_settings(LOGIN_REQUIRE_WEBAUTHN=True)
@pytest.mark.parametrize("remember_me", [False, True])
def test_login_requires_webauthn_before_session(client, monkeypatch, remember_me):
    user = User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )
    create_webauthn_credential(user)

    login_response = client.post(
        reverse("auth-login"),
        {
            "username": "operator",
            "password": "OperatorPass123!",
            "remember_me": remember_me,
        },
        content_type="application/json",
    )

    assert login_response.status_code == 200
    assert login_response.json()["status"] == "webauthn_required"
    assert login_response.json()["pending_token"]
    assert client.get(reverse("auth-me")).status_code in {401, 403}

    monkeypatch.setattr("apps.accounts.views.finish_login", lambda **kwargs: user)
    verify_response = client.post(
        reverse("auth-webauthn-login-verify"),
        {
            "pending_token": login_response.json()["pending_token"],
            "credential": {"id": "credential-001"},
        },
        content_type="application/json",
    )

    assert verify_response.status_code == 200
    assert client.session.get_expire_at_browser_close() is (not remember_me)
    session_cookie_max_age = verify_response.cookies[settings.SESSION_COOKIE_NAME]["max-age"]
    if remember_me:
        assert int(session_cookie_max_age) == settings.SESSION_COOKIE_AGE
    else:
        assert session_cookie_max_age == ""

    me_response = client.get(reverse("auth-me"))
    logout_response = client.post(reverse("auth-logout"))

    assert me_response.status_code == 200
    assert me_response.json()["id"] == user.id
    assert logout_response.status_code == 204
    assert AuditLog.objects.filter(action="auth.password_verified", result="success").exists()
    assert AuditLog.objects.filter(action="auth.login", result="success").exists()
    assert AuditLog.objects.filter(action="auth.logout", result="success").exists()


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=True)
def test_legacy_session_without_webauthn_marker_is_rejected_on_me(client):
    user = User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )
    client.force_login(user)

    response = client.get(reverse("auth-me"))

    assert response.status_code in {401, 403}
    assert "重新登录" in str(response.json())


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=True)
def test_login_without_bound_webauthn_device_is_denied(client):
    User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )

    response = client.post(
        reverse("auth-login"),
        {"username": "operator", "password": "OperatorPass123!"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "本人验证设备" in str(response.json())


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=False)
def test_password_login_creates_usable_session_when_webauthn_is_disabled(client):
    user = User.objects.create_user(
        username="password-only-login",
        password="PasswordOnly123!",
        real_name="Password-only user",
        role=User.Role.DATA_OPERATOR,
    )

    response = client.post(
        reverse("auth-login"),
        {
            "username": user.username,
            "password": "PasswordOnly123!",
            "remember_me": False,
        },
        content_type="application/json",
    )
    me_response = client.get(reverse("auth-me"))

    assert response.status_code == 200
    assert response.json()["status"] == "authenticated"
    assert response.json()["user"]["id"] == user.id
    assert client.session.get_expire_at_browser_close() is True
    assert response.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == ""
    assert me_response.status_code == 200
    login_audit = AuditLog.objects.get(action="auth.login", result="success")
    assert login_audit.after_data == {"verification_method": "password"}


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=False)
def test_password_login_remember_me_uses_configured_session_lifetime(client):
    user = User.objects.create_user(
        username="remembered-login",
        password="RememberedLogin123!",
        real_name="Remembered user",
        role=User.Role.DATA_OPERATOR,
    )

    response = client.post(
        reverse("auth-login"),
        {
            "username": user.username,
            "password": "RememberedLogin123!",
            "remember_me": True,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert client.session.get_expire_at_browser_close() is False
    assert (
        int(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"])
        == settings.SESSION_COOKIE_AGE
    )


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=False)
def test_new_login_replaces_the_previous_session(client):
    user = User.objects.create_user(
        username="single-session-user",
        password="SingleSession123!",
        real_name="Single session user",
        role=User.Role.DATA_OPERATOR,
        must_change_password=False,
    )
    second_client = Client()

    first_login = client.post(
        reverse("auth-login"),
        {"username": user.username, "password": "SingleSession123!"},
        content_type="application/json",
    )
    first_session_key = client.session.session_key
    second_login = second_client.post(
        reverse("auth-login"),
        {"username": user.username, "password": "SingleSession123!"},
        content_type="application/json",
    )
    second_session_key = second_client.session.session_key

    assert first_login.status_code == 200
    assert second_login.status_code == 200
    assert first_session_key != second_session_key
    user.refresh_from_db()
    assert user.active_session_key == second_session_key

    replaced_response = client.get(reverse("auth-me"))
    current_response = second_client.get(reverse("auth-me"))

    assert replaced_response.status_code == 403
    assert replaced_response.json()["code"] == "session_replaced"
    assert "其他设备或浏览器重新登录" in replaced_response.json()["message"]
    assert replaced_response.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == 0
    assert current_response.status_code == 200
    replacement_audit = AuditLog.objects.filter(
        action="auth.login",
        result="success",
        after_data__replaced_existing_session=True,
    )
    assert replacement_audit.exists()


@pytest.mark.django_db
@override_settings(LOGIN_REQUIRE_WEBAUTHN=False)
def test_logout_from_replaced_session_does_not_clear_current_session(client):
    user = User.objects.create_user(
        username="replaced-logout-user",
        password="ReplacedLogout123!",
        real_name="Replaced logout user",
        role=User.Role.DATA_OPERATOR,
        must_change_password=False,
    )
    second_client = Client()
    credentials = {"username": user.username, "password": "ReplacedLogout123!"}

    assert (
        client.post(reverse("auth-login"), credentials, content_type="application/json").status_code
        == 200
    )
    assert (
        second_client.post(
            reverse("auth-login"), credentials, content_type="application/json"
        ).status_code
        == 200
    )

    assert client.post(reverse("auth-logout")).status_code == 204
    assert second_client.get(reverse("auth-me")).status_code == 200
    user.refresh_from_db()
    assert user.active_session_key == second_client.session.session_key


@pytest.mark.django_db
def test_first_request_from_a_legacy_session_claims_the_single_session(client):
    user = User.objects.create_user(
        username="legacy-session-user",
        password="LegacySession123!",
        real_name="Legacy session user",
        role=User.Role.DATA_OPERATOR,
        must_change_password=False,
    )
    client.force_login(user)
    assert user.active_session_key is None

    response = client.get(reverse("auth-me"))

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.active_session_key == client.session.session_key


@pytest.mark.django_db
def test_admin_can_create_and_reset_webauthn_ticket(client):
    admin = User.objects.create_user(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    user = User.objects.create_user(
        username="operator",
        password="OperatorPass123!",
        real_name="资料员",
        role=User.Role.DATA_OPERATOR,
    )
    create_webauthn_credential(user)
    client.force_login(admin)

    ticket_response = client.post(
        reverse("auth-webauthn-enrollment-ticket"),
        {"user": user.id},
        content_type="application/json",
    )
    reset_response = client.post(f"/api/v1/users/{user.id}/webauthn-reset/")

    assert ticket_response.status_code == 201
    assert ticket_response.json()["token"]
    assert reset_response.status_code == 200
    assert reset_response.json()["revoked_credentials"] == 1
    assert user.webauthn_credentials.filter(is_active=True).count() == 0


@pytest.mark.django_db
@override_settings(WEBAUTHN_ENROLLMENT_TICKET_TTL_SECONDS=60)
def test_webauthn_ticket_requires_admin_and_lasts_at_least_three_hours(client):
    admin = User.objects.create_user(
        username="ticket-admin",
        password="AdminPass123!",
        real_name="管理员",
        role=User.Role.SYSTEM_ADMIN,
    )
    operator = User.objects.create_user(
        username="ticket-operator",
        password="OperatorPass123!",
        real_name="资料管理员",
        role=User.Role.DATA_OPERATOR,
    )
    target = User.objects.create_user(
        username="ticket-target",
        password="TargetPass123!",
        real_name="待绑定人员",
        role=User.Role.DATA_OPERATOR,
    )
    client.force_login(operator)
    denied_response = client.post(
        reverse("auth-webauthn-enrollment-ticket"),
        {"user": target.id},
        content_type="application/json",
    )

    before_creation = timezone.now()
    client.force_login(admin)
    created_response = client.post(
        reverse("auth-webauthn-enrollment-ticket"),
        {"user": target.id},
        content_type="application/json",
    )

    ticket = WebAuthnEnrollmentTicket.objects.get(user=target)
    assert denied_response.status_code == 403
    assert created_response.status_code == 201
    assert ticket.expires_at >= before_creation + timedelta(hours=3)
    assert ticket.expires_at <= timezone.now() + timedelta(hours=3, seconds=5)


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
    assert user.active_session_key == client.session.session_key


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
