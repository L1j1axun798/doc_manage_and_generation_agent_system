from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from apps.document_generation.engine.contracts import ENTRY_PLAN_SECTION_CODES  # noqa: E402
from scripts.document_agent.fingerprints import (  # noqa: E402
    compute_implementation_fingerprint,
)

MIN_BLIND_CASES = 3
MIN_HIT_AT_3 = 0.80
MIN_MINOR_EDIT_RATIO = 0.70
MIN_TIME_REDUCTION = 0.50
MIN_USABILITY_SCORE = 4.0
MIN_MINOR_EDIT_SCORE = 4
SCORE_FIELDS = (
    "factual_accuracy",
    "source_traceability",
    "clause_correctness",
    "safety_technical_completeness",
    "current_project_consistency",
    "professional_usability",
    "manual_editing_effort",
)


@dataclass(frozen=True)
class EvaluationCase:
    evaluation_version: str
    blind_case_id: str
    answer_sample_id: str
    input_json_path: str
    output_directory: str
    input_bundle_status: str
    generation_provider: str
    generation_status: str
    review_status: str


@dataclass(frozen=True)
class ScoreRow:
    evaluation_version: str
    blind_case_id: str
    section_code: str
    reviewer: str
    reviewed_at: str
    scores: Mapping[str, int]
    major_fabricated_fact: bool
    major_safety_or_technical_omission: bool
    all_numbers_have_sources: bool
    historical_entity_contamination: bool
    rag_hit_at_3: bool
    changed_character_ratio: float
    baseline_minutes: float | None
    agent_assisted_minutes: float | None


def _required(row: Mapping[str, str], field: str) -> str:
    value = row.get(field, "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _boolean(row: Mapping[str, str], field: str) -> bool:
    value = _required(row, field).lower()
    if value in {"true", "yes", "1"}:
        return True
    if value in {"false", "no", "0"}:
        return False
    raise ValueError(f"{field} must be true/false, yes/no, or 1/0")


def _score(row: Mapping[str, str], field: str) -> int:
    value = int(_required(row, field))
    if not 1 <= value <= 5:
        raise ValueError(f"{field} must be between 1 and 5")
    return value


def _ratio(row: Mapping[str, str], field: str) -> float:
    value = float(_required(row, field))
    if not 0 <= value <= 1:
        raise ValueError(f"{field} must be between 0 and 1")
    return value


def _minutes(row: Mapping[str, str], field: str) -> float:
    value = float(_required(row, field))
    if value <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return value


def _optional_minutes(row: Mapping[str, str], field: str) -> float | None:
    if not row.get(field, "").strip():
        return None
    return _minutes(row, field)


def _read_csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    encoded = path.read_bytes()
    try:
        text = encoded.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = encoded.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path.name} must use UTF-8 or GB18030 encoding") from exc
    with io.StringIO(text, newline="") as source:
        return tuple(csv.DictReader(source))


def load_cases(path: Path) -> tuple[EvaluationCase, ...]:
    rows = _read_csv_rows(path)
    return tuple(
        EvaluationCase(
            evaluation_version=_required(row, "evaluation_version"),
            blind_case_id=_required(row, "blind_case_id"),
            answer_sample_id=_required(row, "answer_sample_id"),
            input_json_path=row.get("input_json_path", "").strip(),
            output_directory=row.get("output_directory", "").strip(),
            input_bundle_status=_required(row, "input_bundle_status"),
            generation_provider=row.get("generation_provider", "").strip(),
            generation_status=_required(row, "generation_status"),
            review_status=_required(row, "review_status"),
        )
        for row in rows
    )


def load_scorecard(
    path: Path,
    *,
    time_gate_waived: bool = False,
) -> tuple[ScoreRow, ...]:
    rows = _read_csv_rows(path)
    return tuple(
        ScoreRow(
            evaluation_version=_required(row, "evaluation_version"),
            blind_case_id=_required(row, "blind_case_id"),
            section_code=_required(row, "section_code"),
            reviewer=_required(row, "reviewer"),
            reviewed_at=_required(row, "reviewed_at"),
            scores={field: _score(row, field) for field in SCORE_FIELDS},
            major_fabricated_fact=_boolean(row, "major_fabricated_fact"),
            major_safety_or_technical_omission=_boolean(
                row,
                "major_safety_or_technical_omission",
            ),
            all_numbers_have_sources=_boolean(row, "all_numbers_have_sources"),
            historical_entity_contamination=_boolean(
                row,
                "historical_entity_contamination",
            ),
            rag_hit_at_3=_boolean(row, "rag_hit_at_3"),
            changed_character_ratio=_ratio(row, "changed_character_ratio"),
            baseline_minutes=(
                _optional_minutes(row, "baseline_minutes")
                if time_gate_waived
                else _minutes(row, "baseline_minutes")
            ),
            agent_assisted_minutes=(
                _optional_minutes(row, "agent_assisted_minutes")
                if time_gate_waived
                else _minutes(row, "agent_assisted_minutes")
            ),
        )
        for row in rows
    )


