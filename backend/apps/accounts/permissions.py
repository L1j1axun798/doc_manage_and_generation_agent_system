from typing import Any

from rest_framework.permissions import BasePermission


class IsSystemAdmin(BasePermission):
    message = "仅系统管理员可执行该操作"

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_system_admin", False))
