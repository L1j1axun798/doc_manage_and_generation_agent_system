import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


@pytest.mark.django_db
def test_system_admin_can_query_and_filter_audit_logs(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    user = make_user("user", User.Role.DATA_OPERATOR)
    AuditLog.objects.create(user=user, action="document.download", result="success")
    AuditLog.objects.create(user=user, action="document.delete", result="denied")
    client.force_login(admin)

    response = client.get("/api/v1/audit-logs/?action=document.download")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["action"] == "document.download"
    assert payload["results"][0]["user_username"] == user.username


@pytest.mark.django_db
def test_non_admin_cannot_query_audit_logs(client):
    user = make_user("user", User.Role.DATA_OPERATOR)
    AuditLog.objects.create(user=user, action="document.download", result="success")
    client.force_login(user)

    response = client.get("/api/v1/audit-logs/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_system_admin_cannot_delete_audit_log(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    user = make_user("user", User.Role.DATA_OPERATOR)
    target = AuditLog.objects.create(
        user=user,
        action="document.download",
        resource_type="Document",
        resource_id="1",
        result="success",
    )
    client.force_login(admin)

    response = client.delete(f"/api/v1/audit-logs/{target.pk}/")

    assert response.status_code == 405
    assert AuditLog.objects.filter(pk=target.pk).exists()


@pytest.mark.django_db
def test_non_admin_cannot_delete_audit_log(client):
    user = make_user("user", User.Role.DATA_OPERATOR)
    target = AuditLog.objects.create(user=user, action="document.download", result="success")
    client.force_login(user)

    response = client.delete(f"/api/v1/audit-logs/{target.pk}/")

    assert response.status_code == 403
    assert AuditLog.objects.filter(pk=target.pk).exists()
    assert not AuditLog.objects.filter(action="audit_log.delete").exists()


@pytest.mark.django_db
def test_system_admin_cannot_bulk_delete_audit_logs(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    user = make_user("user", User.Role.DATA_OPERATOR)
    first = AuditLog.objects.create(user=user, action="document.download", result="success")
    second = AuditLog.objects.create(user=user, action="document.delete", result="denied")
    kept = AuditLog.objects.create(user=user, action="document.create", result="success")
    client.force_login(admin)

    response = client.post(
        "/api/v1/audit-logs/bulk-delete/",
        data={"ids": [first.pk, second.pk]},
        content_type="application/json",
    )

    assert response.status_code == 405
    assert AuditLog.objects.filter(pk__in=[first.pk, second.pk]).count() == 2
    assert AuditLog.objects.filter(pk=kept.pk).exists()


@pytest.mark.django_db
def test_bulk_delete_route_is_not_available(client):
    admin = make_user("admin", User.Role.SYSTEM_ADMIN)
    user = make_user("user", User.Role.DATA_OPERATOR)
    target = AuditLog.objects.create(user=user, action="document.download", result="success")
    client.force_login(admin)

    empty_response = client.post(
        "/api/v1/audit-logs/bulk-delete/",
        data={"ids": []},
        content_type="application/json",
    )
    missing_response = client.post(
        "/api/v1/audit-logs/bulk-delete/",
        data={"ids": [target.pk, 9999]},
        content_type="application/json",
    )

    assert empty_response.status_code == 405
    assert missing_response.status_code == 405
    assert AuditLog.objects.filter(pk=target.pk).exists()
    assert not AuditLog.objects.filter(action="audit_log.bulk_delete").exists()
