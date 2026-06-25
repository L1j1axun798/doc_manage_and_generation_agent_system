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
