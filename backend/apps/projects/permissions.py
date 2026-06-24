from typing import Any

from rest_framework.permissions import BasePermission

from .models import ProjectMember
from .selectors import get_project_membership


def can_manage_project(user: Any, project: Any) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    membership = get_project_membership(user, project)
    return bool(membership and membership.role == ProjectMember.Role.MANAGER)


def can_manage_project_members(user: Any, project: Any) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    membership = get_project_membership(user, project)
    return bool(membership and membership.can_manage_permission)


class IsSystemAdminOrProjectManager(BasePermission):
    message = "仅系统管理员或项目负责人可执行该操作"

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        return can_manage_project(request.user, obj)
