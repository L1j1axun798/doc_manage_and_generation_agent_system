# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import BaseModel, ConfigDict, Field

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    GenerationRequest,
    ModelUsageRecord,
    RenderedArtifact,
    RetrievalQuery,
    RetrievalResult,
    SourceDocument,
    StoredArtifact,
    TemplateDocument,
)
from apps.document_generation.engine.errors import WorkflowExecutionError
from apps.document_generation.engine.fakes import (
    EmptySectionRetriever,
    FakeLLMProvider,
    HashingEmbeddingProvider,
)
from apps.document_generation.engine.orchestrator import GenerationOrchestrator
from apps.document_generation.engine.parsing import EntrySourceParser
from apps.document_generation.engine.ports import (
    EmbeddingProvider,
    LLMProvider,
    SectionRepository,
    SectionRetriever,
)
from apps.document_generation.engine.rag import (
    JsonKnowledgeRepository,
    RagRetriever,
)
from apps.document_generation.engine.rendering import DocxTemplateRenderer
from apps.document_generation.engine.rules import (
    ApprovedClauseRepository,
    DeterministicRiskProfiler,
)
from apps.document_generation.engine.sections import JsonSectionRepository
from apps.document_generation.engine.validation import (
    ControlledSectionValidator,
    fact_citation_coverage,
)
from apps.document_generation.providers.embedding import (
    OpenAICompatibleEmbeddingProvider,
)
from apps.document_generation.providers.llm import OpenAICompatibleLLMProvider
from scripts.document_agent.fingerprints import compute_implementation_fingerprint

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class OfflineSourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_version_id: int = Field(gt=0)
    path: str = Field(min_length=1)
    mime_type: str | None = None


class OfflineGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    business_type: Literal["wind_turbine_inspection_four_measures_two_plans"]
    template_id: str = Field(min_length=1)
    template_path: str = Field(min_length=1)
    template_required_placeholders: tuple[str, ...] = ()
    sources: tuple[OfflineSourceInput, ...] = Field(min_length=1)
    confirmed_facts: tuple[ConfirmedFact, ...]
    required_fact_fields: tuple[str, ...]
    section_codes: tuple[str, ...] = Field(min_length=1)
    historical_entity_blacklist: tuple[str, ...] = ()
    knowledge_json_path: str | None = None


class OfflineArtifactStorage:
    def __init__(self, output_dir: Path, *, overwrite: bool) -> None:
        self.output_dir = output_dir
        self.overwrite = overwrite

    def save(self, artifact: RenderedArtifact) -> StoredArtifact:
        path = self.output_dir / "entry_plan.docx"
        if path.exists() and not self.overwrite:
            raise FileExistsError(f"output already exists: {path}")
        temporary = path.with_suffix(".docx.tmp")
        temporary.write_bytes(artifact.content)
        temporary.replace(path)
        return StoredArtifact(
            artifact_id="offline:entry_plan.docx",
            filename=path.name,
            media_type=artifact.media_type,
            sha256=artifact.sha256,
        )


class RecordingRetriever:
    """Offline evaluation adapter that preserves retrieval evidence for review."""

    def __init__(self, delegate: SectionRetriever, *, state_path: Path) -> None:
        self.delegate = delegate
        self.state_path = state_path
        self.results: dict[str, RetrievalResult] = {}
        if state_path.is_file():
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("retrieval state must contain a JSON list")
            for item in payload:
                result = RetrievalResult.model_validate(item)
                self.results[result.query.section_code] = result

    @property
    def embedding_model_alias(self) -> str:
        return self.delegate.embedding_model_alias

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        cached = self.results.get(query.section_code)
        if cached is not None and cached.query == query:
            return cached
        result = self.delegate.retrieve(query)
        self.results[query.section_code] = result
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [
                    item.model_dump(mode="json")
                    for _, item in sorted(self.results.items())
                ],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
        return result


