from typing import Any

from apps.documents.models import Document
from apps.projects.selectors import get_project_membership


def can_manage_document_grants(user: Any, document: Document) -> bool:
    if getattr(user, "is_system_admin", False):
        return True
    if document.project is not None:
        membership = get_project_membership(user, document.project)
        if membership and membership.can_manage_permission:
            return True
    from .selectors import has_active_document_grant

    return has_active_document_grant(user, document, "manage")
