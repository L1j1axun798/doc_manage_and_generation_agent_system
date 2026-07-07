import tempfile
from datetime import timedelta
from pathlib import PurePath
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.base import File
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.folders.defaults import ARCHIVE_ROOT, standard_root_for_code, standard_root_for_name
from apps.folders.models import Folder
from apps.projects.models import Project
from common.storage import LocalDocumentStorage, StoredFile
from common.validators import validate_uploaded_file

from .models import Document, DocumentVersion
from .permissions import (
    can_delete_document,
    can_download_document,
    can_permanently_delete_document,
    can_restore_document,
    can_update_document,
    can_upload_document,
)


class StoredFileMissing(APIException):
    status_code = 500
    default_detail = "文件存储不一致，当前版本物理文件不存在"
    default_code = "stored_file_missing"


class DocumentConflict(APIException):
    status_code = 409
    default_detail = "文档已被其他操作更新，请刷新后重试"
    default_code = "document_conflict"


class BatchDownloadTooLarge(APIException):
    status_code = 413
    default_detail = "批量下载文件总大小超过限制"
    default_code = "batch_download_too_large"


BATCH_DOWNLOAD_MAX_FILES = 20
BATCH_DOWNLOAD_MAX_BYTES = 500 * 1024 * 1024


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
        _ensure_folder_accepts_document(
            folder=folder,
            title=document_title,
            original_filename=PurePath(uploaded_file.name).name,
            sha256=stored_file.sha256,
        )
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
    if document.is_deleted:
        raise ValidationError("文档已删除，不能新增版本")
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
    if document.is_deleted:
        raise ValidationError("文档已删除，不能下载")
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


@transaction.atomic
def update_document_metadata(
    *,
    actor: Any,
    document: Document,
    data: dict[str, Any],
    expected_updated_at: Any,
    request: Any = None,
) -> Document:
    locked_document = _locked_document(document)
    _ensure_not_deleted(locked_document)
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_update_document(actor, locked_document):
        raise PermissionDenied("无权更新该文档")
    before_data = document_snapshot(locked_document)
    changed_fields = []
    for field in ["title", "description"]:
        if field in data:
            setattr(locked_document, field, data[field])
            changed_fields.append(field)
    if "title" in changed_fields:
        _ensure_folder_accepts_document(
            folder=locked_document.folder,
            title=locked_document.title,
            exclude_document_id=locked_document.pk,
        )
    _touch_document(locked_document, extra_fields=changed_fields)
    audit_log(
        user=actor,
        action="document.update",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=document_snapshot(locked_document),
    )
    return locked_document


@transaction.atomic
def move_document(
    *,
    actor: Any,
    document: Document,
    folder: Folder,
    expected_updated_at: Any,
    request: Any = None,
) -> Document:
    locked_document = _locked_document(document)
    _ensure_not_deleted(locked_document)
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_update_document(actor, locked_document):
        raise PermissionDenied("无权移动该文档")
    _validate_target_folder(document=locked_document, folder=folder)
    current_version = locked_document.current_version
    _ensure_folder_accepts_document(
        folder=folder,
        title=locked_document.title,
        original_filename=current_version.original_filename if current_version else None,
        sha256=current_version.sha256 if current_version else None,
        exclude_document_id=locked_document.pk,
    )
    before_data = document_snapshot(locked_document)
    locked_document.folder = folder
    _touch_document(locked_document, extra_fields=["folder"])
    audit_log(
        user=actor,
        action="document.move",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=document_snapshot(locked_document),
    )
    return locked_document


@transaction.atomic
def soft_delete_document(
    *,
    actor: Any,
    document: Document,
    expected_updated_at: Any,
    request: Any = None,
) -> Document:
    locked_document = _locked_document(document)
    _ensure_not_deleted(locked_document)
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_delete_document(actor, locked_document):
        raise PermissionDenied("无权删除该文档")
    before_data = document_snapshot(locked_document)
    locked_document.deleted_at = timezone.now()
    locked_document.deleted_by = actor
    _touch_document(locked_document, extra_fields=["deleted_at", "deleted_by"])
    audit_log(
        user=actor,
        action="document.delete",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=document_snapshot(locked_document),
    )
    return locked_document