def _retrieval_query(
    request: GenerationRequest,
    section_code: str,
) -> RetrievalQuery:
    fact_text = " ".join(
        f"{fact.field} {fact.value}" for fact in request.confirmed_facts
    )
    return RetrievalQuery(
        business_type=request.business_type,
        section_code=section_code,
        query_text=f"{section_code} {fact_text}".strip(),
    )


def _merge_usage_state(
    path: Path,
    records: Sequence[ModelUsageRecord],
) -> tuple[ModelUsageRecord, ...]:
    existing: tuple[ModelUsageRecord, ...] = ()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("model usage state must contain a JSON list")
        existing = tuple(ModelUsageRecord.model_validate(item) for item in payload)
    combined = (*existing, *records)
    if records:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                [record.model_dump(mode="json") for record in combined],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)
    return combined


def _source_document(source: OfflineSourceInput) -> SourceDocument:
    path = Path(source.path).expanduser().resolve()
    suffix = path.suffix.lower()
    mime_type = source.mime_type
    if mime_type is None:
        if suffix == ".docx":
            mime_type = DOCX_MIME
        elif suffix == ".pdf":
            mime_type = "application/pdf"
        else:
            mime_type = "application/octet-stream"
    return SourceDocument(
        document_version_id=source.document_version_id,
        filename=path.name,
        mime_type=mime_type,
        content=path.read_bytes(),
    )


