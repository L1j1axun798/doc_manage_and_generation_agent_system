from __future__ import annotations

import csv
import json

from apps.document_generation.engine.contracts import ENTRY_PLAN_SECTION_CODES
from scripts.document_agent.phase5_scorecard_builder import build_review_scorecard


def test_review_scorecard_builder_prefills_only_objective_review_context(tmp_path) -> None:
    output_directory = tmp_path / "output"
    output_directory.mkdir()
    (output_directory / "review_bundle.json").write_text(
        json.dumps(
            {
                "sections": [
                    {
                        "section_code": section_code,
                        "generated_section": {"title": section_code},
                        "retrieved_references": [{"chunk_id": "chunk-1"}],
                        "validation_issues": [],
                    }
                    for section_code in ENTRY_PLAN_SECTION_CODES
                ]
            }
        ),
        encoding="utf-8",
    )
    cases_path = tmp_path / "cases.csv"
    with cases_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=(
                "evaluation_version",
                "blind_case_id",
                "answer_sample_id",
                "input_json_path",
                "output_directory",
                "input_bundle_status",
                "generation_provider",
                "generation_status",
                "review_status",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "evaluation_version": "phase5-v1",
                "blind_case_id": "B001",
                "answer_sample_id": "S009",
                "input_json_path": "input.json",
                "output_directory": str(output_directory),
                "input_bundle_status": "ready",
                "generation_provider": "real",
                "generation_status": "completed",
                "review_status": "not_started",
            }
        )
    scorecard_path = tmp_path / "review.csv"

    count = build_review_scorecard(
        cases_path=cases_path,
        output_path=scorecard_path,
        repository_root=tmp_path,
    )

    with scorecard_path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert count == 8
    assert [row["section_code"] for row in rows] == list(ENTRY_PLAN_SECTION_CODES)
    assert rows[0]["retrieved_reference_count"] == "1"
    assert rows[0]["factual_accuracy"] == ""
    assert rows[0]["major_fabricated_fact"] == ""
    assert rows[0]["major_safety_or_technical_omission"] == ""
    assert rows[0]["all_numbers_have_sources"] == ""
    assert rows[0]["historical_entity_contamination"] == ""
