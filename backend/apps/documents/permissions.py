from typing import Any

from apps.projects.models import Project
from apps.projects.selectors import get_project_membership

from .models import Document


def can_upload_document(user: Any, project: Project | None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", True):
        return False
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    if project is None:
        return True
    return get_project_membership(user, project) is not None


def can_download_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    return _has_active_grant(user, document, "download")


def can_view_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    if _has_active_grant(user, document, "view"):
        return True
    return _has_basic_scope(user, document)


def can_update_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    if _has_active_grant(user, document, "update"):
        return True
    if document.project is None:
        return False
    membership = get_project_membership(user, document.project)
    return bool(membership and membership.can_upload)


def can_delete_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    if _has_active_grant(user, document, "delete"):
        return True
    if document.project is None:
        return False
    membership = get_project_membership(user, document.project)
    return bool(membership and membership.can_delete)


def can_restore_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    if getattr(user, "is_system_admin", False):
        return True
    if _has_active_grant(user, document, "restore"):
        return True
    if document.project is None:
        return False
    membership = get_project_membership(user, document.project)
    return bool(membership and membership.can_restore)


def can_permanently_delete_document(user: Any, document: Document) -> bool:
    if getattr(user, "is_temporary_user", False):
        return False
    return bool(getattr(user, "is_system_admin", False))


def _has_basic_scope(user: Any, document: Document) -> bool:
    if document.project is None:
        return True
    return get_project_membership(user, document.project) is not None


def _has_active_grant(user: Any, document: Document, action: str) -> bool:
    from apps.access.selectors import has_active_document_grant

    return has_active_document_grant(user, document, action)
