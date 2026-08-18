from typing import Any, TypedDict

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.projects.selectors import visible_projects_for_user

from .defaults import LEGACY_PROJECT_FOLDER_NAMES
from .models import Folder
from .personnel import (
    own_public_staff_folder_ids,
    public_staff_folder_ids,
    public_staff_root_ids,
)


class FolderTreeNode(TypedDict):
    id: int
    project: int | None
    parent: int | None
    name: str
    code: str
    sort_order: int
    is_active: bool
    is_system_root: bool
    children: list["FolderTreeNode"]


def visible_folders_for_user(user: Any) -> QuerySet[Folder]:
    queryset = Folder.objects.select_related("project", "parent", "created_by")
    if getattr(user, "is_temporary_user", False):
        return queryset.none()
    if getattr(user, "is_system_admin", False):
        return queryset
    if getattr(user, "role", None) != User.Role.DATA_OPERATOR:
        visible_project_ids = visible_projects_for_user(user).values("id")
        queryset = queryset.filter(Q(project__isnull=True) | Q(project_id__in=visible_project_ids))
    staff_folder_ids = public_staff_folder_ids()
    allowed_staff_folder_ids = public_staff_root_ids() | own_public_staff_folder_ids(user)
    return queryset.exclude(id__in=staff_folder_ids - allowed_staff_folder_ids)


def active_visible_folders_for_user(user: Any) -> QuerySet[Folder]:
    return (
        visible_folders_for_user(user)
        .filter(is_active=True)
        .exclude(
            project__isnull=True,
            parent__isnull=True,
            is_system_root=False,
        )
    )


def folder_tree_for_user(user: Any, project_id: str | None = None) -> list[FolderTreeNode]:
    queryset = active_visible_folders_for_user(user)
    if project_id in {"public", "null", "none"}:
        queryset = queryset.filter(project__isnull=True)
    elif project_id:
        queryset = queryset.filter(project_id=project_id).exclude(
            name__in=LEGACY_PROJECT_FOLDER_NAMES,
        )
    folders = list(queryset.order_by("sort_order", "id"))
    return build_tree(folders)


def build_tree(folders: list[Folder]) -> list[FolderTreeNode]:
    nodes: dict[int, FolderTreeNode] = {
        folder.id: {
            "id": folder.id,
            "project": folder.project_id,
            "parent": folder.parent_id,
            "name": folder.name,
            "code": folder.code,
            "sort_order": folder.sort_order,
            "is_active": folder.is_active,
            "is_system_root": folder.is_system_root,
            "children": [],
        }
        for folder in folders
    }
    roots: list[FolderTreeNode] = []
    for folder in folders:
        node = nodes[folder.id]
        if folder.parent_id and folder.parent_id in nodes:
            nodes[folder.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots
