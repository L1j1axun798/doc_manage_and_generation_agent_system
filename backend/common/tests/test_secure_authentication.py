import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()


def mark_verified(client, user) -> None:
    session = client.session
    session["webauthn_verified_user_id"] = user.pk
    session.save()


@pytest.mark.django_db
def test_business_api_rejects_password_only_session(client, settings):
    settings.LOGIN_REQUIRE_WEBAUTHN = True
    settings.API_ENFORCE_PASSWORD_CHANGE = True
    user = User.objects.create_user(
        username="password-only",
        password="Password123!",
        real_name="仅密码用户",
        must_change_password=False,
    )
    client.force_login(user)

    response = client.get("/api/v1/documents/")

    assert response.status_code in {401, 403}
    assert response.json()["code"] == "webauthn_required"


@pytest.mark.django_db
def test_verified_session_can_access_business_api(client, settings):
    settings.LOGIN_REQUIRE_WEBAUTHN = True
    settings.API_ENFORCE_PASSWORD_CHANGE = True
    user = User.objects.create_user(
        username="verified",
        password="Password123!",
        real_name="已验证用户",
        must_change_password=False,
    )
    client.force_login(user)
    mark_verified(client, user)

    assert client.get("/api/v1/documents/").status_code == 200


@pytest.mark.django_db
def test_password_change_requirement_is_enforced_by_api(client, settings):
    settings.LOGIN_REQUIRE_WEBAUTHN = True
    settings.API_ENFORCE_PASSWORD_CHANGE = True
    user = User.objects.create_user(
        username="must-change",
        password="Password123!",
        real_name="待改密用户",
        must_change_password=True,
    )
    client.force_login(user)
    mark_verified(client, user)

    denied = client.get("/api/v1/documents/")
    changed = client.post(
        "/api/v1/auth/change-password/",
        {"old_password": "Password123!", "new_password": "NewPassword123!"},
        content_type="application/json",
    )

    assert denied.status_code == 403
    assert denied.json()["code"] == "password_change_required"
    assert changed.status_code == 204
    assert client.get("/api/v1/documents/").status_code == 200


@pytest.mark.django_db
def test_login_is_rate_limited_per_account(client):
    cache.clear()
    User.objects.create_user(
        username="rate-limited-user",
        password="Password123!",
        real_name="限速用户",
    )

    responses = [
        client.post(
            "/api/v1/auth/login/",
            {"username": "rate-limited-user", "password": "wrong-password"},
            content_type="application/json",
        )
        for _ in range(6)
    ]

    assert responses[-1].status_code == 429
