from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Mapping
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from apps.document_generation.engine.contracts import (  # noqa: E402
    ENTRY_PLAN_SECTION_CODES,
)
from scripts.document_agent.phase5_evaluator import load_cases  # noqa: E402

SCORECARD_FIELDS = (
    "evaluation_version",
    "blind_case_id",
    "section_code",
    "reviewer",
    "reviewed_at",
    "factual_accuracy",
    "source_traceability",
    "clause_correctness",
    "safety_technical_completeness",
    "current_project_consistency",
    "professional_usability",
    "manual_editing_effort",
    "major_fabricated_fact",
    "major_safety_or_technical_omission",
    "all_numbers_have_sources",
    "historical_entity_contamination",
    "rag_hit_at_3",
    "changed_character_ratio",
    "baseline_minutes",
    "agent_assisted_minutes",
    "review_comments",
    "generated_section_title",
    "retrieved_reference_count",
    "validation_error_count",
    "output_docx",
)


def _resolve(repository_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repository_root / path


def build_review_scorecard(
    *,
    cases_path: Path,
    output_path: Path,
    repository_root: Path,
) -> int:
    rows: list[dict[str, object]] = []
    for case in load_cases(cases_path):
        if case.input_bundle_status != "ready":
            continue
        output_directory = _resolve(repository_root, case.output_directory)
        bundle_path = output_directory / "review_bundle.json"
        if not bundle_path.is_file():
            raise ValueError(f"{case.blind_case_id} 缺少 review_bundle.json")
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        sections = payload.get("sections") if isinstance(payload, Mapping) else None
        if not isinstance(sections, list):
            raise ValueError(f"{case.blind_case_id} 的 review_bundle.json 结构无效")
        sections_by_code = {
            section.get("section_code"): section
            for section in sections
            if isinstance(section, Mapping)
        }
        if tuple(sections_by_code) != ENTRY_PLAN_SECTION_CODES:
            raise ValueError(f"{case.blind_case_id} 的评审章节不完整或顺序错误")
        for section_code in ENTRY_PLAN_SECTION_CODES:
            section = sections_by_code[section_code]
            generated = section.get("generated_section")
            references = section.get("retrieved_references")
            issues = section.get("validation_issues")
            error_count = sum(
                1
                for issue in issues
                if isinstance(issue, Mapping) and issue.get("severity") == "error"
            ) if isinstance(issues, list) else 0
            rows.append(
                {
                    "evaluation_version": case.evaluation_version,
                    "blind_case_id": case.blind_case_id,
                    "section_code": section_code,
                    "generated_section_title": (
                        generated.get("title", "") if isinstance(generated, Mapping) else ""
                    ),
                    "retrieved_reference_count": (
                        len(references) if isinstance(references, list) else 0
                    ),
                    "validation_error_count": error_count,
                    "output_docx": str(output_directory / "entry_plan.docx"),
                }
            )
    if not rows:
        raise ValueError("没有可生成评审表的 ready 案例")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=SCORECARD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Build the Phase 5 human review scorecard.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=repository_root / "docs/document_agent/phase5/evaluation_cases.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            repository_root
            / "docs/document_agent/phase5/private/evaluation_scorecard.review.csv"
        ),
    )
    args = parser.parse_args(argv)
    try:
        count = build_review_scorecard(
            cases_path=args.cases.resolve(),
            output_path=args.output.resolve(),
            repository_root=repository_root,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] Phase 5 review scorecard: {type(exc).__name__}: {exc}")
        return 1
    print(f"[PASS] Phase 5 review scorecard rows={count}: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
