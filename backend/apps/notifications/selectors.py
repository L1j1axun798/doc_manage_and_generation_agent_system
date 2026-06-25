from typing import Any

from django.db.models import QuerySet

from .models import Notification


def notifications_for_user(user: Any) -> QuerySet[Notification]:
    return Notification.objects.filter(recipient=user)
