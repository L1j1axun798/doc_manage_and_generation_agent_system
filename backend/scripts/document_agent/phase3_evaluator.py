from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402
import environ  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from apps.document_generation.engine.contracts import (  # noqa: E402
    KnowledgeSectionInput,
    ParsedBlock,
    ParsedBlockType,
    RetrievalQuery,
    SourceDocument,
)
from apps.document_generation.engine.fakes import HashingEmbeddingProvider  # noqa: E402
from apps.document_generation.engine.parsing import EntrySourceParser  # noqa: E402
from apps.document_generation.engine.rag import (  # noqa: E402
    InMemoryKnowledgeRepository,
    KnowledgeIndexer,
    RagRetriever,
    SectionChunker,
    calculate_hit_at_k,
)
from apps.document_generation.providers.embedding import (  # noqa: E402
    OpenAICompatibleEmbeddingProvider,
)
from apps.documents.models import DocumentVersion  # noqa: E402

BUSINESS_TYPE = "wind_turbine_inspection_four_measures_two_plans"


@dataclass(frozen=True)
class EvaluationRecord:
    annotation_id: str
    section_code: str
    heading_text: str
    blocks: tuple[ParsedBlock, ...]
    body_excerpt: str
    relevant_chunk_ids: frozenset[str]


def _default_annotations_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "document_agent"
        / "phase0"
        / "section_annotations.csv"
    )


def _read_approved_annotations(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("review_status") == "approved"]


def _source_path(storage_path: str) -> Path:
    storage_root = Path(settings.FILE_STORAGE_ROOT).resolve()
    path = (storage_root / storage_path).resolve()
    try:
        path.relative_to(storage_root)
    except ValueError as exc:
        raise ValueError("document storage path escapes FILE_STORAGE_ROOT") from exc
    return path


def _blocks_in_range(
    blocks: tuple[ParsedBlock, ...],
    *,
    paragraph_start: int,
    paragraph_end: int,
) -> tuple[ParsedBlock, ...]:
    return tuple(
        block
        for block in blocks
        if block.locator.paragraph_index is not None
        and paragraph_start <= block.locator.paragraph_index <= paragraph_end
    )


