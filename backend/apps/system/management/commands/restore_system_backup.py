import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.system.services import BackupVerificationError, verify_backup_archive


class Command(BaseCommand):
    help = "将系统备份包恢复到指定空库和指定空文件目录。"

    def add_arguments(self, parser):
        parser.add_argument("--backup-path", required=True)
        parser.add_argument("--target-database-url", required=True)
        parser.add_argument("--target-file-root", required=True)
        parser.add_argument("--sha256", required=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("恢复操作必须传入 --confirm")

        backup_path = Path(options["backup_path"])
        target_file_root = Path(options["target_file_root"])
        try:
            verify_backup_archive(backup_path, expected_sha256=options["sha256"])
        except BackupVerificationError as exc:
            raise CommandError(str(exc)) from exc

        database = _parse_mysql_url(options["target_database_url"])
        _ensure_database_empty(database)
        _ensure_directory_empty(target_file_root)

        work_dir = Path(tempfile.mkdtemp(prefix="system-backup-restore-"))
        try:
            with tarfile.open(backup_path, "r:gz") as archive:
                archive.extractall(work_dir, filter="data")

            database_dump = work_dir / "database.sql"
            files_root = work_dir / "files"
            if not database_dump.is_file():
                raise CommandError("备份包缺少 database.sql")
            if not files_root.is_dir():
                raise CommandError("备份包缺少 files 目录")

            _restore_database(database=database, database_dump=database_dump)
            _restore_files(source_root=files_root, target_root=target_file_root)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"恢复完成：database={database['name']} file_root={target_file_root}"
            )
        )


def _parse_mysql_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"mysql", "mysql2"}:
        raise CommandError("恢复命令仅支持 mysql:// 数据库地址")
    if not parsed.path or parsed.path == "/":
        raise CommandError("target database url 缺少数据库名")

    return {
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "name": unquote(parsed.path.lstrip("/")),
    }


def _mysql_command(database: dict[str, str], *, extra_args: list[str] | None = None) -> list[str]:
    command = [settings.SYSTEM_BACKUP_MYSQL_BIN, "--default-character-set=utf8mb4"]
    if database["host"]:
        command.append(f"--host={database['host']}")
    if database["port"]:
        command.append(f"--port={database['port']}")
    if database["user"]:
        command.append(f"--user={database['user']}")
    if extra_args:
        command.extend(extra_args)
    command.append(database["name"])
    return command


def _mysql_env(database: dict[str, str]) -> dict[str, str] | None:
    if not database["password"]:
        return None
    env = os.environ.copy()
    env["MYSQL_PWD"] = database["password"]
    return env


def _ensure_database_empty(database: dict[str, str]) -> None:
    query = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE();"
    result = subprocess.run(
        _mysql_command(
            database,
            extra_args=["--batch", "--skip-column-names", "--execute", query],
        ),
        capture_output=True,
        env=_mysql_env(database),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CommandError(result.stderr.strip() or "检查目标数据库失败")
    if result.stdout.strip() != "0":
        raise CommandError("目标数据库不是空库；恢复命令禁止覆盖或叠加现有数据库")


def _ensure_directory_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise CommandError("目标文件目录不是空目录；恢复命令禁止覆盖或叠加现有文件")


def _restore_database(*, database: dict[str, str], database_dump: Path) -> None:
    with database_dump.open("rb") as source:
        result = subprocess.run(
            _mysql_command(database),
            stdin=source,
            stderr=subprocess.PIPE,
            env=_mysql_env(database),
            check=False,
        )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise CommandError(stderr or "导入数据库备份失败")


def _restore_files(*, source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for child in source_root.iterdir():
        target = target_root / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)
