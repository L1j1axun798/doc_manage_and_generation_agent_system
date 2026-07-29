from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.documents.models import DocumentVersion
from apps.documents.selectors import visible_documents_for_user
from apps.projects.models import Project
from apps.projects.selectors import visible_projects_for_user

from .models import (
    BUSINESS_TYPE,
    ApprovalStatus,
    DocumentTemplate,
    GenerationTask,
)
from .permissions import can_use_generation


def available_templates() -> QuerySet[DocumentTemplate]:
    return (
        DocumentTemplate.objects.filter(
            business_type=BUSINESS_TYPE,
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        )
        .select_related("document_version", "document_version__document")
        .order_by("client_name", "code", "-id")
    )


def visible_generation_tasks(user: Any) -> QuerySet[GenerationTask]:
    projects = visible_projects_for_user(user)
    if getattr(user, "is_temporary_user", False):
        return GenerationTask.objects.none()
    return (
        GenerationTask.objects.filter(project__in=projects, deleted_at__isnull=True)
        .select_related(
            "project",
            "template",
            "created_by",
            "reviewed_by",
            "output_document_version",
            "output_document_version__document",
        )
        .prefetch_related(
            "sources__document_version__document__folder",
            "sections",
            "reviews__actor",
        )
    )


def writable_project_for_user(user: Any, project_id: int) -> Project | None:
    project = visible_projects_for_user(user).filter(pk=project_id).first()
    if project is None or not can_use_generation(user, project):
        return None
    return project


def visible_source_version_for_user(
    user: Any,
    *,
    project_id: int,
    version_id: int,
) -> DocumentVersion | None:
    visible_documents = visible_documents_for_user(user).filter(project_id=project_id)
    return (
        DocumentVersion.objects.filter(pk=version_id, document__in=visible_documents)
        .select_related("document", "document__folder", "uploaded_by")
        .first()
    )
