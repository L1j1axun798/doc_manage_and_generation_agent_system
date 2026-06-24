import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.audit.models import AuditLog

User = get_user_model()


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(
        username="admin",
        password="AdminPass123!",
        real_name="管理员",
        email="admin@example.com",
    )
    client.force_login(admin)
    return client


@pytest.mark.django_db
def test_admin_user_add_success_redirects_and_writes_audit(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "operator",
            "real_name": "资料员",
            "role": User.Role.DATA_OPERATOR,
            "employee_no": "",
            "phone": "",
            "email": "",
            "must_change_password": "on",
            "password1": "OperatorPass123!",
            "password2": "OperatorPass123!",
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    assert User.objects.filter(username="operator", real_name="资料员").exists()
    assert AuditLog.objects.filter(action="user.create", result="success").exists()


@pytest.mark.django_db
def test_admin_user_add_missing_real_name_stays_on_form(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "operator",
            "role": User.Role.DATA_OPERATOR,
            "employee_no": "",
            "phone": "",
            "email": "",
            "must_change_password": "on",
            "password1": "OperatorPass123!",
            "password2": "OperatorPass123!",
            "_save": "Save",
        },
    )

    assert response.status_code == 200
    assert not User.objects.filter(username="operator").exists()
    assert not AuditLog.objects.filter(action="user.create", result="success").exists()


@pytest.mark.django_db
def test_admin_user_changelist_facets_loads(admin_client):
    response = admin_client.get(reverse("admin:accounts_user_changelist"), {"_facets": "True"})

    assert response.status_code == 200
