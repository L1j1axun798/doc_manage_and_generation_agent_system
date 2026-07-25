from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.document_generation.runtime import check_document_agent_runtime


class Command(BaseCommand):
    help = "检查Document Agent模板、条款、RAG、Redis及可选模型连通性"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--check-providers", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            result = check_document_agent_runtime(
                call_providers=options["check_providers"],
            )
        except Exception as exc:
            raise CommandError(f"{type(exc).__name__}: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(
                "templates={templates} clauses={clauses} knowledge={knowledge} "
                "queue={queue} redis={redis} llm={llm_model} "
                "embedding={embedding_model}/{embedding_dimension} "
                "provider_calls={provider_calls}".format(**result)
            )
        )
