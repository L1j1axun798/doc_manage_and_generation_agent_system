from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.documents.models import Document

from .models import DocumentGrant
from .permissions import can_manage_document_grants


@transaction.atomic
def create_document_grant(
    *,
    actor: Any,
    document: Document,
    data: dict[str, Any],
    request: Any = None,
) -> DocumentGrant:
    _ensure_manage_allowed(actor=actor, document=document)
    _validate_grant_payload(data)
    grant = DocumentGrant.objects.create(document=document, created_by=actor, **data)
    audit_log(
        user=actor,
        action="document.grant.create",
        resource=document,
        result="success",
        request=request,
        after_data=grant_snapshot(grant),
    )
    return grant


@transaction.atomic
def update_document_grant(
    *,
    actor: Any,
    grant: DocumentGrant,
    data: dict[str, Any],
    request: Any = None,
) -> DocumentGrant:
    _ensure_manage_allowed(actor=actor, document=grant.document)
    if grant.revoked_at is not None:
        raise ValidationError("授权已撤销，不能修改")
    merged = {
        "can_view": grant.can_view,
        "can_download": grant.can_download,
        "can_update": grant.can_update,
        "can_delete": grant.can_delete,
        "can_restore": grant.can_restore,
        "can_manage": grant.can_manage,
        "expires_at": grant.expires_at,
        **data,
    }
    _validate_grant_payload(merged)
    before_data = grant_snapshot(grant)
    for field, value in data.items():
        setattr(grant, field, value)
    grant.save()
    audit_log(
        user=actor,
        action="document.grant.update",
        resource=grant.document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=grant_snapshot(grant),
    )
    return grant


@transaction.atomic
def revoke_document_grant(
    *,
    actor: Any,
    grant: DocumentGrant,
    request: Any = None,
) -> DocumentGrant:
    _ensure_manage_allowed(actor=actor, document=grant.document)
    if grant.revoked_at is not None:
        raise ValidationError("授权已撤销")
    before_data = grant_snapshot(grant)
    grant.revoked_at = timezone.now()
    grant.revoked_by = actor
    grant.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    audit_log(
        user=actor,
        action="document.grant.revoke",
        resource=grant.document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=grant_snapshot(grant),
    )
    return grant


def _ensure_manage_allowed(*, actor: Any, document: Document) -> None:
    if not can_manage_document_grants(actor, document):
        raise PermissionDenied("无权管理该文档授权")


def _validate_grant_payload(data: dict[str, Any]) -> None:
    action_fields = [
        "can_view",
        "can_download",
        "can_update",
        "can_delete",
        "can_restore",
        "can_manage",
    ]
    if not any(data.get(field) for field in action_fields):
        raise ValidationError("至少需要授予一个权限动作")
    expires_at = data.get("expires_at")
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError("过期时间必须晚于当前时间")


def grant_snapshot(grant: DocumentGrant) -> dict[str, Any]:
    return {
        "id": grant.pk,
        "document_id": grant.document_id,
        "user_id": grant.user_id,
        "can_view": grant.can_view,
        "can_download": grant.can_download,
        "can_update": grant.can_update,
        "can_delete": grant.can_delete,
        "can_restore": grant.can_restore,
        "can_manage": grant.can_manage,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "revoked_by_id": grant.revoked_by_id,
    }
