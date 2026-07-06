from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import audit_log
from apps.documents.models import Document
from apps.folders.defaults import ARCHIVE_ROOT, STANDARD_PUBLIC_ROOTS
from apps.folders.models import Folder
from common.storage import LocalDocumentStorage

from .models import Project, ProjectMember

PROJECT_ARCHIVE_FOLDER_CODE_PREFIX = "PROJECT-ARCHIVE"


@transaction.atomic
def create_project(*, actor: Any, data: dict[str, Any], request: Any = None) -> Project:
    manager = data.get("manager")
    project = Project.objects.create(created_by=actor, **data)
    if manager is not None:
        ProjectMember.objects.update_or_create(
            project=project,
            user=manager,
            defaults=manager_member_defaults(),
        )
    ensure_project_standard_folders(actor=actor, project=project)
    audit_log(
        user=actor,
        action="project.create",
        resource=project,
        result="success",
        request=request,
        after_data=project_snapshot(project),
    )
    return project


@transaction.atomic
def update_project(
    *,
    actor: Any,
    project: Project,
    data: dict[str, Any],
    request: Any = None,
) -> Project:
    if project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档，不能修改")
    before_data = project_snapshot(project)
    for field, value in data.items():
        setattr(project, field, value)
    project.save()
    if "manager" in data and data["manager"] is not None:
        ProjectMember.objects.update_or_create(
            project=project,
            user=data["manager"],
            defaults=manager_member_defaults(),
        )
    audit_log(
        user=actor,
        action="project.update",
        resource=project,
        result="success",
        request=request,
        before_data=before_data,
        after_data=project_snapshot(project),
    )
    return project


@transaction.atomic
def archive_project(*, actor: Any, project: Project, request: Any = None) -> Project:
    if project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档")
    before_data = project_snapshot(project)
    archived_at = timezone.now()
    project.status = Project.Status.ARCHIVED
    project.archived_at = archived_at
    project.archived_by = actor
    project.save(update_fields=["status", "archived_at", "archived_by", "updated_at"])
    archive_project_folders(actor=actor, project=project, archived_at=archived_at)
    audit_log(
        user=actor,
        action="project.archive",
        resource=project,
        result="success",
        request=request,
        before_data=before_data,
        after_data=project_snapshot(project),
    )
    return project


@transaction.atomic
def unarchive_project(*, actor: Any, project: Project, request: Any = None) -> Project:
    if project.status == Project.Status.ACTIVE:
        raise ValidationError("项目未归档")
    before_data = project_snapshot(project)
    restore_archived_project_folders(project=project)
    project.status = Project.Status.ACTIVE
    project.archived_at = None
    project.archived_by = None
    project.save(update_fields=["status", "archived_at", "archived_by", "updated_at"])
    audit_log(
        user=actor,
        action="project.unarchive",
        resource=project,
        result="success",
        request=request,
        before_data=before_data,
        after_data=project_snapshot(project),
    )
    return project


@transaction.atomic
def delete_project(*, actor: Any, project: Project, request: Any = None) -> None:
    before_data = project_snapshot(project)
    project_id = project.pk
    if project_has_active_documents(project=project):
        message = "项目中仍有资料，不能删除。请先归档项目，或清空项目资料后再删除项目。"
        raise ValidationError(message)
    if project_has_foreign_folder_documents(project=project):
        message = "项目目录中存在归属异常的资料，不能删除。请先清理项目资料后再删除项目。"
        raise ValidationError(message)
    storage_paths = permanently_delete_removed_project_documents(project=project)
    delete_project_folders(project=project)
    project.delete()
    audit_log(
        user=actor,
        action="project.delete",
        result="success",
        request=request,
        resource_type="Project",
        resource_id=str(project_id),
        before_data=before_data,
    )
    transaction.on_commit(lambda: delete_stored_files(storage_paths))


def project_has_active_documents(*, project: Project) -> bool:
    if project.documents.filter(deleted_at__isnull=True).exists():
        return True
    return Document.objects.filter(folder__project=project, deleted_at__isnull=True).exists()


def project_has_foreign_folder_documents(*, project: Project) -> bool:
    return Document.objects.filter(folder__project=project).exclude(project=project).exists()


