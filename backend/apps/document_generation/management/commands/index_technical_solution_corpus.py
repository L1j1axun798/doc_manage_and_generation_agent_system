from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.document_generation.technical_solution_corpus import (
    enqueue_technical_solution_corpus,
    scan_technical_solution_corpus,
)


class Command(BaseCommand):
    help = "扫描技术方案目录，并为尚未覆盖的可用章节生成RAG Embedding任务"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--approved-by", required=True, help="系统管理员用户名")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="实际创建并投递任务；省略时只执行预检",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(
                username=options["approved_by"],
                is_active=True,
            )
        except user_model.DoesNotExist as exc:
            raise CommandError("批准人不存在或已停用") from exc
        if not getattr(actor, "is_system_admin", False):
            raise CommandError("批准人必须是系统管理员")

        plans = scan_technical_solution_corpus()
        queueable = [plan for plan in plans if plan.should_queue]
        for plan in queueable:
            self.stdout.write(
                "QUEUE version={version_id} chunks≈{chunks} sections={sections} "
                "empty={empty} file={filename}".format(
                    version_id=plan.version_id,
                    chunks=plan.estimated_chunk_count,
                    sections=",".join(plan.section_codes),
                    empty=",".join(plan.empty_section_codes) or "-",
                    filename=plan.filename,
                )
            )
        for plan in plans:
            if plan.should_queue:
                continue
            self.stdout.write(
                f"SKIP version={plan.version_id} reason={plan.skip_reason} file={plan.filename}"
            )

        created = (
            enqueue_technical_solution_corpus(actor=actor, plans=plans)
            if options["execute"]
            else []
        )
        self.stdout.write(
            self.style.SUCCESS(
                "execute={execute} scanned={scanned} queueable={queueable} "
                "estimated_chunks={estimated_chunks} created={created}".format(
                    execute=options["execute"],
                    scanned=len(plans),
                    queueable=len(queueable),
                    estimated_chunks=sum(plan.estimated_chunk_count for plan in queueable),
                    created=len(created),
                )
            )
        )
