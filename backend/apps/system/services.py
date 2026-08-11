import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit_log

from .models import SystemBackupRun

DumpCallback = Callable[[Path], None]
CopyCallback = Callable[[Path, Path], object]

BACKUP_ARCHIVE_VERSION = 1
BACKUP_LOCK_STALE_SECONDS = 6 * 60 * 60


class BackupError(Exception):
    pass


class BackupAlreadyRunning(BackupError):
    pass


class BackupConfigurationError(BackupError):
    pass


class BackupProcessError(BackupError):
    pass


class BackupVerificationError(BackupError):
    pass


@dataclass(frozen=True)
class BackupArchiveInfo:
    path: Path
    manifest: dict[str, Any]
    sha256: str
    size_bytes: int


def create_system_backup(
    *,
    trigger: str = SystemBackupRun.Trigger.SCHEDULED,
    actor: Any = None,
    request: Any = None,
    database_dumper: DumpCallback | None = None,
    copy_file: CopyCallback | None = None,
) -> SystemBackupRun:
    local_root = _configured_path(settings.SYSTEM_BACKUP_LOCAL_ROOT)
    local_root.mkdir(parents=True, exist_ok=True)

    lock_dir = local_root / ".backup.lock"
    try:
        _acquire_backup_lock(lock_dir)
    except BackupAlreadyRunning as exc:
        run = _create_failed_run(
            trigger=trigger,
            actor=actor,
            request=request,
            message="已有系统备份任务正在执行",
        )
        raise BackupAlreadyRunning(run.error_message) from exc

    run = SystemBackupRun.objects.create(
        trigger=trigger,
        status=SystemBackupRun.Status.RUNNING,
        started_at=timezone.now(),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    work_dir: Path | None = None
    final_local_path: Path | None = None
    final_offsite_path: Path | None = None
    offsite_tmp_path: Path | None = None

    try:
        offsite_root = _get_optional_offsite_root()
        tmp_root = local_root / ".tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix="system-backup-", dir=tmp_root))

        database_dump = work_dir / "database.sql"
        (database_dumper or dump_mysql_database)(database_dump)

        manifest = _build_manifest(run=run, database_dump=database_dump)
        manifest_path = work_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        archive_tmp_path = work_dir / "backup.tar.gz"
        _write_backup_archive(
            archive_path=archive_tmp_path,
            database_dump=database_dump,
            manifest_path=manifest_path,
            files_root=_configured_path(settings.FILE_STORAGE_ROOT),
        )
        verify_backup_archive(archive_tmp_path)
        local_sha256, local_size = calculate_sha256(archive_tmp_path)

        final_local_path = local_root / _build_archive_filename(run)
        os.replace(archive_tmp_path, final_local_path)

        if offsite_root is not None:
            offsite_root.mkdir(parents=True, exist_ok=True)
            offsite_tmp_path = offsite_root / f"{final_local_path.name}.tmp-{uuid4().hex}"
            (copy_file or shutil.copy2)(final_local_path, offsite_tmp_path)
            offsite_sha256, offsite_size = calculate_sha256(offsite_tmp_path)
            if offsite_sha256 != local_sha256 or offsite_size != local_size:
                raise BackupVerificationError("离机副本校验失败")

            final_offsite_path = offsite_root / final_local_path.name
            os.replace(offsite_tmp_path, final_offsite_path)
            offsite_tmp_path = None

        with transaction.atomic():
            run.status = SystemBackupRun.Status.SUCCESS
            run.finished_at = timezone.now()
            run.local_path = str(final_local_path)
            run.offsite_path = str(final_offsite_path) if final_offsite_path is not None else ""
            run.sha256 = local_sha256
            run.size_bytes = local_size
            run.error_message = ""
            run.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "local_path",
                    "offsite_path",
                    "sha256",
                    "size_bytes",
                    "error_message",
                    "updated_at",
                ]
            )
        if final_offsite_path is not None:
            audit_log(
                user=actor,
                action="system_backup.offsite_copy",
                result="success",
                request=request,
                resource=run,
                after_data={"offsite_copy_available": True, "sha256": run.sha256},
            )
        audit_log(
            user=actor,
            action="system_backup.create",
            result="success",
            request=request,
            resource=run,
            after_data=backup_run_snapshot(run),
        )
        cleanup_expired_backups()
        return run
    except Exception as exc:
        _delete_path_if_exists(offsite_tmp_path)
        _mark_backup_failed(
            run=run,
            actor=actor,
            request=request,
            error_message=_safe_backup_error(exc),
            local_path=final_local_path,
            offsite_path=final_offsite_path,
        )
        raise
    finally:
        if work_dir is not None:
            shutil.rmtree(work_dir, ignore_errors=True)
        _release_backup_lock(lock_dir)


