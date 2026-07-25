from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from apps.projects.models import ProjectMember
from apps.projects.selectors import get_project_membership


def can_use_generation(user: Any, project: Any) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", True) or getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    membership = get_project_membership(user, project)
    return bool(
        membership
        and (
            membership.role in {ProjectMember.Role.MANAGER, ProjectMember.Role.OPERATOR}
            or membership.can_upload
        )
    )


def can_review_generation(user: Any, project: Any) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", True) or getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    membership = get_project_membership(user, project)
    return bool(membership and membership.role == ProjectMember.Role.MANAGER)


class IsDocumentGenerationUser(BasePermission):
    message = "无权使用入场资料编制功能"

    def has_permission(self, request: Any, view: Any) -> bool:
        return bool(
            getattr(request.user, "is_authenticated", False)
            and getattr(request.user, "is_active", True)
            and not getattr(request.user, "is_temporary_user", False)
        )
