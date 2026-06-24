from typing import Any

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.documents.models import Document
from apps.projects.models import ProjectMember

from .models import DocumentGrant

GRANT_ACTION_FIELDS = {
    "view": "can_view",
    "download": "can_download",
    "update": "can_update",
    "delete": "can_delete",
    "restore": "can_restore",
    "manage": "can_manage",
}


def active_grants_for_user(user: Any) -> QuerySet[DocumentGrant]:
    return DocumentGrant.objects.filter(
        user=user,
        revoked_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))


def has_active_document_grant(user: Any, document: Document, action: str) -> bool:
    field = GRANT_ACTION_FIELDS[action]
    return active_grants_for_user(user).filter(document=document, **{field: True}).exists()


def active_granted_document_ids(user: Any, *actions: str) -> QuerySet:
    query = Q()
    for action in actions:
        query |= Q(**{GRANT_ACTION_FIELDS[action]: True})
    return active_grants_for_user(user).filter(query).values("document_id")


def manageable_document_ids_for_user(user: Any) -> QuerySet[Document]:
    queryset = Document.objects.all()
    if getattr(user, "is_system_admin", False):
        return queryset
    project_ids = ProjectMember.objects.filter(
        user=user,
        can_manage_permission=True,
    ).values("project_id")
    grant_document_ids = active_granted_document_ids(user, "manage")
    return queryset.filter(Q(project_id__in=project_ids) | Q(id__in=grant_document_ids))


def grants_manageable_by_user(user: Any) -> QuerySet[DocumentGrant]:
    return DocumentGrant.objects.select_related(
        "document",
        "document__project",
        "user",
        "created_by",
        "revoked_by",
    ).filter(document_id__in=manageable_document_ids_for_user(user).values("id"))
