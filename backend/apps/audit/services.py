from ipaddress import ip_address
from typing import Any

from django.conf import settings

from .models import AuditLog


def audit_log(
    *,
    user: Any,
    action: str,
    result: str,
    request: Any = None,
    resource: Any = None,
    resource_type: str = "",
    resource_id: str = "",
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    error_message: str = "",
) -> None:
    if resource is not None:
        resource_type = resource_type or resource.__class__.__name__
        resource_id = resource_id or str(resource.pk)

    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        request_id=getattr(request, "request_id", "") if request is not None else "",
        before_data=before_data,
        after_data=after_data,
        error_message=error_message,
    )


def _get_client_ip(request: Any) -> str | None:
    if request is None:
        return None
    candidate = (
        request.META.get("HTTP_X_REAL_IP")
        if getattr(settings, "TRUST_PROXY_HEADERS", False)
        else request.META.get("REMOTE_ADDR")
    )
    if not candidate:
        return None
    try:
        return str(ip_address(candidate.strip()))
    except ValueError:
        return None


def _get_user_agent(request: Any) -> str:
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")