@transaction.atomic
def restore_document(
    *,
    actor: Any,
    document: Document,
    expected_updated_at: Any,
    request: Any = None,
) -> Document:
    locked_document = _locked_document(document)
    if not locked_document.is_deleted:
        raise ValidationError("文档未删除，不能恢复")
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_restore_document(actor, locked_document):
        raise PermissionDenied("无权恢复该文档")
    if not locked_document.folder.is_active:
        raise ValidationError("所在文件夹已停用，不能恢复")
    current_version = locked_document.current_version
    _ensure_folder_accepts_document(
        folder=locked_document.folder,
        title=locked_document.title,
        original_filename=current_version.original_filename if current_version else None,
        sha256=current_version.sha256 if current_version else None,
        exclude_document_id=locked_document.pk,
    )
    before_data = document_snapshot(locked_document)
    locked_document.deleted_at = None
    locked_document.deleted_by = None
    _touch_document(locked_document, extra_fields=["deleted_at", "deleted_by"])
    audit_log(
        user=actor,
        action="document.restore",
        resource=locked_document,
        result="success",
        request=request,
        before_data=before_data,
        after_data=document_snapshot(locked_document),
    )
    return locked_document


def permanently_delete_document(
    *,
    actor: Any,
    document: Document,
    expected_updated_at: Any,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> None:
    backend = storage or LocalDocumentStorage()
    with transaction.atomic():
        locked_document = _locked_document(document)
        _ensure_expected_updated_at(locked_document, expected_updated_at)
        if not can_permanently_delete_document(actor, locked_document):
            raise PermissionDenied("无权永久删除该文档")
        if not locked_document.is_deleted:
            raise ValidationError("请先将文档删除到回收站")
        before_data = document_snapshot(locked_document)
        storage_paths = list(locked_document.versions.values_list("storage_path", flat=True))
        locked_document.current_version = None
        locked_document.save(update_fields=["current_version", "updated_at"])
        locked_document.delete()
        audit_log(
            user=actor,
            action="document.permanent_delete",
            result="success",
            request=request,
            resource_type="Document",
            resource_id=str(document.pk),
            before_data=before_data,
        )
    for storage_path in storage_paths:
        backend.delete(storage_path)


def build_batch_download_zip(
    *,
    actor: Any,
    documents: list[Document],
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> tuple[Any, str, int]:
    if len(documents) > BATCH_DOWNLOAD_MAX_FILES:
        raise ValidationError(f"单次最多下载 {BATCH_DOWNLOAD_MAX_FILES} 个文件")
    backend = storage or LocalDocumentStorage()
    versions: list[DocumentVersion] = []
    total_size = 0
    for document in documents:
        if document.is_deleted:
            raise ValidationError("不能批量下载已删除文档")
        if not can_download_document(actor, document):
            audit_log(
                user=actor,
                action="document.batch_download",
                resource=document,
                result="denied",
                request=request,
                error_message="无权下载批量中的文件",
            )
            raise PermissionDenied("批量下载包含无权下载的文件")
        version = document.current_version
        if version is None:
            raise ValidationError("批量下载包含没有当前版本的文档")
        total_size += version.file_size
        if total_size > BATCH_DOWNLOAD_MAX_BYTES:
            raise BatchDownloadTooLarge()
        if not backend.exists(version.storage_path):
            raise StoredFileMissing()
        versions.append(version)

    archive = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    used_names: set[str] = set()
    with ZipFile(archive, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for version in versions:
            archive_name = _unique_archive_name(version.original_filename, used_names)
            zip_file.write(backend.resolve(version.storage_path), arcname=archive_name)
    archive.seek(0)
    audit_log(
        user=actor,
        action="document.batch_download",
        result="success",
        request=request,
        resource_type="DocumentBatch",
        resource_id=",".join(str(document.pk) for document in documents),
        after_data={"document_count": len(documents), "total_size": total_size},
    )
    return archive, "documents.zip", total_size


def _ensure_upload_allowed(*, actor: Any, folder: Folder) -> None:
    if not folder.is_active:
        raise ValidationError("文件夹已停用，不能上传文件")
    _ensure_not_qualification_root_folder(folder=folder)
    _ensure_not_archive_folder(folder=folder, message="归档目录不能直接上传文件")
    project: Project | None = folder.project
    if project is not None and project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档，不能上传文件")
    if not can_upload_document(actor, project):
        raise PermissionDenied("无权上传文件")


def _locked_document(document: Document) -> Document:
    return (
        Document.objects.select_for_update()
        .select_related("project", "folder", "current_version", "deleted_by")
        .get(pk=document.pk)
    )


def _ensure_not_deleted(document: Document) -> None:
    if document.is_deleted:
        raise ValidationError("文档已删除")


def _ensure_project_write_allowed(document: Document) -> None:
    if document.project is not None and document.project.status == Project.Status.ARCHIVED:
        raise ValidationError("项目已归档，不能修改文档")


def _ensure_expected_updated_at(document: Document, expected_updated_at: Any) -> None:
    if document.updated_at != expected_updated_at:
        raise DocumentConflict()


def _touch_document(document: Document, extra_fields: list[str] | None = None) -> None:
    previous_updated_at = document.updated_at
    document.lock_version += 1
    update_fields = ["lock_version", "updated_at", *(extra_fields or [])]
    document.save(update_fields=update_fields)
    if document.updated_at <= previous_updated_at:
        document.updated_at = previous_updated_at + timedelta(microseconds=1)
        Document.objects.filter(pk=document.pk).update(updated_at=document.updated_at)


def _validate_target_folder(*, document: Document, folder: Folder) -> None:
    if not folder.is_active:
        raise ValidationError("目标文件夹已停用")
    _ensure_not_qualification_root_folder(folder=folder)
    _ensure_not_archive_folder(folder=folder, message="归档目录不能作为目标目录")
    if folder.project_id != document.project_id:
        raise ValidationError("目标文件夹和文档项目不一致")


def _ensure_folder_accepts_document(
    *,
    folder: Folder,
    title: str | None = None,
    original_filename: str | None = None,
    sha256: str | None = None,
    exclude_document_id: int | None = None,
) -> None:
    documents = Document.objects.filter(folder=folder, deleted_at__isnull=True)
    if exclude_document_id is not None:
        documents = documents.exclude(pk=exclude_document_id)

    name_filters = Q()
    clean_title = title.strip() if title else ""
    clean_filename = PurePath(original_filename).name if original_filename else ""
    if clean_title:
        name_filters |= Q(title=clean_title)
    if clean_filename:
        name_filters |= Q(current_version__original_filename=clean_filename)
    if name_filters and documents.filter(name_filters).exists():
        raise ValidationError("同一目录下已存在同名文件")

    if sha256 and documents.filter(current_version__sha256=sha256).exists():
        raise ValidationError("同一目录下已存在内容相同的重复文件")


def _ensure_not_qualification_root_folder(*, folder: Folder) -> None:
    if not _is_qualification_root_folder(folder):
        return
    raise ValidationError("资质根目录不能直接存储文件，请选择具体公司或人员")


def _ensure_not_archive_folder(*, folder: Folder, message: str) -> None:
    if not _is_archive_folder(folder):
        return
    raise ValidationError(message)


def _is_qualification_root_folder(folder: Folder) -> bool:
    if folder.parent_id is not None or folder.project_id is not None:
        return False
    definition = standard_root_for_code(folder.code) or standard_root_for_name(folder.name)
    return definition is not None and definition.code in {"PUBLIC-COMPANY", "PUBLIC-STAFF"}


def _is_archive_folder(folder: Folder) -> bool:
    if folder.project_id is not None:
        return False
    return (
        folder.code == ARCHIVE_ROOT.code
        or folder.name in ARCHIVE_ROOT.names
        or folder.code.startswith(f"{ARCHIVE_ROOT.code}-")
        or folder.name.endswith("年归档资料")
    )


def _unique_archive_name(filename: str, used_names: set[str]) -> str:
    candidate = PurePath(filename).name or "document"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate
    stem = PurePath(candidate).stem or "document"
    suffix = PurePath(candidate).suffix
    counter = 2
    while True:
        deduped = f"{stem} ({counter}){suffix}"
        if deduped not in used_names:
            used_names.add(deduped)
            return deduped
        counter += 1


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
        "lock_version": document.lock_version,
        "deleted_at": document.deleted_at.isoformat() if document.deleted_at else None,
        "deleted_by_id": document.deleted_by_id,
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