def dump_mysql_database(output_path: Path) -> None:
    database = settings.DATABASES["default"]
    if database.get("ENGINE") != "django.db.backends.mysql":
        raise BackupConfigurationError("系统备份仅支持生产 MySQL 数据库")

    name = database.get("NAME")
    if not name:
        raise BackupConfigurationError("DATABASE_URL 缺少数据库名")

    command = [
        settings.SYSTEM_BACKUP_MYSQLDUMP_BIN,
        "--single-transaction",
        "--skip-lock-tables",
        "--no-tablespaces",
        "--skip-masking-policies",
        "--set-gtid-purged=OFF",
        "--quick",
        "--routines",
        "--triggers",
        "--events",
        "--default-character-set=utf8mb4",
    ]
    command.extend(_mysql_connection_args(database))
    command.append(str(name))

    env = _mysql_password_env(database)
    result = _run_mysqldump(command=command, output_path=output_path, env=env)
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    if (
        result.returncode != 0
        and "--skip-masking-policies" in command
        and "unknown option '--skip-masking-policies'" in stderr
    ):
        compatible_command = [
            argument for argument in command if argument != "--skip-masking-policies"
        ]
        result = _run_mysqldump(
            command=compatible_command,
            output_path=output_path,
            env=env,
        )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise BackupProcessError(stderr or "mysqldump 执行失败")


def _run_mysqldump(
    *,
    command: list[str],
    output_path: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[bytes]:
    with output_path.open("wb") as target:
        return subprocess.run(
            command,
            stdout=target,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )


def verify_backup_archive(
    backup_path: Path,
    *,
    expected_sha256: str = "",
) -> BackupArchiveInfo:
    archive_path = Path(backup_path)
    if not archive_path.is_file():
        raise BackupVerificationError(f"备份文件不存在：{archive_path}")

    digest, size_bytes = calculate_sha256(archive_path)
    if expected_sha256 and digest != expected_sha256:
        raise BackupVerificationError("备份包 SHA-256 与期望值不一致")

    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
        required_names = {"manifest.json", "database.sql"}
        missing_names = required_names - names
        if missing_names:
            raise BackupVerificationError(f"备份包缺少文件：{', '.join(sorted(missing_names))}")
        manifest_file = archive.extractfile("manifest.json")
        if manifest_file is None:
            raise BackupVerificationError("备份包 manifest 无法读取")
        manifest = json.loads(manifest_file.read().decode("utf-8"))
        if manifest.get("archive_version") != BACKUP_ARCHIVE_VERSION:
            raise BackupVerificationError("备份包版本不兼容")
        if not any(name == "files" or name.startswith("files/") for name in names):
            raise BackupVerificationError("备份包缺少文件存储目录")
        _verify_archive_contents(archive=archive, manifest=manifest, names=names)

    return BackupArchiveInfo(
        path=archive_path,
        manifest=manifest,
        sha256=digest,
        size_bytes=size_bytes,
    )


def cleanup_expired_backups() -> None:
    retention_days = settings.SYSTEM_BACKUP_RETENTION_DAYS
    if retention_days <= 0:
        return

    cutoff = timezone.now() - timedelta(days=retention_days)
    expired_runs = SystemBackupRun.objects.filter(
        status=SystemBackupRun.Status.SUCCESS,
        finished_at__lt=cutoff,
    )
    for run in expired_runs:
        _delete_path_if_exists(Path(run.local_path) if run.local_path else None)
        _delete_path_if_exists(Path(run.offsite_path) if run.offsite_path else None)


def calculate_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def backup_run_snapshot(run: SystemBackupRun) -> dict[str, Any]:
    return {
        "id": run.pk,
        "trigger": run.trigger,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "local_copy_available": bool(run.local_path),
        "offsite_copy_available": bool(run.offsite_path),
        "sha256": run.sha256,
        "size_bytes": run.size_bytes,
        "has_error": bool(run.error_message),
    }


def _create_failed_run(
    *,
    trigger: str,
    actor: Any,
    request: Any,
    message: str,
) -> SystemBackupRun:
    now = timezone.now()
    run = SystemBackupRun.objects.create(
        trigger=trigger,
        status=SystemBackupRun.Status.FAILURE,
        started_at=now,
        finished_at=now,
        error_message=message,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    audit_log(
        user=actor,
        action="system_backup.create",
        result="failure",
        request=request,
        resource=run,
        error_message=message,
        after_data=backup_run_snapshot(run),
    )
    return run


def _mark_backup_failed(
    *,
    run: SystemBackupRun,
    actor: Any,
    request: Any,
    error_message: str,
    local_path: Path | None,
    offsite_path: Path | None,
) -> None:
    run.status = SystemBackupRun.Status.FAILURE
    run.finished_at = timezone.now()
    if local_path is not None:
        run.local_path = str(local_path)
    if offsite_path is not None:
        run.offsite_path = str(offsite_path)
    run.error_message = error_message[:4000]
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "local_path",
            "offsite_path",
            "error_message",
            "updated_at",
        ]
    )
    audit_log(
        user=actor,
        action="system_backup.create",
        result="failure",
        request=request,
        resource=run,
        error_message=run.error_message,
        after_data=backup_run_snapshot(run),
    )


