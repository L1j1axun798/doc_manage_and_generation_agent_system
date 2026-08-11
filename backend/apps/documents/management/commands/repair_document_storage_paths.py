from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.documents.storage_repair import StoragePathRepairError, repair_document_storage_paths


class Command(BaseCommand):
    help = "校验并规范化从 Windows 迁移到 Linux 的文档存储路径"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="校验物理文件大小和 SHA-256 后写入修复；不传时只预览数量",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = not options["apply"]
        try:
            repairs = repair_document_storage_paths(dry_run=dry_run)
        except StoragePathRepairError as exc:
            raise CommandError(str(exc)) from exc

        mode = "待修复" if dry_run else "已修复"
        self.stdout.write(self.style.SUCCESS(f"{mode} {len(repairs)} 条文档版本存储路径"))