def permanently_delete_removed_project_documents(*, project: Project) -> list[str]:
    storage_paths: list[str] = []
    documents = project.documents.filter(deleted_at__isnull=False).prefetch_related("versions")
    for document in documents:
        storage_paths.extend(document.versions.values_list("storage_path", flat=True))
        document.current_version = None
        document.save(update_fields=["current_version", "updated_at"])
        document.delete()
    return storage_paths


def delete_stored_files(storage_paths: list[str]) -> None:
    backend = LocalDocumentStorage()
    for storage_path in storage_paths:
        backend.delete(storage_path)


def delete_project_folders(*, project: Project) -> None:
    folders = list(project.folders.only("id", "parent_id"))
    depths: dict[int, int] = {}
    parent_by_id = {folder.id: folder.parent_id for folder in folders}

    def folder_depth(folder_id: int) -> int:
        if folder_id in depths:
            return depths[folder_id]
        parent_id = parent_by_id.get(folder_id)
        if parent_id is None or parent_id not in parent_by_id:
            depths[folder_id] = 0
            return 0
        depths[folder_id] = folder_depth(parent_id) + 1
        return depths[folder_id]

    for folder in sorted(folders, key=lambda item: folder_depth(item.id), reverse=True):
        Folder.objects.filter(pk=folder.id).delete()


@transaction.atomic
def create_project_member(
    *,
    actor: Any,
    project: Project,
    data: dict[str, Any],
    request: Any = None,
) -> ProjectMember:
    member = ProjectMember.objects.create(project=project, **data)
    audit_log(
        user=actor,
        action="project.member.create",
        resource=project,
        result="success",
        request=request,
        after_data=member_snapshot(member),
    )
    return member


@transaction.atomic
def update_project_member(
    *,
    actor: Any,
    member: ProjectMember,
    data: dict[str, Any],
    request: Any = None,
) -> ProjectMember:
    before_data = member_snapshot(member)
    for field, value in data.items():
        setattr(member, field, value)
    member.save()
    audit_log(
        user=actor,
        action="project.member.update",
        resource=member.project,
        result="success",
        request=request,
        before_data=before_data,
        after_data=member_snapshot(member),
    )
    return member


@transaction.atomic
def delete_project_member(*, actor: Any, member: ProjectMember, request: Any = None) -> None:
    project = member.project
    before_data = member_snapshot(member)
    member.delete()
    audit_log(
        user=actor,
        action="project.member.delete",
        resource=project,
        result="success",
        request=request,
        before_data=before_data,
    )


def manager_member_defaults() -> dict[str, Any]:
    return {
        "role": ProjectMember.Role.MANAGER,
        "can_download_restricted": True,
        "can_manage_folder": True,
        "can_delete": True,
        "can_restore": True,
        "can_manage_permission": True,
    }


def ensure_project_standard_folders(*, actor: Any, project: Project) -> None:
    if project.status != Project.Status.ACTIVE:
        return

    for definition in STANDARD_PUBLIC_ROOTS:
        Folder.objects.update_or_create(
            project=project,
            parent=None,
            code=definition.code,
            defaults={
                "name": definition.name,
                "sort_order": definition.sort_order,
                "is_active": True,
                "created_by": actor,
            },
        )


def archive_project_folders(*, actor: Any, project: Project, archived_at: Any) -> None:
    archive_year_folder = get_or_create_archive_year_folder(actor=actor, year=archived_at.year)
    project_container = get_or_create_project_archive_folder(
        actor=actor,
        archive_year_folder=archive_year_folder,
        project=project,
    )
    top_level_folders = Folder.objects.filter(project=project, parent__isnull=True)
    top_level_folders.update(parent=project_container)


def restore_archived_project_folders(*, project: Project) -> None:
    container_code = project_archive_folder_code(project)
    project_container = Folder.objects.filter(
        project=project,
        code=container_code,
        parent__project__isnull=True,
    ).first()
    if project_container is None:
        return

    Folder.objects.filter(project=project, parent=project_container).update(parent=None)
    if not project_container.children.exists() and not project_container.documents.exists():
        project_container.delete()


