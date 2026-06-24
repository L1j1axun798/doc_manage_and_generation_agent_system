from typing import Any

from apps.projects.models import Project
from apps.projects.selectors import get_project_membership

from .models import Document


def can_upload_document(user: Any, project: Project | None) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    if project is None:
        return False
    membership = get_project_membership(user, project)
    return bool(membership and membership.can_upload)


def can_download_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    if document.access_level == Document.AccessLevel.INTERNAL:
        return _has_basic_scope(user, document)
    if document.project is None:
        return False
    membership = get_project_membership(user, document.project)
    return bool(membership and membership.can_download_restricted)


def _has_basic_scope(user: Any, document: Document) -> bool:
    if document.project is None:
        return True
    return get_project_membership(user, document.project) is not None
