from typing import Any

from django.db.models import Q, QuerySet

from apps.folders.defaults import standard_root_for_code
from apps.folders.models import Folder
from apps.projects.selectors import visible_projects_for_user

from .models import Document


def base_documents_for_user(user: Any, *, include_deleted: bool = False) -> QuerySet[Document]:
    queryset = Document.objects.select_related(
        "project",
        "folder",
        "current_version",
        "created_by",
        "deleted_by",
    )
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True)
    if getattr(user, "is_temporary_user", False):
        return queryset.none()
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
    visible_project_ids = visible_projects_for_user(user).values("id")
    granted_view_document_ids = _active_granted_document_ids(user, "view")
    queryset = queryset.filter(
        Q(project__isnull=True)
        | Q(project_id__in=visible_project_ids)
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
    staff_folder_ids = _public_staff_folder_ids()
    if not staff_folder_ids:
        return queryset

    own_staff_folder_ids = _own_public_staff_folder_ids(user)
    return queryset.exclude(
        Q(folder_id__in=staff_folder_ids) & ~Q(folder_id__in=own_staff_folder_ids)
    )


def _public_staff_folder_ids() -> list[int]:
    staff_root = standard_root_for_code("PUBLIC-STAFF")
    if staff_root is None:
        return []

    root_ids = list(
        Folder.objects.filter(
            Q(code=staff_root.code) | Q(name__in=staff_root.names),
            project__isnull=True,
            parent__isnull=True,
        ).values_list("id", flat=True)
    )
    return _folder_and_descendant_ids(root_ids)


def _own_public_staff_folder_ids(user: Any) -> list[int]:
    staff_root = standard_root_for_code("PUBLIC-STAFF")
    real_name = (getattr(user, "real_name", "") or "").strip()
    if staff_root is None or not real_name:
        return []

    root_ids = Folder.objects.filter(
        Q(code=staff_root.code) | Q(name__in=staff_root.names),
        project__isnull=True,
        parent__isnull=True,
    ).values_list("id", flat=True)
    own_root_ids = list(
        Folder.objects.filter(
            project__isnull=True,
            parent_id__in=root_ids,
            name=real_name,
        ).values_list("id", flat=True)
    )
    return _folder_and_descendant_ids(own_root_ids)


def _folder_and_descendant_ids(root_ids: list[int]) -> list[int]:
    folder_ids = list(dict.fromkeys(root_ids))
    frontier = folder_ids.copy()
    while frontier:
        child_ids = list(
            Folder.objects.filter(parent_id__in=frontier).values_list("id", flat=True)
        )
        frontier = [child_id for child_id in child_ids if child_id not in folder_ids]
        folder_ids.extend(frontier)
    return folder_ids
