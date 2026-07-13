import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.system.models import SystemBackupRun
from apps.system.services import (
    BackupAlreadyRunning,
    BackupProcessError,
    BackupVerificationError,
    create_system_backup,
    ensure_backup_not_running,
    verify_backup_archive,
)


@pytest.mark.django_db
def test_create_system_backup_copies_to_offsite_and_writes_audit(settings, tmp_path):
    settings.FILE_STORAGE_ROOT = tmp_path / "files"
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = tmp_path / "offsite"
    (settings.FILE_STORAGE_ROOT / "aa").mkdir(parents=True)
    (settings.FILE_STORAGE_ROOT / "aa" / "document.bin").write_bytes(b"document")
    (settings.FILE_STORAGE_ROOT / ".tmp").mkdir()
    (settings.FILE_STORAGE_ROOT / ".tmp" / "partial.upload").write_bytes(b"partial")

    run = create_system_backup(trigger=SystemBackupRun.Trigger.MANUAL, database_dumper=_fake_dumper)

    assert run.status == SystemBackupRun.Status.SUCCESS
    assert run.local_path
    assert run.offsite_path
    assert run.sha256
    assert run.size_bytes > 0
    assert (tmp_path / "local" / _archive_name(run)).is_file()
    assert (tmp_path / "offsite" / _archive_name(run)).is_file()
    archive_info = verify_backup_archive(
        tmp_path / "offsite" / _archive_name(run),
        expected_sha256=run.sha256,
    )
    assert archive_info.manifest["files"]["file_count"] == 1
    assert archive_info.manifest["files"]["entries"][0]["path"] == "aa/document.bin"
    assert len(archive_info.manifest["files"]["entries"][0]["sha256"]) == 64
    assert AuditLog.objects.filter(action="system_backup.create", result="success").exists()
    offsite_audit = AuditLog.objects.get(action="system_backup.offsite_copy", result="success")
    assert offsite_audit.after_data["offsite_copy_available"] is True
    assert "offsite_path" not in offsite_audit.after_data


@pytest.mark.django_db
def test_create_system_backup_succeeds_without_offsite_root(settings, tmp_path):
    settings.FILE_STORAGE_ROOT = tmp_path / "files"
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = None

    run = create_system_backup(database_dumper=_fake_dumper)

    assert run.status == SystemBackupRun.Status.SUCCESS
    assert run.local_path
    assert run.offsite_path == ""
    assert (tmp_path / "local" / _archive_name(run)).is_file()
    assert AuditLog.objects.filter(action="system_backup.create", result="success").exists()
    assert not AuditLog.objects.filter(action="system_backup.offsite_copy").exists()


@pytest.mark.django_db
def test_create_system_backup_fails_when_offsite_copy_hash_differs(settings, tmp_path):
    settings.FILE_STORAGE_ROOT = tmp_path / "files"
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = tmp_path / "offsite"

    def corrupt_copy(source, target):
        target.write_bytes(b"corrupted")

    with pytest.raises(BackupVerificationError):
        create_system_backup(database_dumper=_fake_dumper, copy_file=corrupt_copy)

    run = SystemBackupRun.objects.get()
    assert run.status == SystemBackupRun.Status.FAILURE
    assert "校验失败" in run.error_message
    assert run.local_path


@pytest.mark.django_db
def test_create_system_backup_records_dump_failure(settings, tmp_path):
    settings.FILE_STORAGE_ROOT = tmp_path / "files"
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = tmp_path / "offsite"

    def failing_dumper(output_path):
        raise BackupProcessError("mysqldump failed")

    with pytest.raises(BackupProcessError):
        create_system_backup(database_dumper=failing_dumper)

    run = SystemBackupRun.objects.get()
    assert run.status == SystemBackupRun.Status.FAILURE
    assert run.error_message == "数据库备份命令执行失败"


