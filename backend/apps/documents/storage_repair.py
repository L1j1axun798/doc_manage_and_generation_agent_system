import hashlib
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from common.storage import LocalDocumentStorage

from .models import DocumentVersion


class StoragePathRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoragePathRepair:
    version_id: int
    original_path: str
    canonical_path: str


def repair_document_storage_paths(
    *,
    dry_run: bool = True,
    storage: LocalDocumentStorage | None = None,
) -> list[StoragePathRepair]:
    backend = storage or LocalDocumentStorage()
    repairs = _verified_storage_path_repairs(backend=backend)
    if dry_run or not repairs:
        return repairs

    version_ids = [repair.version_id for repair in repairs]
    canonical_paths = [repair.canonical_path for repair in repairs]
    if len(canonical_paths) != len(set(canonical_paths)):
        raise StoragePathRepairError("规范化后的文件存储路径发生重复")

    with transaction.atomic():
        versions = {
            version.id: version
            for version in DocumentVersion.objects.select_for_update().filter(id__in=version_ids)
        }
        if len(versions) != len(repairs):
            raise StoragePathRepairError("修复期间文件版本记录发生变化")
        if (
            DocumentVersion.objects.exclude(id__in=version_ids)
            .filter(storage_path__in=canonical_paths)
            .exists()
        ):
            raise StoragePathRepairError("规范化后的文件存储路径已被其他版本占用")

        for repair in repairs:
            version = versions[repair.version_id]
            if version.storage_path != repair.original_path:
                raise StoragePathRepairError("修复期间文件存储路径发生变化")
            version.storage_path = repair.canonical_path
        DocumentVersion.objects.bulk_update(versions.values(), ["storage_path"])

    return repairs


def _verified_storage_path_repairs(*, backend: LocalDocumentStorage) -> list[StoragePathRepair]:
    repairs: list[StoragePathRepair] = []
    versions = DocumentVersion.objects.filter(storage_path__contains="\\").order_by("id")
    for version in versions.iterator(chunk_size=200):
        canonical_path = backend.canonical_relative_path(version.storage_path)
        physical_path = backend.resolve(version.storage_path)
        if not physical_path.is_file():
            raise StoragePathRepairError(f"版本 {version.id} 的物理文件不存在")
        if physical_path.stat().st_size != version.file_size:
            raise StoragePathRepairError(f"版本 {version.id} 的物理文件大小不一致")
        if _file_sha256(physical_path) != version.sha256:
            raise StoragePathRepairError(f"版本 {version.id} 的物理文件 SHA-256 不一致")
        repairs.append(
            StoragePathRepair(
                version_id=version.id,
                original_path=version.storage_path,
                canonical_path=canonical_path,
            )
        )
    return repairs


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
