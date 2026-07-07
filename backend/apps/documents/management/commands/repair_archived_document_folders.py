from typing import Any

from django.core.management.base import BaseCommand

from apps.documents.repair import repair_archived_document_folders


class Command(BaseCommand):
    help = "修复已归档项目文档未挂入归档年份目录树的数据"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--apply",
            action="store_true",
            help="实际写入修复；不传时只预览将要修复的文档",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = not options["apply"]
        repairs = repair_archived_document_folders(dry_run=dry_run)
        mode = "预览" if dry_run else "已修复"
        if not repairs:
            self.stdout.write(self.style.SUCCESS(f"{mode} 0 条异常归档文档"))
            return

        for item in repairs:
            target = item.target_path
            if item.target_folder_id is not None:
                target = f"{target} (folder_id={item.target_folder_id})"
            self.stdout.write(
                f"document_id={item.document_id} project_id={item.project_id} "
                f"{item.source_path} -> {target}"
            )
        self.stdout.write(self.style.SUCCESS(f"{mode} {len(repairs)} 条异常归档文档"))