def get_or_create_archive_year_folder(*, actor: Any, year: int) -> Folder:
    archive_root = get_or_create_archive_root_folder(actor=actor)
    name = f"{year}年归档资料"
    folder, _ = Folder.objects.get_or_create(
        project=None,
        parent=archive_root,
        name=name,
        defaults={
            "code": archive_year_folder_code(year),
            "sort_order": year,
            "is_system_root": False,
            "created_by": actor,
        },
    )
    changed_fields = []
    if folder.parent_id != archive_root.pk:
        folder.parent = archive_root
        changed_fields.append("parent")
    if folder.is_system_root:
        folder.is_system_root = False
        changed_fields.append("is_system_root")
    if not folder.is_active:
        folder.is_active = True
        changed_fields.append("is_active")
    if folder.code != archive_year_folder_code(year):
        folder.code = archive_year_folder_code(year)
        changed_fields.append("code")
    if changed_fields:
        folder.save(update_fields=[*changed_fields, "updated_at"])
    return folder


def get_or_create_archive_root_folder(*, actor: Any) -> Folder:
    folder = (
        Folder.objects.filter(project=None, parent=None)
        .filter(Q(code=ARCHIVE_ROOT.code) | Q(name__in=ARCHIVE_ROOT.names))
        .order_by("id")
        .first()
    )
    if folder is None:
        folder = Folder.objects.create(
            project=None,
            parent=None,
            name=ARCHIVE_ROOT.name,
            code=ARCHIVE_ROOT.code,
            sort_order=ARCHIVE_ROOT.sort_order,
            is_system_root=True,
            created_by=actor,
        )

    changed_fields = []
    if folder.name != ARCHIVE_ROOT.name:
        folder.name = ARCHIVE_ROOT.name
        changed_fields.append("name")
    if folder.code != ARCHIVE_ROOT.code:
        folder.code = ARCHIVE_ROOT.code
        changed_fields.append("code")
    if folder.sort_order != ARCHIVE_ROOT.sort_order:
        folder.sort_order = ARCHIVE_ROOT.sort_order
        changed_fields.append("sort_order")
    if not folder.is_system_root:
        folder.is_system_root = True
        changed_fields.append("is_system_root")
    if not folder.is_active:
        folder.is_active = True
        changed_fields.append("is_active")
    if changed_fields:
        folder.save(update_fields=[*changed_fields, "updated_at"])
    return folder


def get_or_create_project_archive_folder(
    *,
    actor: Any,
    archive_year_folder: Folder,
    project: Project,
) -> Folder:
    code = project_archive_folder_code(project)
    name = f"{project.code} {project.name}"
    folder, created = Folder.objects.get_or_create(
        project=project,
        code=code,
        defaults={
            "parent": archive_year_folder,
            "name": name,
            "sort_order": project.pk,
            "created_by": actor,
        },
    )
    if created:
        return folder

    changed_fields = []
    if folder.parent_id != archive_year_folder.pk:
        folder.parent = archive_year_folder
        changed_fields.append("parent")
    if folder.name != name:
        folder.name = name
        changed_fields.append("name")
    if not folder.is_active:
        folder.is_active = True
        changed_fields.append("is_active")
    if changed_fields:
        folder.save(update_fields=[*changed_fields, "updated_at"])
    return folder


def archive_year_folder_code(year: int) -> str:
    return f"{ARCHIVE_ROOT.code}-{year}"


def project_archive_folder_code(project: Project) -> str:
    return f"{PROJECT_ARCHIVE_FOLDER_CODE_PREFIX}-{project.pk}"


def project_snapshot(project: Project) -> dict[str, Any]:
    return {
        "id": project.pk,
        "name": project.name,
        "code": project.code,
        "manager_id": project.manager_id,
        "status": project.status,
        "archived_at": project.archived_at.isoformat() if project.archived_at else None,
        "archived_by_id": project.archived_by_id,
    }


def member_snapshot(member: ProjectMember) -> dict[str, Any]:
    return {
        "id": member.pk,
        "project_id": member.project_id,
        "user_id": member.user_id,
        "role": member.role,
        "can_download_restricted": member.can_download_restricted,
        "can_manage_folder": member.can_manage_folder,
        "can_delete": member.can_delete,
        "can_restore": member.can_restore,
        "can_manage_permission": member.can_manage_permission,
    }
