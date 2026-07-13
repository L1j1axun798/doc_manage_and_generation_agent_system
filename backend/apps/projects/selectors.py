from typing import Any

from django.db.models import QuerySet

from .models import Project, ProjectMember


def visible_projects_for_user(user: Any) -> QuerySet[Project]:
    queryset = Project.objects.select_related("manager", "created_by", "archived_by")
    if getattr(user, "is_system_admin", False):
        return queryset
    return queryset.filter(members__user=user).distinct()


def project_members_for_project(project: Project) -> QuerySet[ProjectMember]:
    return ProjectMember.objects.filter(project=project).select_related("project", "user")


def get_project_membership(user: Any, project: Project) -> ProjectMember | None:
    if not getattr(user, "is_authenticated", False):
        return None
    prefetched = getattr(project, "_request_user_memberships", None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return ProjectMember.objects.filter(project=project, user=user).first()
