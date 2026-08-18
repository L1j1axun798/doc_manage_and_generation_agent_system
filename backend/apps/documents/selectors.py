from typing import Any

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from apps.access.models import DocumentGrant
from apps.accounts.models import User
from apps.folders.personnel import own_public_staff_folder_ids, public_staff_folder_ids
from apps.projects.models import ProjectMember
from apps.projects.selectors import visible_projects_for_user

from .models import Document


def base_documents_for_user(user: Any, *, include_deleted: bool = False) -> QuerySet[Document]:
    queryset = Document.objects.select_related(
        "project",
        "folder",
        "current_version",
        "created_by",
        "deleted_by",
    ).prefetch_related(
        Prefetch(
            "grants",
            queryset=DocumentGrant.objects.filter(
                user=user,
                revoked_at__isnull=True,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())),
            to_attr="_active_request_user_grants",
        ),
        Prefetch(
            "project__members",
            queryset=ProjectMember.objects.filter(user=user),
            to_attr="_request_user_memberships",
        ),
    )
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True)
    if getattr(user, "is_temporary_user", False):
        return queryset.none()
    if getattr(user, "is_system_admin", False):
        return queryset
    if getattr(user, "role", None) == User.Role.DATA_OPERATOR:
        return queryset
    visible_project_ids = visible_projects_for_user(user).values("id")
    granted_document_ids = _active_granted_document_ids(
        user,
        "view",
        "download",
        "update",
        "delete",
        "restore",
    )
    return queryset.filter(
        Q(project__isnull=True)
        | Q(project_id__in=visible_project_ids)
        | Q(id__in=granted_document_ids)
    )


def visible_documents_for_user(user: Any, *, include_deleted: bool = False) -> QuerySet[Document]:
    queryset = base_documents_for_user(user, include_deleted=include_deleted)
    if getattr(user, "is_system_admin", False):
        return queryset
    if getattr(user, "role", None) == User.Role.DATA_OPERATOR:
        return _filter_public_staff_documents_for_user(queryset, user)
    visible_project_ids = visible_projects_for_user(user).values("id")
    granted_view_document_ids = _active_granted_document_ids(user, "view")
    restricted_project_ids = ProjectMember.objects.filter(
        user=user,
        can_download_restricted=True,
    ).values("project_id")
    queryset = queryset.filter(
        Q(access_level=Document.AccessLevel.INTERNAL, project__isnull=True)
        | Q(access_level=Document.AccessLevel.INTERNAL, project_id__in=visible_project_ids)
        | Q(
            access_level=Document.AccessLevel.RESTRICTED,
            project_id__in=restricted_project_ids,
        )
        | Q(id__in=granted_view_document_ids)
    )
    return _filter_public_staff_documents_for_user(queryset, user)


def trashed_documents_for_user(user: Any) -> QuerySet[Document]:
    return visible_documents_for_user(user, include_deleted=True).filter(deleted_at__isnull=False)


def _active_granted_document_ids(user: Any, *actions: str) -> QuerySet:
    from apps.access.selectors import active_granted_document_ids

    return active_granted_document_ids(user, *actions)


def _filter_public_staff_documents_for_user(
    queryset: QuerySet[Document],
    user: Any,
) -> QuerySet[Document]:
    staff_folder_ids = public_staff_folder_ids()
    if not staff_folder_ids:
        return queryset

    own_staff_folder_ids = own_public_staff_folder_ids(user)
    return queryset.exclude(
        Q(folder_id__in=staff_folder_ids) & ~Q(folder_id__in=own_staff_folder_ids)
    )