def _load_validation(case: EvaluationCase, repository_root: Path) -> Mapping[str, Any]:
    output_directory = _resolve(repository_root, case.output_directory)
    path = output_directory / "validation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{case.blind_case_id} validation.json must contain an object")
    return payload


def _load_review_bundle(case: EvaluationCase, repository_root: Path) -> Mapping[str, Any]:
    output_directory = _resolve(repository_root, case.output_directory)
    path = output_directory / "review_bundle.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{case.blind_case_id} review_bundle.json must contain an object")
    return payload


def _review_sections(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    sections = payload.get("sections")
    if not isinstance(sections, list):
        raise ValueError("review bundle must contain a sections list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for section in sections:
        if not isinstance(section, Mapping):
            raise ValueError("review bundle section must be an object")
        section_code = section.get("section_code")
        if not isinstance(section_code, str) or not section_code:
            raise ValueError("review bundle section_code is required")
        if section_code in indexed:
            raise ValueError("review bundle section_code must be unique")
        indexed[section_code] = section
    return indexed


def _case_time(rows: Sequence[ScoreRow]) -> tuple[float, float] | None:
    baselines = {row.baseline_minutes for row in rows}
    assisted = {row.agent_assisted_minutes for row in rows}
    if len(baselines) != 1 or len(assisted) != 1:
        raise ValueError("project timing must be identical on every section row")
    baseline = next(iter(baselines))
    agent_assisted = next(iter(assisted))
    if baseline is None and agent_assisted is None:
        return None
    if baseline is None or agent_assisted is None:
        raise ValueError("project timing must provide both values or neither")
    return baseline, agent_assisted


def _resolve(repository_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repository_root / path


def _input_source_version_ids(case: EvaluationCase, repository_root: Path) -> set[int]:
    path = _resolve(repository_root, case.input_json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list) or not sources:
        raise ValueError("input JSON must contain a non-empty sources list")
    version_ids: set[int] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each input source must be an object")
        version_id = source.get("document_version_id")
        if not isinstance(version_id, int) or version_id <= 0:
            raise ValueError("source document_version_id must be a positive integer")
        version_ids.add(version_id)
    return version_ids


def load_blind_answer_version_ids(repository_root: Path) -> set[int]:
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


def load_expected_blind_case_samples(repository_root: Path) -> dict[str, str]:
    path = repository_root / "docs" / "document_agent" / "phase0" / "blind_test_set.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        return {
            row["blind_case_id"]: row["sample_id"]
            for row in csv.DictReader(source)
            if row["approval_status"] == "approved"
        }


def evaluate_phase5(
    cases: Sequence[EvaluationCase],
    score_rows: Sequence[ScoreRow],
    *,
    repository_root: Path,
    blind_answer_version_ids: set[int] | None = None,
    expected_blind_case_samples: Mapping[str, str] | None = None,
    time_gate_waived: bool = False,
) -> dict[str, Any]:
    issues: list[str] = []
    current_implementation_fingerprint = compute_implementation_fingerprint()
    blind_answer_version_ids = blind_answer_version_ids or set()
    case_ids = [case.blind_case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        issues.append("DUPLICATE_BLIND_CASE_ID")
    registered_case_samples = {case.blind_case_id: case.answer_sample_id for case in cases}
    if (
        expected_blind_case_samples is not None
        and registered_case_samples != expected_blind_case_samples
    ):
        issues.append("BLIND_CASE_REGISTRY_MISMATCH")

    selected_cases = [case for case in cases if case.input_bundle_status == "ready"]
    selected_case_ids = {case.blind_case_id for case in selected_cases}
    for case in selected_cases:
        if not case.input_json_path:
            issues.append(f"INPUT_JSON_PATH_MISSING:{case.blind_case_id}")
            continue
        try:
            source_version_ids = _input_source_version_ids(case, repository_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"INPUT_JSON_INVALID:{case.blind_case_id}:{type(exc).__name__}")
            continue
        if source_version_ids & blind_answer_version_ids:
            issues.append(f"BLIND_ANSWER_USED_AS_INPUT:{case.blind_case_id}")
        if case.generation_status != "completed":
            issues.append(f"GENERATION_NOT_COMPLETED:{case.blind_case_id}")
        if case.review_status != "completed":
            issues.append(f"REVIEW_NOT_COMPLETED:{case.blind_case_id}")

    completed_cases = [
        case
        for case in selected_cases
        if case.generation_status == "completed" and case.review_status == "completed"
    ]
    rows_by_case: dict[str, list[ScoreRow]] = defaultdict(list)
    for row in score_rows:
        rows_by_case[row.blind_case_id].append(row)
        if row.blind_case_id not in registered_case_samples:
            issues.append(f"UNREGISTERED_SCORE_CASE:{row.blind_case_id}")
        elif row.blind_case_id not in selected_case_ids:
            issues.append(f"SCORE_FOR_UNSELECTED_CASE:{row.blind_case_id}")

    evaluated_cases = [case for case in completed_cases if case.blind_case_id in rows_by_case]
    if len(evaluated_cases) < MIN_BLIND_CASES:
        issues.append(f"INSUFFICIENT_EVALUATED_CASES:{len(evaluated_cases)}/{MIN_BLIND_CASES}")

    accepted_rows: list[ScoreRow] = []
    total_baseline = 0.0
    total_assisted = 0.0
    validation_case_count = 0
    for case in evaluated_cases:
        rows = rows_by_case[case.blind_case_id]
        if any(row.evaluation_version != case.evaluation_version for row in rows):
            issues.append(f"EVALUATION_VERSION_MISMATCH:{case.blind_case_id}")
        section_codes = [row.section_code for row in rows]
        if len(section_codes) != len(set(section_codes)):
            issues.append(f"DUPLICATE_SECTION_SCORE:{case.blind_case_id}")
            continue
        if tuple(section_codes) != ENTRY_PLAN_SECTION_CODES:
            missing = sorted(set(ENTRY_PLAN_SECTION_CODES) - set(section_codes))
            unexpected = sorted(set(section_codes) - set(ENTRY_PLAN_SECTION_CODES))
            issues.append(
                f"SECTION_SCORE_SET_INVALID:{case.blind_case_id}:"
                f"missing={','.join(missing) or '-'}:"
                f"unexpected={','.join(unexpected) or '-'}"
            )
            continue
        if case.generation_provider.lower() != "real":
            issues.append(f"REAL_PROVIDER_REQUIRED:{case.blind_case_id}")
        output_directory = _resolve(repository_root, case.output_directory)
        for filename in ("entry_plan.docx", "trace.json", "validation.json", "review_bundle.json"):
            if not (output_directory / filename).is_file():
                issues.append(f"OUTPUT_MISSING:{case.blind_case_id}:{filename}")
        try:
            validation = _load_validation(case, repository_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"VALIDATION_UNAVAILABLE:{case.blind_case_id}:{type(exc).__name__}")
            continue
        validation_case_count += 1
        if validation.get("valid") is not True:
            issues.append(f"DETERMINISTIC_VALIDATION_FAILED:{case.blind_case_id}")
        if validation.get("fact_citation_coverage") != 1.0:
            issues.append(f"FACT_CITATION_COVERAGE_FAILED:{case.blind_case_id}")
        model_usage = validation.get("model_usage")
        if not isinstance(model_usage, list) or not model_usage:
            issues.append(f"REAL_MODEL_USAGE_MISSING:{case.blind_case_id}")
        elif any(
            not isinstance(record, Mapping)
            or str(record.get("model_alias", "")).lower().startswith("fake")
            for record in model_usage
        ):
            issues.append(f"REAL_MODEL_USAGE_INVALID:{case.blind_case_id}")
        try:
            review_bundle = _load_review_bundle(case, repository_root)
            review_sections = _review_sections(review_bundle)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"REVIEW_BUNDLE_UNAVAILABLE:{case.blind_case_id}:{type(exc).__name__}")
            continue
        if review_bundle.get("implementation_fingerprint") != current_implementation_fingerprint:
            issues.append(f"IMPLEMENTATION_FINGERPRINT_MISMATCH:{case.blind_case_id}")
        if tuple(review_sections) != ENTRY_PLAN_SECTION_CODES:
            issues.append(f"REVIEW_SECTION_SET_INVALID:{case.blind_case_id}")
            continue
        for row in rows:
            references = review_sections[row.section_code].get("retrieved_references")
            if row.rag_hit_at_3 and (not isinstance(references, list) or not references):
                issues.append(f"RAG_HIT_WITHOUT_RETRIEVAL:{case.blind_case_id}:{row.section_code}")
        try:
            timing = _case_time(rows)
        except ValueError:
            issues.append(f"INCONSISTENT_PROJECT_TIMING:{case.blind_case_id}")
            continue
        if timing is None:
            if not time_gate_waived:
                issues.append(f"PROJECT_TIMING_MISSING:{case.blind_case_id}")
                continue
        elif not time_gate_waived:
            baseline, assisted = timing
            total_baseline += baseline
            total_assisted += assisted
        accepted_rows.extend(rows)

    if any(row.major_fabricated_fact for row in accepted_rows):
        issues.append("MAJOR_FABRICATED_FACT_PRESENT")
    if any(row.major_safety_or_technical_omission for row in accepted_rows):
        issues.append("MAJOR_SAFETY_OR_TECHNICAL_OMISSION_PRESENT")
    if any(not row.all_numbers_have_sources for row in accepted_rows):
        issues.append("UNSOURCED_PROJECT_NUMBER_PRESENT")
    if any(row.historical_entity_contamination for row in accepted_rows):
        issues.append("HISTORICAL_ENTITY_CONTAMINATION_PRESENT")

    row_count = len(accepted_rows)
    hit_at_3 = sum(row.rag_hit_at_3 for row in accepted_rows) / row_count if row_count else 0.0
    minor_edit_ratio = (
        sum(row.scores["manual_editing_effort"] >= MIN_MINOR_EDIT_SCORE for row in accepted_rows)
        / row_count
        if row_count
        else 0.0
    )
    usability_score = (
        sum(row.scores["professional_usability"] for row in accepted_rows) / row_count
        if row_count
        else 0.0
    )
    changed_character_ratio = (
        sum(row.changed_character_ratio for row in accepted_rows) / row_count if row_count else 0.0
    )
    time_reduction = (
        None
        if time_gate_waived
        else (1 - total_assisted / total_baseline if total_baseline > 0 else 0.0)
    )
    factual_error_section_count = sum(row.scores["factual_accuracy"] < 5 for row in accepted_rows)
    clause_error_section_count = sum(row.scores["clause_correctness"] < 5 for row in accepted_rows)
    if hit_at_3 < MIN_HIT_AT_3:
        issues.append(f"RAG_HIT_AT_3_BELOW_GATE:{hit_at_3:.3f}")
    if minor_edit_ratio < MIN_MINOR_EDIT_RATIO:
        issues.append(f"MINOR_EDIT_RATIO_BELOW_GATE:{minor_edit_ratio:.3f}")
    if usability_score < MIN_USABILITY_SCORE:
        issues.append(f"USABILITY_SCORE_BELOW_GATE:{usability_score:.3f}")
    if time_reduction is not None and time_reduction < MIN_TIME_REDUCTION:
        issues.append(f"TIME_REDUCTION_BELOW_GATE:{time_reduction:.3f}")

    return {
        "status": "passed" if not issues else "failed",
        "evaluated_case_count": len(evaluated_cases),
        "validation_case_count": validation_case_count,
        "evaluated_section_count": row_count,
        "rag_hit_at_3": round(hit_at_3, 6),
        "minor_edit_section_ratio": round(minor_edit_ratio, 6),
        "changed_character_ratio_average": round(changed_character_ratio, 6),
        "factual_error_section_count": factual_error_section_count,
        "clause_error_section_count": clause_error_section_count,
        "professional_usability_average": round(usability_score, 6),
        "time_reduction_ratio": (
            round(time_reduction, 6) if time_reduction is not None else None
        ),
        "time_gate_status": (
            "waived_by_project_owner" if time_gate_waived else "evaluated"
        ),
        "hard_gate_issue_count": len(issues),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Evaluate the Phase 5 blind test gate.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=repository_root / "docs" / "document_agent" / "phase5" / "evaluation_cases.csv",
    )
    parser.add_argument(
        "--scorecard",
        type=Path,
        default=repository_root / "docs" / "document_agent" / "phase5" / "evaluation_scorecard.csv",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--waive-time-gate",
        action="store_true",
        help=(
            "Apply an explicit project-owner waiver when baseline and "
            "Agent-assisted time cannot be estimated reliably."
        ),
    )
    args = parser.parse_args(argv)
    try:
        summary = evaluate_phase5(
            load_cases(args.cases),
            load_scorecard(
                args.scorecard,
                time_gate_waived=args.waive_time_gate,
            ),
            repository_root=repository_root,
            blind_answer_version_ids=load_blind_answer_version_ids(repository_root),
            expected_blind_case_samples=load_expected_blind_case_samples(repository_root),
            time_gate_waived=args.waive_time_gate,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "status": "failed",
            "hard_gate_issue_count": 1,
            "issues": [f"EVALUATION_INPUT_INVALID:{type(exc).__name__}:{exc}"],
        }
    encoded = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)
    if summary["status"] == "passed":
        print("[PASS] Phase 5 offline evaluation gate")
        return 0
    print("[BLOCKED] Phase 5 offline evaluation gate")
    return 2


if __name__ == "__main__":
    sys.exit(main())