def evaluate(
    *,
    annotations_path: Path,
    dimension: int,
    minimum_hit_at_3: float,
    embedding_provider_mode: str = "hashing",
    output_index: Path | None = None,
    overwrite: bool = False,
) -> int:
    annotations = _read_approved_annotations(annotations_path)
    version_ids = sorted({int(row["document_version_id"]) for row in annotations})
    versions = {
        item.id: item
        for item in DocumentVersion.objects.select_related("document").filter(id__in=version_ids)
    }
    missing_version_ids = sorted(set(version_ids) - set(versions))
    if missing_version_ids:
        print(f"[FAIL] missing DocumentVersion IDs: {missing_version_ids}")
        return 1

    parser = EntrySourceParser()
    parsed_documents = {}
    for version_id in version_ids:
        version = versions[version_id]
        content = _source_path(version.storage_path).read_bytes()
        parsed = parser.parse(
            SourceDocument(
                document_version_id=version_id,
                filename=version.original_filename,
                mime_type=(
                    version.content_type
                    or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ),
                content=content,
            )
        )
        if parsed.content_sha256 != version.sha256.lower():
            print(f"[FAIL] SHA-256 mismatch for DocumentVersion {version_id}")
            return 1
        parsed_documents[version_id] = parsed

    provider = (
        OpenAICompatibleEmbeddingProvider.from_env()
        if embedding_provider_mode == "real"
        else HashingEmbeddingProvider(dimension=dimension)
    )
    repository = InMemoryKnowledgeRepository()
    indexer = KnowledgeIndexer(
        chunker=SectionChunker(),
        embedding_provider=provider,
        repository=repository,
    )
    staged_records: list[tuple[dict[str, str], tuple[ParsedBlock, ...], str, frozenset[str]]] = []
    skipped_empty = 0
    for annotation in annotations:
        version_id = int(annotation["document_version_id"])
        blocks = _blocks_in_range(
            parsed_documents[version_id].blocks,
            paragraph_start=int(annotation["paragraph_start"]),
            paragraph_end=int(annotation["paragraph_end"]),
        )
        body = tuple(block for block in blocks if block.block_type != ParsedBlockType.HEADING)
        if not body:
            skipped_empty += 1
            continue
        chunks = indexer.index(
            KnowledgeSectionInput(
                source_document_version_id=version_id,
                business_type=BUSINESS_TYPE,
                section_code=annotation["section_code"],
                blocks=blocks,
                approval_status="approved",
            )
        )
        staged_records.append(
            (
                annotation,
                blocks,
                body[0].text[:500],
                frozenset(chunk.chunk_id for chunk in chunks),
            )
        )

    stored_chunks = {chunk.chunk_id: chunk for chunk in repository.all()}
    records: list[EvaluationRecord] = []
    skipped_duplicate = 0
    for annotation, blocks, body_excerpt, chunk_ids in staged_records:
        relevant_chunk_ids = frozenset(chunk_ids & stored_chunks.keys())
        if not relevant_chunk_ids:
            skipped_duplicate += 1
            continue
        records.append(
            EvaluationRecord(
                annotation_id=annotation["annotation_id"],
                section_code=annotation["section_code"],
                heading_text=annotation["heading_text"],
                blocks=blocks,
                body_excerpt=body_excerpt,
                relevant_chunk_ids=relevant_chunk_ids,
            )
        )

    retriever = RagRetriever(
        repository=repository,
        embedding_provider=provider,
    )
    cases = []
    misses: list[tuple[str, str]] = []
    trace_complete = True
    cross_business = False
    for record in records:
        result = retriever.retrieve(
            RetrievalQuery(
                business_type=BUSINESS_TYPE,
                section_code=record.section_code,
                query_text=f"{record.heading_text}\n{record.body_excerpt}",
                top_k=3,
            )
        )
        cases.append((result, set(record.relevant_chunk_ids)))
        returned_ids = {section.chunk_id for section in result.sections}
        if not returned_ids & record.relevant_chunk_ids:
            misses.append((record.annotation_id, record.section_code))
        trace_complete = (
            trace_complete
            and bool(result.trace)
            and all(
                item.source_document_version_id > 0 and bool(item.chunk_id) for item in result.trace
            )
            and all(
                bool(section.heading_path) and section.source_document_version_id > 0
                for section in result.sections
            )
        )
        cross_business = cross_business or any(
            stored_chunks[chunk_id].business_type != BUSINESS_TYPE for chunk_id in returned_ids
        )

    hit_at_3 = calculate_hit_at_k(cases, k=3)
    passed = bool(cases) and hit_at_3 >= minimum_hit_at_3 and trace_complete and not cross_business
    status = "PASS" if passed else "FAIL"
    print(
        f"[{status}] Phase 3 evaluation: documents={len(version_ids)}, "
        f"annotations={len(annotations)}, evaluated={len(cases)}, "
        f"skipped_empty={skipped_empty}, skipped_duplicate={skipped_duplicate}, "
        f"unique_chunks={len(stored_chunks)}, hit_at_3={hit_at_3:.3f}, "
        f"trace_complete={trace_complete}, cross_business={cross_business}"
    )
    if misses:
        print(
            "[INFO] misses="
            + ",".join(f"{annotation_id}:{section_code}" for annotation_id, section_code in misses)
        )
    if passed and output_index is not None:
        if output_index.exists() and not overwrite:
            print(f"[FAIL] knowledge index already exists: {output_index}")
            return 1
        output_index.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_index.with_suffix(output_index.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [chunk.model_dump(mode="json") for chunk in repository.all()],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(output_index)
        print(f"[PASS] knowledge index written: {output_index}")
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 3 RAG against approved Phase 0 annotations."
    )
    parser.add_argument(
        "--annotations-path",
        type=Path,
        default=_default_annotations_path(),
    )
    parser.add_argument("--dimension", type=int, default=1024)
    parser.add_argument(
        "--embedding-provider",
        choices=("hashing", "real"),
        default="hashing",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_ROOT / ".env",
        help="Environment file used when --embedding-provider=real.",
    )
    parser.add_argument("--minimum-hit-at-3", type=float, default=0.80)
    parser.add_argument("--output-index", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.dimension <= 0:
        parser.error("--dimension must be greater than zero")
    if not 0 <= args.minimum_hit_at_3 <= 1:
        parser.error("--minimum-hit-at-3 must be between zero and one")
    if args.embedding_provider == "real":
        env_file = args.env_file.resolve()
        if not env_file.is_file():
            parser.error(f"--env-file does not exist: {env_file}")
        environ.Env.read_env(env_file, overwrite=False)
    return evaluate(
        annotations_path=args.annotations_path.resolve(),
        dimension=args.dimension,
        minimum_hit_at_3=args.minimum_hit_at_3,
        embedding_provider_mode=args.embedding_provider,
        output_index=args.output_index.resolve() if args.output_index else None,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    sys.exit(main())
