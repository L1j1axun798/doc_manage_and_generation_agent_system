from typing import Any

from apps.projects.models import Project
from apps.projects.selectors import get_project_membership


def can_manage_folder(user: Any, project: Project | None) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    if project is None:
        return False
    membership = get_project_membership(user, project)
    return bool(membership and membership.can_manage_folder)
