import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog
from apps.notifications.services import create_notification

User = get_user_model()


def make_user(username: str, role: str):
    return User.objects.create_user(
        username=username,
        password="Password123!",
        real_name=username,
        role=role,
    )


@pytest.mark.django_db
def test_user_only_lists_own_notifications_and_filters_read_state(client):
    user = make_user("user", User.Role.DATA_OPERATOR)
    other = make_user("other", User.Role.DATA_OPERATOR)
    mine = create_notification(recipient=user, title="我的通知", message="内容")
    create_notification(recipient=other, title="他人通知", message="内容")
    read = create_notification(recipient=user, title="已读通知", message="内容")
    read.is_read = True
    read.save(update_fields=["is_read"])
    client.force_login(user)

    response = client.get("/api/v1/notifications/?is_read=false")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == mine.id


@pytest.mark.django_db
def test_mark_notification_read_and_unread(client):
    user = make_user("user", User.Role.DATA_OPERATOR)
    notification = create_notification(recipient=user, title="通知", message="内容")
    client.force_login(user)

    read_response = client.post(f"/api/v1/notifications/{notification.id}/read/")
    unread_response = client.post(f"/api/v1/notifications/{notification.id}/unread/")

    notification.refresh_from_db()
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True
    assert unread_response.status_code == 200
    assert unread_response.json()["is_read"] is False
    assert notification.is_read is False
    assert AuditLog.objects.filter(action="notification.read", result="success").exists()
    assert AuditLog.objects.filter(action="notification.unread", result="success").exists()


@pytest.mark.django_db
def test_cannot_access_other_user_notification(client):
    user = make_user("user", User.Role.DATA_OPERATOR)
    other = make_user("other", User.Role.DATA_OPERATOR)
    notification = create_notification(recipient=other, title="他人通知", message="内容")
    client.force_login(user)

    response = client.post(f"/api/v1/notifications/{notification.id}/read/")

    assert response.status_code == 404
