from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import audit_log

from .models import Project, ProjectMember


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
    project.status = Project.Status.ARCHIVED
    project.archived_at = timezone.now()
    project.archived_by = actor
    project.save(update_fields=["status", "archived_at", "archived_by", "updated_at"])
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
        "can_upload": True,
        "can_download_restricted": True,
        "can_manage_folder": True,
        "can_delete": True,
        "can_restore": True,
        "can_manage_permission": True,
    }


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
        "can_upload": member.can_upload,
        "can_download_restricted": member.can_download_restricted,
        "can_manage_folder": member.can_manage_folder,
        "can_delete": member.can_delete,
        "can_restore": member.can_restore,
        "can_manage_permission": member.can_manage_permission,
    }
