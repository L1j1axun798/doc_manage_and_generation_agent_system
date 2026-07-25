from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.document_generation.bootstrap import (
    BootstrapPaths,
    bootstrap_document_agent,
)


def _repository_root() -> Path:
    return Path(settings.BASE_DIR).resolve().parent


class Command(BaseCommand):
    help = "导入并批准Document Agent模板、条款和RAG知识基线"

    def add_arguments(self, parser: Any) -> None:
        root = _repository_root()
        parser.add_argument("--approved-by", required=True, help="批准人用户名")
        parser.add_argument(
            "--template-inventory",
            type=Path,
            default=root / "docs/document_agent/phase0/template_inventory.csv",
        )
        parser.add_argument(
            "--clause-matrix",
            type=Path,
            default=root / "docs/document_agent/phase0/clause_applicability_matrix.csv",
        )
        parser.add_argument(
            "--clause-blocks",
            type=Path,
            default=root / "docs/document_agent/phase4/approved_clause_blocks.csv",
        )
        parser.add_argument(
            "--knowledge-index",
            type=Path,
            default=root / "docs/document_agent/private-evaluation/knowledge.json",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(username=options["approved_by"], is_active=True)
            result = bootstrap_document_agent(
                actor=actor,
                paths=BootstrapPaths(
                    template_inventory=options["template_inventory"].resolve(),
                    clause_matrix=options["clause_matrix"].resolve(),
                    clause_blocks=options["clause_blocks"].resolve(),
                    knowledge_index=options["knowledge_index"].resolve(),
                ),
                dry_run=options["dry_run"],
            )
        except (user_model.DoesNotExist, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "dry_run={dry_run} templates(created={templates_created},"
                "updated={templates_updated}) clauses(created={clauses_created},"
                "updated={clauses_updated}) knowledge(created={knowledge_created},"
                "updated={knowledge_updated})".format(**result.__dict__)
            )
        )
