from typing import Any

from django.utils import timezone

from apps.audit.services import audit_log

from .models import Notification


def create_notification(
    *,
    recipient: Any,
    title: str,
    message: str,
    category: str = Notification.Category.SYSTEM,
    resource_type: str = "",
    resource_id: str = "",
) -> Notification:
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def mark_notification_read(
    *,
    actor: Any,
    notification: Notification,
    request: Any = None,
) -> Notification:
    if notification.is_read:
        return notification
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])
    audit_log(
        user=actor,
        action="notification.read",
        resource=notification,
        result="success",
        request=request,
    )
    return notification


def mark_notification_unread(
    *,
    actor: Any,
    notification: Notification,
    request: Any = None,
) -> Notification:
    if not notification.is_read:
        return notification
    notification.is_read = False
    notification.read_at = None
    notification.save(update_fields=["is_read", "read_at"])
    audit_log(
        user=actor,
        action="notification.unread",
        resource=notification,
        result="success",
        request=request,
    )
    return notification
