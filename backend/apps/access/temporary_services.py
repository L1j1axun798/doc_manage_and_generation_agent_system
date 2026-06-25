from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.files.base import File
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.documents.models import Document, DocumentVersion
from apps.documents.services import StoredFileMissing, version_snapshot
from common.storage import LocalDocumentStorage

from .models import TemporaryAccessGrant
from .permissions import can_manage_document_grants
from .temporary_tokens import generate_temporary_access_token, hash_temporary_access_token


@dataclass(frozen=True)
class TemporaryAccessGrantResult:
    grant: TemporaryAccessGrant
    token: str


class TemporaryAccessInvalid(APIException):
    status_code = 403
    default_detail = "临时访问无效或已失效"
    default_code = "temporary_access_invalid"


def create_temporary_access_grant(
    *,
    actor: Any,
    document_version: DocumentVersion,
    expires_at: Any = None,
    max_downloads: int = 1,
    request: Any = None,
) -> TemporaryAccessGrantResult:
    document = document_version.document
    _ensure_manage_allowed(actor=actor, document=document)
    if max_downloads < 1:
        raise ValidationError("最大下载次数至少为 1")
    expires_at = expires_at or _default_expires_at()
    if expires_at <= timezone.now():
        raise ValidationError("过期时间必须晚于当前时间")
    token = generate_temporary_access_token()
    grant = TemporaryAccessGrant.objects.create(
        document_version=document_version,
        token_hash=hash_temporary_access_token(token),
        max_downloads=max_downloads,
        expires_at=expires_at,
        created_by=actor,
    )
    audit_log(
        user=actor,
        action="temporary_access.create",
        resource=document,
        result="success",
        request=request,
        after_data=temporary_access_snapshot(grant),
    )
    return TemporaryAccessGrantResult(grant=grant, token=token)


@transaction.atomic
def revoke_temporary_access_grant(
    *,
    actor: Any,
    grant: TemporaryAccessGrant,
    request: Any = None,
) -> TemporaryAccessGrant:
    locked_grant = (
        TemporaryAccessGrant.objects.select_for_update()
        .select_related("document_version__document")
        .get(pk=grant.pk)
    )
    _ensure_manage_allowed(actor=actor, document=locked_grant.document_version.document)
    if locked_grant.revoked_at is not None:
        raise ValidationError("临时访问已撤销")
    before_data = temporary_access_snapshot(locked_grant)
    locked_grant.revoked_at = timezone.now()
    locked_grant.revoked_by = actor
    locked_grant.save(update_fields=["revoked_at", "revoked_by"])
    audit_log(
        user=actor,
        action="temporary_access.revoke",
        resource=locked_grant.document_version.document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=temporary_access_snapshot(locked_grant),
    )
    return locked_grant


def consume_temporary_access_token(
    *,
    token: str,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> tuple[File, DocumentVersion]:
    token_hash = hash_temporary_access_token(token)
    denied_document: Document | None = None
    denied_snapshot: dict[str, Any] | None = None
    try:
        with transaction.atomic():
            grant = (
                TemporaryAccessGrant.objects.select_for_update()
                .select_related("document_version__document")
                .get(token_hash=token_hash)
            )
            if not grant.is_active:
                denied_document = grant.document_version.document
                denied_snapshot = temporary_access_snapshot(grant)
                version = grant.document_version
            else:
                grant.used_count += 1
                grant.last_used_at = timezone.now()
                grant.save(update_fields=["used_count", "last_used_at"])
                version = grant.document_version
                audit_log(
                    user=getattr(request, "user", None),
                    action="temporary_access.download",
                    resource=version.document,
                    result="success",
                    request=request,
                    after_data=temporary_access_snapshot(grant),
                )
    except TemporaryAccessGrant.DoesNotExist as exc:
        audit_log(
            user=getattr(request, "user", None),
            action="temporary_access.download",
            result="denied",
            request=request,
            resource_type="TemporaryAccessGrant",
            resource_id="invalid",
            error_message="临时访问不存在",
        )
        raise TemporaryAccessInvalid() from exc

    if denied_document is not None:
        audit_log(
            user=getattr(request, "user", None),
            action="temporary_access.download",
            resource=denied_document,
            result="denied",
            request=request,
            after_data=denied_snapshot,
            error_message="临时访问已失效",
        )
        raise TemporaryAccessInvalid()

    backend = storage or LocalDocumentStorage()
    path = backend.resolve(version.storage_path)
    if not path.is_file():
        audit_log(
            user=getattr(request, "user", None),
            action="temporary_access.download",
            resource=version.document,
            result="failed",
            request=request,
            after_data=version_snapshot(version),
            error_message="物理文件不存在",
        )
        raise StoredFileMissing()
    return File(path.open("rb")), version


def _ensure_manage_allowed(*, actor: Any, document: Document) -> None:
    if not can_manage_document_grants(actor, document):
        raise PermissionDenied("无权管理该文档临时访问")


def _default_expires_at() -> Any:
    return timezone.now() + timedelta(hours=settings.TEMPORARY_GRANT_DEFAULT_HOURS)


def temporary_access_snapshot(grant: TemporaryAccessGrant) -> dict[str, Any]:
    return {
        "id": grant.pk,
        "document_version_id": grant.document_version_id,
        "max_downloads": grant.max_downloads,
        "used_count": grant.used_count,
        "remaining_downloads": grant.remaining_downloads,
        "expires_at": grant.expires_at.isoformat(),
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "revoked_by_id": grant.revoked_by_id,
        "last_used_at": grant.last_used_at.isoformat() if grant.last_used_at else None,
    }
