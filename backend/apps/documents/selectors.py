from typing import Any

from django.db.models import Q, QuerySet

from apps.projects.models import ProjectMember
from apps.projects.selectors import visible_projects_for_user

from .models import Document


def base_documents_for_user(user: Any) -> QuerySet[Document]:
    queryset = Document.objects.select_related(
        "project",
        "folder",
        "current_version",
        "created_by",
    )
    if getattr(user, "is_system_admin", False):
        return queryset
    visible_project_ids = visible_projects_for_user(user).values("id")
    granted_document_ids = _active_granted_document_ids(
        user,
        "view",
        "download",
        "update",
        "delete",
        "restore",
        "manage",
    )
    return queryset.filter(
        Q(project__isnull=True)
        | Q(project_id__in=visible_project_ids)
        | Q(id__in=granted_document_ids)
    )


def visible_documents_for_user(user: Any) -> QuerySet[Document]:
    queryset = base_documents_for_user(user)
    if getattr(user, "is_system_admin", False):
        return queryset
    restricted_project_ids = ProjectMember.objects.filter(
        user=user,
        can_download_restricted=True,
    ).values("project_id")
    granted_view_document_ids = _active_granted_document_ids(user, "view")
    return queryset.filter(
        Q(access_level=Document.AccessLevel.INTERNAL)
        | Q(access_level=Document.AccessLevel.RESTRICTED, project_id__in=restricted_project_ids)
        | Q(id__in=granted_view_document_ids)
    )


def _active_granted_document_ids(user: Any, *actions: str) -> QuerySet:
    from apps.access.selectors import active_granted_document_ids

    return active_granted_document_ids(user, *actions)
