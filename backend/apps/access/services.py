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
    locked_document = Document.objects.select_for_update().get(pk=document.pk)
    _ensure_manage_allowed(actor=actor, document=locked_document)
    _validate_grant_payload(data)
    user = data["user"]
    active_grant = (
        DocumentGrant.objects.select_for_update()
        .filter(
            document=locked_document,
            user=user,
            revoked_at__isnull=True,
        )
        .first()
    )
    if active_grant is not None:
        if not active_grant.is_expired:
            raise ValidationError("该用户已有未撤销授权")
        active_grant.revoked_at = timezone.now()
        active_grant.revoked_by = actor
        active_grant.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    grant = DocumentGrant.objects.create(
        document=locked_document,
        created_by=actor,
        **data,
    )
    audit_log(
        user=actor,
        action="document.grant.create",
        resource=locked_document,
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
    if "document" in data or "user" in data:
        raise ValidationError("授权文档和授权用户不能修改")
    locked_document = Document.objects.select_for_update().get(pk=grant.document_id)
    locked_grant = DocumentGrant.objects.select_for_update().get(pk=grant.pk)
    _ensure_manage_allowed(actor=actor, document=locked_document)
    if locked_grant.revoked_at is not None:
        raise ValidationError("授权已撤销，不能修改")
    merged = {
        "can_view": locked_grant.can_view,
        "can_download": locked_grant.can_download,
        "can_update": locked_grant.can_update,
        "can_delete": locked_grant.can_delete,
        "can_restore": locked_grant.can_restore,
        "can_manage": locked_grant.can_manage,
        "expires_at": locked_grant.expires_at,
        **data,
    }
    _validate_grant_payload(merged)
    before_data = grant_snapshot(locked_grant)
    for field, value in data.items():
        setattr(locked_grant, field, value)
    locked_grant.save()
    audit_log(
        user=actor,
        action="document.grant.update",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=grant_snapshot(locked_grant),
    )
    return locked_grant


@transaction.atomic
def revoke_document_grant(
    *,
    actor: Any,
    grant: DocumentGrant,
    request: Any = None,
) -> DocumentGrant:
    locked_document = Document.objects.select_for_update().get(pk=grant.document_id)
    locked_grant = DocumentGrant.objects.select_for_update().get(pk=grant.pk)
    _ensure_manage_allowed(actor=actor, document=locked_document)
    if locked_grant.revoked_at is not None:
        raise ValidationError("授权已撤销")
    before_data = grant_snapshot(locked_grant)
    locked_grant.revoked_at = timezone.now()
    locked_grant.revoked_by = actor
    locked_grant.save(update_fields=["revoked_at", "revoked_by", "updated_at"])
    audit_log(
        user=actor,
        action="document.grant.revoke",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=grant_snapshot(locked_grant),
    )
    return locked_grant


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
