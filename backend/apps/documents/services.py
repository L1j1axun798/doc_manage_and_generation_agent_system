from pathlib import PurePath
from typing import Any

from django.core.files.base import File
from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.folders.models import Folder
from apps.projects.models import Project
from common.storage import LocalDocumentStorage, StoredFile
from common.validators import validate_uploaded_file

from .models import Document, DocumentVersion
from .permissions import can_download_document, can_upload_document


class StoredFileMissing(APIException):
    status_code = 500
    default_detail = "文件存储不一致，当前版本物理文件不存在"
    default_code = "stored_file_missing"


def create_document(
    *,
    actor: Any,
    folder: Folder,
    uploaded_file: Any,
    title: str = "",
    description: str = "",
    access_level: str = Document.AccessLevel.INTERNAL,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> Document:
    _ensure_upload_allowed(actor=actor, folder=folder)
    validate_uploaded_file(uploaded_file)
    document_title = title.strip() or PurePath(uploaded_file.name).name
    backend = storage or LocalDocumentStorage()
    stored_file = backend.save_uploaded_file(uploaded_file)
    try:
        with transaction.atomic():
            document = Document.objects.create(
                project=folder.project,
                folder=folder,
                title=document_title,
                description=description,
                access_level=access_level,
                created_by=actor,
            )
            version = _create_version(
                document=document,
                actor=actor,
                uploaded_file=uploaded_file,
                stored_file=stored_file,
                version_number=1,
            )
            document.current_version = version
            document.save(update_fields=["current_version", "updated_at"])
            audit_log(
                user=actor,
                action="document.create",
                resource=document,
                result="success",
                request=request,
                after_data=document_snapshot(document),
            )
            return document
    except Exception:
        backend.delete(stored_file.relative_path)
        raise


def create_document_version(
    *,
    actor: Any,
    document: Document,
    uploaded_file: Any,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> DocumentVersion:
    _ensure_upload_allowed(actor=actor, folder=document.folder)
    validate_uploaded_file(uploaded_file)
    backend = storage or LocalDocumentStorage()
    stored_file = backend.save_uploaded_file(uploaded_file)
    try:
        with transaction.atomic():
            locked_document = (
                Document.objects.select_for_update()
                .select_related("folder", "project")
                .get(pk=document.pk)
            )
            latest_version = (
                DocumentVersion.objects.filter(document=locked_document).aggregate(
                    latest=Max("version_number")
                )["latest"]
                or 0
            )
            version = _create_version(
                document=locked_document,
                actor=actor,
                uploaded_file=uploaded_file,
                stored_file=stored_file,
                version_number=latest_version + 1,
            )
            locked_document.current_version = version
            locked_document.save(update_fields=["current_version", "updated_at"])
            audit_log(
                user=actor,
                action="document.version.create",
                resource=locked_document,
                result="success",
                request=request,
                after_data=version_snapshot(version),
            )
            return version
    except Exception:
        backend.delete(stored_file.relative_path)
        raise


def document_storage_consistency(
    *,
    document: Document,
    storage: LocalDocumentStorage | None = None,
) -> dict[str, list[str]]:
    backend = storage or LocalDocumentStorage()
    missing = [
        version.storage_path
        for version in document.versions.all()
        if not backend.exists(version.storage_path)
    ]
    return {"missing_files": missing}


def open_current_version_for_download(
    *,
    actor: Any,
    document: Document,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> tuple[File, DocumentVersion]:
    if not can_download_document(actor, document):
        audit_log(
            user=actor,
            action="document.download",
            resource=document,
            result="denied",
            request=request,
            error_message="无权下载该文件",
        )
        raise PermissionDenied("无权下载该文件")
    version = document.current_version
    if version is None:
        raise ValidationError("文档没有可下载的当前版本")
    backend = storage or LocalDocumentStorage()
    path = backend.resolve(version.storage_path)
    if not path.is_file():
        audit_log(
            user=actor,
            action="document.download",
            resource=document,
            result="failed",
            request=request,
            after_data=version_snapshot(version),
            error_message="物理文件不存在",
        )
        raise StoredFileMissing()
    audit_log(
        user=actor,
        action="document.download",
        resource=document,
        result="success",
        request=request,
        after_data=version_snapshot(version),
    )
    return File(path.open("rb")), version


def _ensure_upload_allowed(*, actor: Any, folder: Folder) -> None:
    if not folder.is_active:
        raise ValidationError("文件夹已停用，不能上传文件")
    project: Project | None = folder.project
    if project is not None and project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档，不能上传文件")
    if not can_upload_document(actor, project):
        raise PermissionDenied("无权上传文件")


def _create_version(
    *,
    document: Document,
    actor: Any,
    uploaded_file: Any,
    stored_file: StoredFile,
    version_number: int,
) -> DocumentVersion:
    return DocumentVersion.objects.create(
        document=document,
        version_number=version_number,
        original_filename=PurePath(uploaded_file.name).name,
        content_type=getattr(uploaded_file, "content_type", ""),
        file_size=stored_file.size,
        sha256=stored_file.sha256,
        storage_path=stored_file.relative_path,
        uploaded_by=actor,
    )


def document_snapshot(document: Document) -> dict[str, Any]:
    return {
        "id": document.pk,
        "project_id": document.project_id,
        "folder_id": document.folder_id,
        "title": document.title,
        "description": document.description,
        "access_level": document.access_level,
        "current_version_id": document.current_version_id,
    }


def version_snapshot(version: DocumentVersion) -> dict[str, Any]:
    return {
        "id": version.pk,
        "document_id": version.document_id,
        "version_number": version.version_number,
        "original_filename": version.original_filename,
        "file_size": version.file_size,
        "sha256": version.sha256,
        "storage_path": version.storage_path,
    }