@pytest.mark.django_db
def test_create_system_backup_rejects_concurrent_run(settings, tmp_path):
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = tmp_path / "offsite"
    lock_dir = settings.SYSTEM_BACKUP_LOCAL_ROOT / ".backup.lock"
    lock_dir.mkdir(parents=True)

    with pytest.raises(BackupAlreadyRunning):
        create_system_backup(database_dumper=_fake_dumper)

    run = SystemBackupRun.objects.get()
    assert run.status == SystemBackupRun.Status.FAILURE
    assert "正在执行" in run.error_message


def test_stale_backup_lock_is_removed_before_permanent_delete(settings, tmp_path, monkeypatch):
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "local"
    lock_dir = settings.SYSTEM_BACKUP_LOCAL_ROOT / ".backup.lock"
    lock_dir.mkdir(parents=True)
    monkeypatch.setattr("apps.system.services._backup_lock_is_stale", lambda _path: True)

    ensure_backup_not_running()

    assert not lock_dir.exists()


@pytest.mark.django_db
def test_restore_command_verifies_archive_and_restores_files(settings, tmp_path, monkeypatch):
    settings.FILE_STORAGE_ROOT = tmp_path / "files"
    settings.SYSTEM_BACKUP_LOCAL_ROOT = tmp_path / "backups"
    settings.SYSTEM_BACKUP_OFFSITE_ROOT = None
    (settings.FILE_STORAGE_ROOT / "aa").mkdir(parents=True)
    (settings.FILE_STORAGE_ROOT / "aa" / "document.bin").write_bytes(b"document")
    run = create_system_backup(database_dumper=_fake_dumper)
    restored_database_dumps = []
    monkeypatch.setattr(
        "apps.system.management.commands.restore_system_backup._ensure_database_empty",
        lambda _database: None,
    )
    monkeypatch.setattr(
        "apps.system.management.commands.restore_system_backup._restore_database",
        lambda *, database, database_dump: restored_database_dumps.append(
            database_dump.read_bytes()
        ),
    )
    target_root = tmp_path / "restored-files"

    call_command(
        "restore_system_backup",
        backup_path=run.local_path,
        sha256=run.sha256,
        target_database_url="mysql://restore:password@127.0.0.1:3306/restore_db",
        target_file_root=str(target_root),
        confirm=True,
        verbosity=0,
    )

    assert [dump.splitlines() for dump in restored_database_dumps] == [[b"-- fake mysql dump"]]
    assert (target_root / "aa" / "document.bin").read_bytes() == b"document"


@pytest.mark.django_db
def test_system_backup_latest_requires_system_admin(client, django_user_model):
    admin = django_user_model.objects.create_user(
        username="admin",
        password="Password123!",
        real_name="管理员",
        email="admin@example.com",
        role="system_admin",
    )
    user = django_user_model.objects.create_user(
        username="operator",
        password="Password123!",
        real_name="操作员",
        email="operator@example.com",
    )
    run = SystemBackupRun.objects.create(
        trigger=SystemBackupRun.Trigger.SCHEDULED,
        status=SystemBackupRun.Status.SUCCESS,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        local_path="D:/backups/example.tar.gz",
        offsite_path="Z:/backups/example.tar.gz",
        sha256="a" * 64,
        size_bytes=123,
    )

    client.force_login(user)
    denied_response = client.get("/api/v1/system/backups/latest/")
    assert denied_response.status_code == 403

    client.force_login(admin)
    response = client.get("/api/v1/system/backups/latest/")
    assert response.status_code == 200
    assert response.json()["id"] == run.pk
    assert response.json()["offsite_available"] is True
    assert "local_path" not in response.json()
    assert "offsite_path" not in response.json()
    assert "error_message" not in response.json()


@pytest.mark.django_db
def test_system_backup_latest_returns_no_content_when_empty(client, django_user_model):
    admin = django_user_model.objects.create_user(
        username="admin",
        password="Password123!",
        real_name="管理员",
        email="admin@example.com",
        role="system_admin",
    )

    client.force_login(admin)
    response = client.get("/api/v1/system/backups/latest/")

    assert response.status_code == 204
    assert response.content == b""


def _fake_dumper(output_path):
    output_path.write_text("-- fake mysql dump\n", encoding="utf-8")


def _archive_name(run):
    return run.local_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
