from typing import Any

from apps.documents.models import Document


def can_manage_document_grants(user: Any, document: Document) -> bool:
    return bool(getattr(user, "is_system_admin", False))