def _safe_backup_error(exc: Exception) -> str:
    if isinstance(exc, BackupVerificationError):
        return "备份校验失败"
    if isinstance(exc, BackupConfigurationError):
        return "备份配置无效"
    if isinstance(exc, BackupProcessError):
        return "数据库备份命令执行失败"
    return "系统备份失败"


def _build_archive_filename(run: SystemBackupRun) -> str:
    timestamp = timezone.localtime(run.started_at).strftime("%Y%m%d-%H%M%S")
    return f"wind-doc-system-backup-{timestamp}-{run.pk}.tar.gz"


def _build_manifest(*, run: SystemBackupRun, database_dump: Path) -> dict[str, Any]:
    files_root = _configured_path(settings.FILE_STORAGE_ROOT)
    file_entries = _file_storage_manifest(files_root)
    files_size = sum(entry["size_bytes"] for entry in file_entries)
    database_sha256, database_size = calculate_sha256(database_dump)
    return {
        "archive_version": BACKUP_ARCHIVE_VERSION,
        "system": "wind-doc-system",
        "backup_id": run.pk,
        "trigger": run.trigger,
        "created_at": timezone.now().isoformat(),
        "database": {
            "engine": settings.DATABASES["default"].get("ENGINE", ""),
            "name": settings.DATABASES["default"].get("NAME", ""),
            "dump_file": "database.sql",
            "sha256": database_sha256,
            "size_bytes": database_size,
        },
        "files": {
            "archive_path": "files",
            "file_count": len(file_entries),
            "size_bytes": files_size,
            "entries": file_entries,
        },
    }


def _write_backup_archive(
    *,
    archive_path: Path,
    database_dump: Path,
    manifest_path: Path,
    files_root: Path,
) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(manifest_path, arcname="manifest.json")
        archive.add(database_dump, arcname="database.sql")
        _add_files_root(archive=archive, files_root=files_root)


def _add_files_root(*, archive: tarfile.TarFile, files_root: Path) -> None:
    info = tarfile.TarInfo("files")
    info.type = tarfile.DIRTYPE
    info.mtime = timezone.now().timestamp()
    archive.addfile(info)
    if not files_root.exists():
        return

    for path in sorted(files_root.rglob("*")):
        relative_path = path.relative_to(files_root)
        if relative_path.parts and relative_path.parts[0] == ".tmp":
            continue
        archive.add(path, arcname=str(Path("files") / relative_path), recursive=False)


def _file_storage_manifest(files_root: Path) -> list[dict[str, Any]]:
    if not files_root.exists():
        return []

    entries: list[dict[str, Any]] = []
    for path in sorted(files_root.rglob("*")):
        relative_path = path.relative_to(files_root)
        if relative_path.parts and relative_path.parts[0] == ".tmp":
            continue
        if path.is_file():
            digest, size_bytes = calculate_sha256(path)
            entries.append(
                {
                    "path": relative_path.as_posix(),
                    "sha256": digest,
                    "size_bytes": size_bytes,
                }
            )
    return entries


def ensure_backup_not_running() -> None:
    lock_dir = _configured_path(settings.SYSTEM_BACKUP_LOCAL_ROOT) / ".backup.lock"
    if not lock_dir.exists():
        return
    if _backup_lock_is_stale(lock_dir):
        shutil.rmtree(lock_dir, ignore_errors=True)
        return
    raise BackupAlreadyRunning("系统备份正在执行，暂不能永久删除文件")


