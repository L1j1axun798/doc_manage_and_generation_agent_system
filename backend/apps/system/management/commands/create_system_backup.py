from django.core.management.base import BaseCommand, CommandError

from apps.system.models import SystemBackupRun
from apps.system.services import BackupError, create_system_backup


class Command(BaseCommand):
    help = "创建系统备份：MySQL dump、文件归档、本机保存，并可选复制到离机目录。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--trigger",
            choices=[choice[0] for choice in SystemBackupRun.Trigger.choices],
            default=SystemBackupRun.Trigger.SCHEDULED,
        )

    def handle(self, *args, **options):
        try:
            run = create_system_backup(trigger=options["trigger"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        offsite = run.offsite_path or "not-configured"
        self.stdout.write(
            self.style.SUCCESS(
                f"系统备份完成：id={run.pk} local={run.local_path} offsite={offsite}"
            )
        )
