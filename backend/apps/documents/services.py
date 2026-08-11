import re
import tempfile
from collections.abc import Callable, Iterable
from datetime import timedelta
from pathlib import Path, PurePath
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.files.base import File
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.audit.services import audit_log
from apps.folders.defaults import (
    ARCHIVE_ROOT,
    ENTRY_PREPARATION_ROOT_CODE,
    standard_root_for_code,
    standard_root_for_name,
)
from apps.folders.models import Folder
from apps.projects.models import Project
from common.storage import LocalDocumentStorage, StoredFile
from common.validators import normalize_upload_filename, validate_uploaded_file

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


class ArchiveDownloadCanceled(APIException):
    status_code = 409
    default_detail = "资料下载已取消"
    default_code = "archive_download_canceled"


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
ARCHIVE_COPY_CHUNK_SIZE = 1024 * 1024


def create_document(
    *,
    actor: Any,
    folder: Folder,
    uploaded_file: Any,
    title: str = "",
    description: str = "",
    access_level: str = Document.AccessLevel.INTERNAL,
    source_type: str = Document.SourceType.PROJECT_UPLOAD,
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
) -> Document:
    _ensure_upload_allowed(actor=actor, folder=folder)
    validate_uploaded_file(uploaded_file)
    original_filename = normalize_upload_filename(uploaded_file.name)
    document_title = title.strip() or original_filename
    backend = storage or LocalDocumentStorage()
    stored_file = backend.save_uploaded_file(uploaded_file)
    try:
        with transaction.atomic():
            if folder.project_id is not None:
                Project.objects.select_for_update().get(pk=folder.project_id)
            locked_folder = Folder.objects.select_for_update().get(pk=folder.pk)
            _ensure_upload_allowed(actor=actor, folder=locked_folder)
            _ensure_source_type_matches_folder(source_type=source_type, folder=locked_folder)
            _ensure_folder_accepts_document(
                folder=locked_folder,
                title=document_title,
                original_filename=original_filename,
                sha256=stored_file.sha256,
            )
            document = Document.objects.create(
                project=locked_folder.project,
                folder=locked_folder,
                title=document_title,
                description=description,
                access_level=access_level,
                source_type=source_type,
                created_by=actor,
            )
            version = _create_version(
                document=document,
                actor=actor,
                original_filename=original_filename,
                content_type=_safe_content_type(original_filename),
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
    if not can_update_document(actor, document):
        raise PermissionDenied("无权新增文档版本")
    validate_uploaded_file(uploaded_file)
    original_filename = normalize_upload_filename(uploaded_file.name)
    backend = storage or LocalDocumentStorage()
    stored_file = backend.save_uploaded_file(uploaded_file)
    try:
        with transaction.atomic():
            locked_document = (
                Document.objects.select_for_update()
                .select_related("folder", "project")
                .get(pk=document.pk)
            )
            _ensure_not_deleted(locked_document)
            _ensure_project_write_allowed(locked_document)
            if not can_update_document(actor, locked_document):
                raise PermissionDenied("无权新增文档版本")
            latest_version = (
                DocumentVersion.objects.filter(document=locked_document).aggregate(
                    latest=Max("version_number")
                )["latest"]
                or 0
            )
            version = _create_version(
                document=locked_document,
                actor=actor,
                original_filename=original_filename,
                content_type=_safe_content_type(original_filename),
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
    Folder.objects.select_for_update().get(pk=locked_document.folder_id)
    _ensure_not_deleted(locked_document)
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_update_document(actor, locked_document):
        raise PermissionDenied("无权更新该文档")
    before_data = document_snapshot(locked_document)
    changed_fields = []
    for field in ["title", "description", "access_level"]:
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
    list(
        Folder.objects.select_for_update()
        .filter(pk__in={locked_document.folder_id, folder.pk})
        .order_by("pk")
    )
    _ensure_not_deleted(locked_document)
    _ensure_project_write_allowed(locked_document)
    _ensure_expected_updated_at(locked_document, expected_updated_at)
    if not can_update_document(actor, locked_document):
        raise PermissionDenied("无权移动该文档")
    _validate_target_folder(document=locked_document, folder=folder)
    _ensure_source_type_matches_folder(
        source_type=locked_document.source_type,
        folder=folder,
    )
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
    _revoke_temporary_access_for_document(document=locked_document, actor=actor)
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


def _revoke_temporary_access_for_document(*, document: Document, actor: Any) -> int:
    from apps.access.models import TemporaryAccessGrant

    return TemporaryAccessGrant.objects.filter(
        document_version__document=document,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now(), revoked_by=actor)


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
    from apps.system.services import ensure_backup_not_running

    ensure_backup_not_running()
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


def build_folder_download_zip(
    *,
    actor: Any,
    root_folder: Folder,
    folders: list[Folder],
    documents: Iterable[Document],
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
    is_canceled: Callable[[], bool] | None = None,
) -> tuple[Any, str, int, int, int]:
    backend = storage or LocalDocumentStorage()
    folder_paths = _folder_archive_paths(root_folder=root_folder, folders=folders)
    root_path = _safe_archive_component(root_folder.name, fallback="资料目录")
    return _build_authorized_download_zip(
        actor=actor,
        documents=documents,
        folder_paths=folder_paths,
        fallback_path=root_path,
        archive_filename=f"{root_path}.zip",
        empty_message="当前目录及子目录没有可下载文件",
        audit_action="document.folder_download",
        audit_resource=root_folder,
        request=request,
        storage=backend,
        is_canceled=is_canceled,
    )


def build_document_center_download_zip(
    *,
    actor: Any,
    root_folders: list[Folder],
    folders: list[Folder],
    folder_root_ids: dict[int, int],
    documents: Iterable[Document],
    request: Any = None,
    storage: LocalDocumentStorage | None = None,
    is_canceled: Callable[[], bool] | None = None,
) -> tuple[Any, str, int, int, int]:
    root_by_id = {folder.pk: folder for folder in root_folders}
    folders_by_root: dict[int, list[Folder]] = {root_id: [] for root_id in root_by_id}
    for folder in folders:
        root_id = folder_root_ids.get(folder.pk)
        if root_id in folders_by_root:
            folders_by_root[root_id].append(folder)

    folder_paths: dict[int, str] = {}
    for root_id, root_folder in root_by_id.items():
        folder_paths.update(
            _folder_archive_paths(
                root_folder=root_folder,
                folders=folders_by_root[root_id],
            )
        )

    return _build_authorized_download_zip(
        actor=actor,
        documents=documents,
        folder_paths=folder_paths,
        fallback_path="资料中心",
        archive_filename="资料中心全部资料.zip",
        empty_message="资料中心没有可下载文件",
        audit_action="document.center_download",
        audit_resource_type="DocumentCenter",
        audit_resource_id="all",
        request=request,
        storage=storage or LocalDocumentStorage(),
        is_canceled=is_canceled,
    )


def _build_authorized_download_zip(
    *,
    actor: Any,
    documents: Iterable[Document],
    folder_paths: dict[int, str],
    fallback_path: str,
    archive_filename: str,
    empty_message: str,
    audit_action: str,
    request: Any,
    storage: LocalDocumentStorage,
    audit_resource: Any = None,
    audit_resource_type: str = "",
    audit_resource_id: str = "",
    is_canceled: Callable[[], bool] | None = None,
) -> tuple[Any, str, int, int, int]:
    archive = tempfile.TemporaryFile()
    used_paths: set[str] = set()
    total_size = 0
    document_count = 0

    try:
        with ZipFile(archive, mode="w", compression=ZIP_DEFLATED, allowZip64=True) as zip_file:
            for document in documents:
                if is_canceled is not None and is_canceled():
                    raise ArchiveDownloadCanceled()
                if not can_download_document(actor, document):
                    continue

                version = document.current_version
                if version is None:
                    raise ValidationError("目录中包含没有可下载版本的文档")
                if not storage.exists(version.storage_path):
                    raise StoredFileMissing()

                directory = folder_paths.get(document.folder_id, fallback_path)
                archive_path = _unique_archive_path(
                    directory=directory,
                    filename=version.original_filename,
                    used_paths=used_paths,
                )
                _write_file_to_zip(
                    zip_file=zip_file,
                    source_path=storage.resolve(version.storage_path),
                    archive_path=archive_path,
                    is_canceled=is_canceled,
                )
                total_size += version.file_size
                document_count += 1

        if document_count == 0:
            audit_log(
                user=actor,
                action=audit_action,
                resource=audit_resource,
                resource_type=audit_resource_type,
                resource_id=audit_resource_id,
                result="failed",
                request=request,
                error_message=empty_message,
            )
            raise ValidationError(empty_message)

        archive_size = archive.tell()
        archive.seek(0)
    except Exception:
        archive.close()
        raise

    try:
        audit_log(
            user=actor,
            action=audit_action,
            resource=audit_resource,
            resource_type=audit_resource_type,
            resource_id=audit_resource_id,
            result="success",
            request=request,
            after_data={
                "document_count": document_count,
                "total_size": total_size,
            },
        )
    except Exception:
        archive.close()
        raise
    return archive, archive_filename, total_size, archive_size, document_count


def _write_file_to_zip(
    *,
    zip_file: ZipFile,
    source_path: Path,
    archive_path: str,
    is_canceled: Callable[[], bool] | None,
) -> None:
    with source_path.open("rb") as source, zip_file.open(archive_path, mode="w") as target:
        while chunk := source.read(ARCHIVE_COPY_CHUNK_SIZE):
            if is_canceled is not None and is_canceled():
                raise ArchiveDownloadCanceled()
            target.write(chunk)


def _folder_archive_paths(*, root_folder: Folder, folders: list[Folder]) -> dict[int, str]:
    folder_by_id = {folder.pk: folder for folder in folders}
    folder_by_id[root_folder.pk] = root_folder
    root_path = _safe_archive_component(root_folder.name, fallback="资料目录")
    resolved: dict[int, str] = {root_folder.pk: root_path}
    resolving: set[int] = set()

    def resolve(folder: Folder) -> str:
        cached = resolved.get(folder.pk)
        if cached is not None:
            return cached
        if folder.pk in resolving:
            return root_path

        resolving.add(folder.pk)
        try:
            parent = folder_by_id.get(folder.parent_id) if folder.parent_id else None
            if parent is not None:
                path = f"{resolve(parent)}/{_safe_archive_component(folder.name)}"
            elif folder.project is not None:
                project_label = f"{folder.project.code} {folder.project.name}".strip()
                path = f"{root_path}/{_safe_archive_component(project_label, fallback='项目资料')}"
            else:
                path = f"{root_path}/{_safe_archive_component(folder.name)}"
            resolved[folder.pk] = path
            return path
        finally:
            resolving.discard(folder.pk)

    for folder in folders:
        resolve(folder)
    return resolved


def _safe_archive_component(value: str, fallback: str = "未命名") -> str:
    component = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", value).strip(" .")
    if component in {"", ".", ".."}:
        return fallback
    return component


def _unique_archive_path(*, directory: str, filename: str, used_paths: set[str]) -> str:
    safe_filename = _safe_archive_component(filename, fallback="document")
    candidate = f"{directory}/{safe_filename}"
    normalized = candidate.casefold()
    if normalized not in used_paths:
        used_paths.add(normalized)
        return candidate

    stem = PurePath(safe_filename).stem or "document"
    suffix = PurePath(safe_filename).suffix
    counter = 2
    while True:
        candidate = f"{directory}/{stem} ({counter}){suffix}"
        normalized = candidate.casefold()
        if normalized not in used_paths:
            used_paths.add(normalized)
            return candidate
        counter += 1


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


def _folder_is_within_root(folder: Folder, root_code: str) -> bool:
    current: Folder | None = folder
    visited: set[int] = set()
    while current is not None and current.pk not in visited:
        if current.code == root_code:
            return True
        visited.add(current.pk)
        current = current.parent
    return False


def _ensure_source_type_matches_folder(*, source_type: str, folder: Folder) -> None:
    is_entry_preparation_folder = _folder_is_within_root(
        folder,
        ENTRY_PREPARATION_ROOT_CODE,
    )
    if source_type == Document.SourceType.ENTRANCE_MATERIAL:
        if folder.project_id is None or not is_entry_preparation_folder:
            raise ValidationError("入场前置资料必须上传到当前项目的“入场前置资料”目录")
        return

    if is_entry_preparation_folder:
        raise ValidationError("普通项目资料不能上传到“入场前置资料”目录")


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
    original_filename: str,
    content_type: str,
    stored_file: StoredFile,
    version_number: int,
) -> DocumentVersion:
    return DocumentVersion.objects.create(
        document=document,
        version_number=version_number,
        original_filename=original_filename,
        content_type=content_type,
        file_size=stored_file.size,
        sha256=stored_file.sha256,
        storage_path=stored_file.relative_path,
        uploaded_by=actor,
    )


def _safe_content_type(filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xls": "application/vnd.ms-excel",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(extension, "application/octet-stream")


def document_snapshot(document: Document) -> dict[str, Any]:
    return {
        "id": document.pk,
        "project_id": document.project_id,
        "folder_id": document.folder_id,
        "title": document.title,
        "description": document.description,
        "access_level": document.access_level,
        "source_type": document.source_type,
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
    }