def _acquire_backup_lock(lock_dir: Path) -> None:
    try:
        lock_dir.mkdir()
    except FileExistsError:
        if not _backup_lock_is_stale(lock_dir):
            raise BackupAlreadyRunning("已有系统备份任务正在执行") from None
        shutil.rmtree(lock_dir, ignore_errors=True)
        try:
            lock_dir.mkdir()
        except FileExistsError as exc:
            raise BackupAlreadyRunning("已有系统备份任务正在执行") from exc
    owner = {"pid": os.getpid(), "created_at": timezone.now().isoformat()}
    (lock_dir / "owner.json").write_text(json.dumps(owner), encoding="utf-8")


def _release_backup_lock(lock_dir: Path) -> None:
    shutil.rmtree(lock_dir, ignore_errors=True)


def _backup_lock_is_stale(lock_dir: Path) -> bool:
    try:
        age = timezone.now().timestamp() - lock_dir.stat().st_mtime
    except OSError:
        return False
    if age <= BACKUP_LOCK_STALE_SECONDS:
        return False
    owner_path = lock_dir / "owner.json"
    try:
        owner = json.loads(owner_path.read_text(encoding="utf-8"))
        pid = int(owner.get("pid", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return True
    if pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return True
    return False


def _verify_archive_contents(
    *,
    archive: tarfile.TarFile,
    manifest: dict[str, Any],
    names: set[str],
) -> None:
    database = manifest.get("database", {})
    _verify_archive_member(
        archive=archive,
        archive_name="database.sql",
        expected_sha256=str(database.get("sha256", "")),
        expected_size=int(database.get("size_bytes", -1)),
    )
    files = manifest.get("files", {})
    entries = files.get("entries")
    if not isinstance(entries, list):
        raise BackupVerificationError("备份包缺少文件哈希清单")
    expected_names = {"files"}
    total_size = 0
    for entry in entries:
        relative_path = str(entry.get("path", ""))
        if not relative_path or relative_path.startswith("/") or ".." in Path(relative_path).parts:
            raise BackupVerificationError("备份文件清单包含非法路径")
        archive_name = f"files/{relative_path}"
        expected_names.add(archive_name)
        expected_size = int(entry.get("size_bytes", -1))
        _verify_archive_member(
            archive=archive,
            archive_name=archive_name,
            expected_sha256=str(entry.get("sha256", "")),
            expected_size=expected_size,
        )
        total_size += expected_size
    actual_file_names = {
        name for name in names if name.startswith("files/") and archive.getmember(name).isfile()
    }
    if actual_file_names != expected_names - {"files"}:
        raise BackupVerificationError("备份包文件与 manifest 清单不一致")
    if len(entries) != int(files.get("file_count", -1)) or total_size != int(
        files.get("size_bytes", -1)
    ):
        raise BackupVerificationError("备份包文件统计与 manifest 不一致")


def _verify_archive_member(
    *,
    archive: tarfile.TarFile,
    archive_name: str,
    expected_sha256: str,
    expected_size: int,
) -> None:
    member = archive.getmember(archive_name)
    source = archive.extractfile(member)
    if source is None:
        raise BackupVerificationError(f"备份成员无法读取：{archive_name}")
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        size += len(chunk)
        digest.update(chunk)
    if not expected_sha256 or digest.hexdigest() != expected_sha256 or size != expected_size:
        raise BackupVerificationError(f"备份成员校验失败：{archive_name}")


def _get_optional_offsite_root() -> Path | None:
    offsite_root = getattr(settings, "SYSTEM_BACKUP_OFFSITE_ROOT", None)
    if offsite_root is None:
        return None
    return _configured_path(offsite_root)


def _configured_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(settings.BASE_DIR) / path


def _mysql_connection_args(database: dict[str, Any]) -> list[str]:
    args: list[str] = []
    host = database.get("HOST")
    port = database.get("PORT")
    user = database.get("USER")
    if host:
        args.append(f"--host={host}")
    if port:
        args.append(f"--port={port}")
    if user:
        args.append(f"--user={user}")
    return args


def _mysql_password_env(database: dict[str, Any]) -> dict[str, str] | None:
    password = database.get("PASSWORD")
    if not password:
        return None
    env = os.environ.copy()
    env["MYSQL_PWD"] = str(password)
    return env


def _delete_path_if_exists(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