def _blind_answer_version_ids(repository_root: Path) -> set[int]:
    phase0_dir = repository_root / "docs" / "document_agent" / "phase0"
    with (phase0_dir / "blind_test_set.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as source:
        blind_sample_ids = {
            row["sample_id"]
            for row in csv.DictReader(source)
            if row["approval_status"] == "approved"
        }
    with (phase0_dir / "sample_inventory.csv").open(
        encoding="utf-8-sig",
        newline="",
    ) as source:
        return {
            int(row["document_version_id"])
            for row in csv.DictReader(source)
            if row["sample_id"] in blind_sample_ids
        }


def _template_document(payload: OfflineGenerationInput) -> TemplateDocument:
    path = Path(payload.template_path).expanduser().resolve()
    return TemplateDocument(
        template_id=payload.template_id,
        filename=path.name,
        content=path.read_bytes(),
        required_placeholders=payload.template_required_placeholders,
    )


def _retriever(
    payload: OfflineGenerationInput,
    *,
    state_path: Path,
) -> RecordingRetriever:
    if payload.knowledge_json_path is None:
        return RecordingRetriever(EmptySectionRetriever(), state_path=state_path)
    repository = JsonKnowledgeRepository(Path(payload.knowledge_json_path).expanduser().resolve())
    chunks = repository.all()
    if not chunks:
        return RecordingRetriever(EmptySectionRetriever(), state_path=state_path)
    aliases = {chunk.embedding_model_alias for chunk in chunks}
    dimensions = {chunk.embedding_dimension for chunk in chunks}
    if len(aliases) != 1 or len(dimensions) != 1:
        raise ValueError("knowledge index contains mixed embedding versions")
    alias = next(iter(aliases))
    dimension = next(iter(dimensions))
    embedding_provider: EmbeddingProvider
    if alias.startswith("hashing-fake-"):
        embedding_provider = HashingEmbeddingProvider(
            dimension=dimension,
            model_alias=alias,
        )
    else:
        embedding_provider = OpenAICompatibleEmbeddingProvider.from_env()
        if embedding_provider.model_alias != alias or embedding_provider.dimension != dimension:
            raise ValueError("knowledge index does not match configured embedding model")
    return RecordingRetriever(
        RagRetriever(
            repository=repository,
            embedding_provider=embedding_provider,
        ),
        state_path=state_path,
    )


def _validation_payload(
    *,
    request: GenerationRequest,
    repository: SectionRepository,
    usage_records: Sequence[ModelUsageRecord],
) -> Mapping[str, object]:
    section_results: list[Mapping[str, object]] = []
    sections = []
    has_errors = False
    for section_code in request.section_codes:
        persisted = repository.load(request.idempotency_key, section_code)
        if persisted is None:
            continue
        sections.append(persisted.section)
        has_errors = has_errors or any(
            issue.severity == "error" for issue in persisted.validation_issues
        )
        section_results.append(
            {
                "section_code": section_code,
                "revision": persisted.revision,
                "locked": persisted.locked,
                "issues": [issue.model_dump(mode="json") for issue in persisted.validation_issues],
            }
        )
    serialized_usage = [record.model_dump(mode="json") for record in usage_records]
    return {
        "valid": not has_errors,
        "fact_citation_coverage": fact_citation_coverage(
            sections,
            request.confirmed_facts,
        ),
        "sections": section_results,
        "model_usage": serialized_usage,
    }


def _review_payload(
    *,
    request: GenerationRequest,
    repository: SectionRepository,
    retriever: RecordingRetriever,
    usage_records: Sequence[ModelUsageRecord],
) -> Mapping[str, object]:
    sections: list[Mapping[str, object]] = []
    for section_code in request.section_codes:
        persisted = repository.load(request.idempotency_key, section_code)
        if persisted is None:
            continue
        retrieval = retriever.results.get(section_code)
        sections.append(
            {
                "section_code": section_code,
                "generated_section": persisted.section.model_dump(mode="json"),
                "validation_issues": [
                    issue.model_dump(mode="json") for issue in persisted.validation_issues
                ],
                "retrieval_query": (
                    retrieval.query.model_dump(mode="json") if retrieval is not None else None
                ),
                "retrieved_references": (
                    [item.model_dump(mode="json") for item in retrieval.sections]
                    if retrieval is not None
                    else []
                ),
                "retrieval_trace": (
                    [item.model_dump(mode="json") for item in retrieval.trace]
                    if retrieval is not None
                    else []
                ),
            }
        )
    return {
        "schema_version": "phase5-review-v1",
        "implementation_fingerprint": compute_implementation_fingerprint(),
        "request_id": request.request_id,
        "idempotency_key": request.idempotency_key,
        "section_codes": list(request.section_codes),
        "sections": sections,
        "model_usage": [
            record.model_dump(mode="json")
            for record in usage_records
        ],
    }


def run_offline(
    *,
    input_path: Path,
    output_dir: Path,
    provider_mode: Literal["fake", "real"],
    overwrite: bool = False,
    fresh: bool = False,
    env_file: Path | None = None,
) -> tuple[Path, Path, Path]:
    payload = OfflineGenerationInput.model_validate_json(input_path.read_text(encoding="utf-8"))
    repository_root = Path(__file__).resolve().parents[3]
    blind_version_ids = _blind_answer_version_ids(repository_root)
    leaked_version_ids = sorted(
        {
            source.document_version_id
            for source in payload.sources
            if source.document_version_id in blind_version_ids
        }
    )
    if leaked_version_ids:
        raise ValueError(
            "blind answer documents cannot be used as generation inputs: "
            + ",".join(str(version_id) for version_id in leaked_version_ids)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    target_paths = (
        output_dir / "entry_plan.docx",
        output_dir / "trace.json",
        output_dir / "validation.json",
    )
    review_bundle_path = output_dir / "review_bundle.json"
    if not overwrite and any(path.exists() for path in (*target_paths, review_bundle_path)):
        raise FileExistsError("one or more offline output files already exist")

    risk_profiler = DeterministicRiskProfiler.from_csv(
        repository_root / "docs" / "document_agent" / "phase0" / "risk_labels.csv"
    )
    clause_repository = ApprovedClauseRepository.from_csv(
        matrix_path=(
            repository_root
            / "docs"
            / "document_agent"
            / "phase0"
            / "clause_applicability_matrix.csv"
        ),
        clause_blocks_path=(
            repository_root / "docs" / "document_agent" / "phase4" / "approved_clause_blocks.csv"
        ),
    )
    llm_provider: LLMProvider
    if provider_mode == "real":
        import environ

        if env_file is not None and env_file.is_file():
            environ.Env.read_env(env_file, overwrite=False)
        llm_provider = OpenAICompatibleLLMProvider.from_env()
    else:
        llm_provider = FakeLLMProvider()
    section_state_path = output_dir / "section_state.json"
    usage_state_path = output_dir / "model_usage_state.json"
    retrieval_state_path = output_dir / "retrieval_state.json"
    if fresh:
        section_state_path.unlink(missing_ok=True)
        usage_state_path.unlink(missing_ok=True)
        retrieval_state_path.unlink(missing_ok=True)
    section_repository = JsonSectionRepository(section_state_path)
    request = GenerationRequest(
        request_id=payload.request_id,
        idempotency_key=payload.idempotency_key,
        business_type=payload.business_type,
        template=_template_document(payload),
        sources=tuple(_source_document(source) for source in payload.sources),
        confirmed_facts=payload.confirmed_facts,
        required_fact_fields=payload.required_fact_fields,
        section_codes=payload.section_codes,
    )
    retriever = _retriever(payload, state_path=retrieval_state_path)
    for section_code in request.section_codes:
        retriever.retrieve(_retrieval_query(request, section_code))
    orchestrator = GenerationOrchestrator(
        parser=EntrySourceParser(),
        llm_provider=llm_provider,
        risk_profiler=risk_profiler,
        clause_repository=clause_repository,
        retriever=retriever,
        section_validator=ControlledSectionValidator(
            historical_entity_blacklist=payload.historical_entity_blacklist
        ),
        renderer=DocxTemplateRenderer(),
        storage=OfflineArtifactStorage(output_dir, overwrite=overwrite),
        section_repository=section_repository,
    )
    failure_path = output_dir / "failure.json"
    try:
        result = orchestrator.run(request)
    except WorkflowExecutionError as exc:
        failure_usage = (
            tuple(llm_provider.usage_records)
            if isinstance(llm_provider, OpenAICompatibleLLMProvider)
            else ()
        )
        _merge_usage_state(usage_state_path, failure_usage)
        failure_path.write_text(
            json.dumps(
                {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "trace": exc.trace.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise
    failure_path.unlink(missing_ok=True)
    trace_path = output_dir / "trace.json"
    trace_path.write_text(
        result.trace.model_dump_json(indent=2),
        encoding="utf-8",
    )
    current_usage: Sequence[ModelUsageRecord] = (
        tuple(llm_provider.usage_records)
        if isinstance(llm_provider, OpenAICompatibleLLMProvider)
        else ()
    )
    usage_records = _merge_usage_state(usage_state_path, current_usage)
    validation_path = output_dir / "validation.json"
    validation_path.write_text(
        json.dumps(
            _validation_payload(
                request=request,
                repository=section_repository,
                usage_records=usage_records,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    review_bundle_path.write_text(
        json.dumps(
            _review_payload(
                request=request,
                repository=section_repository,
                retriever=retriever,
                usage_records=usage_records,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return target_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline entry-plan generation pipeline.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--provider",
        choices=("fake", "real"),
        default="fake",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Discard resumable section state after an intentional prompt or rule change.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=BACKEND_ROOT / ".env",
        help="Load provider variables without overriding existing process variables.",
    )
    args = parser.parse_args(argv)
    run_offline(
        input_path=args.input.resolve(),
        output_dir=args.output_dir.resolve(),
        provider_mode=args.provider,
        overwrite=args.overwrite,
        fresh=args.fresh,
        env_file=args.env_file.resolve() if args.env_file else None,
    )
    print(f"[PASS] Phase 5 offline outputs: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
