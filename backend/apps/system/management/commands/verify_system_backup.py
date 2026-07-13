from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.system.services import BackupVerificationError, verify_backup_archive


class Command(BaseCommand):
    help = "校验系统备份包结构和 SHA-256。"

    def add_arguments(self, parser):
        parser.add_argument("--backup-path", required=True)
        parser.add_argument("--sha256", required=True)

    def handle(self, *args, **options):
        try:
            info = verify_backup_archive(
                Path(options["backup_path"]),
                expected_sha256=options["sha256"],
            )
        except BackupVerificationError as exc:
            raise CommandError(str(exc)) from exc

        manifest = info.manifest
        self.stdout.write(self.style.SUCCESS("备份包校验通过"))
        self.stdout.write(f"path={info.path}")
        self.stdout.write(f"sha256={info.sha256}")
        self.stdout.write(f"size_bytes={info.size_bytes}")
        self.stdout.write(f"backup_id={manifest.get('backup_id')}")
        self.stdout.write(f"created_at={manifest.get('created_at')}")
