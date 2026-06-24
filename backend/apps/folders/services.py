from typing import Any

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.projects.models import Project

from .models import Folder
from .permissions import can_manage_folder


@transaction.atomic
def create_folder(*, actor: Any, data: dict[str, Any], request: Any = None) -> Folder:
    project = _resolve_project_from_data(data)
    _ensure_folder_write_allowed(actor, project)
    _validate_parent(project=project, parent=data.get("parent"))
    _validate_public_root(project=project, parent=data.get("parent"))
    _validate_unique_sibling_name(project=project, parent=data.get("parent"), name=data["name"])
    folder = Folder.objects.create(created_by=actor, **data)
    audit_log(
        user=actor,
        action="folder.create",
        resource=folder,
        result="success",
        request=request,
        after_data=folder_snapshot(folder),
    )
    return folder


@transaction.atomic
def update_folder(
    *,
    actor: Any,
    folder: Folder,
    data: dict[str, Any],
    request: Any = None,
) -> Folder:
    if folder.is_system_root:
        raise ValidationError("系统根分类不能修改")
    _ensure_folder_write_allowed(actor, folder.project)
    before_data = folder_snapshot(folder)
    if "project" in data or "parent" in data:
        raise ValidationError("请使用移动接口调整文件夹位置")
    if "name" in data:
        _validate_unique_sibling_name(
            project=folder.project,
            parent=folder.parent,
            name=data["name"],
            exclude=folder,
        )
    for field, value in data.items():
        setattr(folder, field, value)
    folder.save()
    audit_log(
        user=actor,
        action="folder.update",
        resource=folder,
        result="success",
        request=request,
        before_data=before_data,
        after_data=folder_snapshot(folder),
    )
    return folder


@transaction.atomic
def move_folder(
    *,
    actor: Any,
    folder: Folder,
    parent: Folder | None,
    sort_order: int | None = None,
    request: Any = None,
) -> Folder:
    if folder.is_system_root:
        raise ValidationError("系统根分类不能移动")
    _ensure_folder_write_allowed(actor, folder.project)
    _validate_public_root(project=folder.project, parent=parent)
    _validate_parent(project=folder.project, parent=parent, folder=folder)
    _validate_unique_sibling_name(
        project=folder.project,
        parent=parent,
        name=folder.name,
        exclude=folder,
    )
    before_data = folder_snapshot(folder)
    folder.parent = parent
    if sort_order is not None:
        folder.sort_order = sort_order
    folder.save(update_fields=["parent", "sort_order", "updated_at"])
    audit_log(
        user=actor,
        action="folder.move",
        resource=folder,
        result="success",
        request=request,
        before_data=before_data,
        after_data=folder_snapshot(folder),
    )
    return folder


@transaction.atomic
def disable_folder(*, actor: Any, folder: Folder, request: Any = None) -> Folder:
    if folder.is_system_root:
        raise ValidationError("系统根分类不能停用")
    _ensure_folder_write_allowed(actor, folder.project)
    if folder.children.filter(is_active=True).exists():
        raise ValidationError("文件夹下存在启用的子文件夹，不能停用")
    before_data = folder_snapshot(folder)
    folder.is_active = False
    folder.save(update_fields=["is_active", "updated_at"])
    audit_log(
        user=actor,
        action="folder.disable",
        resource=folder,
        result="success",
        request=request,
        before_data=before_data,
        after_data=folder_snapshot(folder),
    )
    return folder


def _resolve_project_from_data(data: dict[str, Any]) -> Project | None:
    parent = data.get("parent")
    if parent is not None:
        if data.get("project") is not None and data["project"] != parent.project:
            raise ValidationError("父文件夹和项目不一致")
        data["project"] = parent.project
        return parent.project
    return data.get("project")


def _ensure_folder_write_allowed(actor: Any, project: Project | None) -> None:
    if project is not None and project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档，不能修改文件夹")
    if not can_manage_folder(actor, project):
        raise PermissionDenied("无权管理文件夹")


def _validate_parent(
    *,
    project: Project | None,
    parent: Folder | None,
    folder: Folder | None = None,
) -> None:
    if parent is None:
        return
    if not parent.is_active:
        raise ValidationError("父文件夹已停用")
    if parent.project_id != (project.id if project else None):
        raise ValidationError("父文件夹和项目不一致")
    if folder is not None:
        if parent.pk == folder.pk:
            raise ValidationError("文件夹不能移动到自身")
        if _is_descendant(candidate=parent, ancestor=folder):
            raise ValidationError("文件夹不能移动到自己的后代")


def _validate_public_root(*, project: Project | None, parent: Folder | None) -> None:
    if project is None and parent is None:
        raise ValidationError("公共文件夹必须选择一个系统根分类作为父文件夹")


def _is_descendant(*, candidate: Folder, ancestor: Folder) -> bool:
    current: Folder | None = candidate
    while current is not None and current.parent_id:
        if current.parent_id == ancestor.pk:
            return True
        current = current.parent
    return False


def _validate_unique_sibling_name(
    *,
    project: Project | None,
    parent: Folder | None,
    name: str,
    exclude: Folder | None = None,
) -> None:
    queryset = Folder.objects.filter(
        project=project,
        parent=parent,
        name=name,
        is_active=True,
    )
    if exclude is not None:
        queryset = queryset.exclude(pk=exclude.pk)
    if queryset.exists():
        raise ValidationError("同级文件夹名称已存在")


def folder_snapshot(folder: Folder) -> dict[str, Any]:
    return {
        "id": folder.pk,
        "project_id": folder.project_id,
        "parent_id": folder.parent_id,
        "name": folder.name,
        "code": folder.code,
        "sort_order": folder.sort_order,
        "is_active": folder.is_active,
        "is_system_root": folder.is_system_root,
    }
