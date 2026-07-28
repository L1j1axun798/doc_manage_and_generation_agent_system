from __future__ import annotations

import json
from pathlib import Path

from apps.document_generation.engine.contracts import ENTRY_PLAN_SECTION_CODES
from scripts.document_agent.fingerprints import compute_implementation_fingerprint
from scripts.document_agent.phase5_evaluator import (
    EvaluationCase,
    ScoreRow,
    evaluate_phase5,
    load_scorecard,
)


def _case(case_number: int, output_directory: Path) -> EvaluationCase:
    return EvaluationCase(
        evaluation_version="phase5-v1",
        blind_case_id=f"B{case_number:03d}",
        answer_sample_id=f"S{case_number + 8:03d}",
        input_json_path=f"case-{case_number}.json",
        output_directory=str(output_directory),
        input_bundle_status="ready",
        generation_provider="real",
        generation_status="completed",
        review_status="completed",
    )


def _score(case_number: int, section_code: str) -> ScoreRow:
    return ScoreRow(
        evaluation_version="phase5-v1",
        blind_case_id=f"B{case_number:03d}",
        section_code=section_code,
        reviewer="technical-owner",
        reviewed_at="2026-07-24T18:00:00+08:00",
        scores={
            "factual_accuracy": 5,
            "source_traceability": 5,
            "clause_correctness": 5,
            "safety_technical_completeness": 5,
            "current_project_consistency": 5,
            "professional_usability": 4,
            "manual_editing_effort": 4,
        },
        major_fabricated_fact=False,
        major_safety_or_technical_omission=False,
        all_numbers_have_sources=True,
        historical_entity_contamination=False,
        rag_hit_at_3=True,
        changed_character_ratio=0.1,
        baseline_minutes=120,
        agent_assisted_minutes=45,
    )


def _write_outputs(tmp_path: Path, case_number: int) -> Path:
    output_directory = tmp_path / f"case-{case_number}"
    output_directory.mkdir()
    (tmp_path / f"case-{case_number}.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "document_version_id": 1000 + case_number,
                        "path": f"current-input-{case_number}.docx",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (output_directory / "entry_plan.docx").write_bytes(b"test-docx")
    (output_directory / "trace.json").write_text(
        json.dumps({"llm_model_alias": "approved-real-model"}),
        encoding="utf-8",
    )
    (output_directory / "validation.json").write_text(
        json.dumps(
            {
                "valid": True,
                "fact_citation_coverage": 1.0,
                "model_usage": [{"model_alias": "approved-real-model"}],
            }
        ),
        encoding="utf-8",
    )
    (output_directory / "review_bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "phase5-review-v1",
                "implementation_fingerprint": compute_implementation_fingerprint(),
                "sections": [
                    {
                        "section_code": section_code,
                        "retrieved_references": [{"chunk_id": f"{section_code}:reference"}],
                    }
                    for section_code in ENTRY_PLAN_SECTION_CODES
                ],
            }
        ),
        encoding="utf-8",
    )
    return output_directory


def test_phase5_gate_rejects_stale_implementation_fingerprint(tmp_path) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        cases.append(_case(case_number, output_directory))
        scores.extend(
            _score(case_number, section_code) for section_code in ENTRY_PLAN_SECTION_CODES
        )
    review_path = Path(cases[0].output_directory) / "review_bundle.json"
    review_bundle = json.loads(review_path.read_text(encoding="utf-8"))
    review_bundle["implementation_fingerprint"] = "0" * 64
    review_path.write_text(json.dumps(review_bundle), encoding="utf-8")

    summary = evaluate_phase5(cases, scores, repository_root=tmp_path)

    assert "IMPLEMENTATION_FINGERPRINT_MISMATCH:B001" in summary["issues"]


def test_phase5_gate_passes_three_real_reviewed_cases_and_ignores_unselected(
    tmp_path: Path,
) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        cases.append(_case(case_number, output_directory))
        scores.extend(
            _score(case_number, section_code) for section_code in ENTRY_PLAN_SECTION_CODES
        )
    for case_number in range(4, 9):
        cases.append(
            EvaluationCase(
                evaluation_version="phase5-v1",
                blind_case_id=f"B{case_number:03d}",
                answer_sample_id=f"S{case_number + 8:03d}",
                input_json_path="",
                output_directory="",
                input_bundle_status="awaiting_input",
                generation_provider="",
                generation_status="not_started",
                review_status="not_started",
            )
        )

    summary = evaluate_phase5(cases, scores, repository_root=tmp_path)

    assert summary["status"] == "passed"
    assert summary["evaluated_case_count"] == 3
    assert summary["evaluated_section_count"] == 24
    assert summary["time_reduction_ratio"] == 0.625


def test_phase5_gate_rejects_incomplete_section_score_set(tmp_path) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        cases.append(_case(case_number, output_directory))
        section_codes = (
            ENTRY_PLAN_SECTION_CODES[:-1] if case_number == 1 else ENTRY_PLAN_SECTION_CODES
        )
        scores.extend(_score(case_number, section_code) for section_code in section_codes)

    summary = evaluate_phase5(cases, scores, repository_root=tmp_path)

    assert summary["status"] == "failed"
    assert any(issue.startswith("SECTION_SCORE_SET_INVALID:B001") for issue in summary["issues"])


def test_phase5_gate_rejects_rag_hit_without_retrieval_evidence(tmp_path) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        if case_number == 1:
            review_bundle = json.loads(
                (output_directory / "review_bundle.json").read_text(encoding="utf-8")
            )
            review_bundle["sections"][0]["retrieved_references"] = []
            (output_directory / "review_bundle.json").write_text(
                json.dumps(review_bundle),
                encoding="utf-8",
            )
        cases.append(_case(case_number, output_directory))
        scores.extend(
            _score(case_number, section_code) for section_code in ENTRY_PLAN_SECTION_CODES
        )

    summary = evaluate_phase5(cases, scores, repository_root=tmp_path)

    assert "RAG_HIT_WITHOUT_RETRIEVAL:B001:overview" in summary["issues"]


def test_phase5_gate_passes_three_real_reviewed_cases(tmp_path) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        cases.append(_case(case_number, output_directory))
        scores.extend(
            _score(case_number, section_code) for section_code in ENTRY_PLAN_SECTION_CODES
        )

    summary = evaluate_phase5(cases, scores, repository_root=tmp_path)

    assert summary["status"] == "passed"
    assert summary["evaluated_case_count"] == 3
    assert summary["time_reduction_ratio"] == 0.625
    assert summary["time_gate_status"] == "evaluated"


def test_phase5_gate_allows_explicit_project_owner_time_waiver(tmp_path) -> None:
    cases = []
    scores = []
    for case_number in range(1, 4):
        output_directory = _write_outputs(tmp_path, case_number)
        cases.append(_case(case_number, output_directory))
        for section_code in ENTRY_PLAN_SECTION_CODES:
            score = _score(case_number, section_code)
            scores.append(
                ScoreRow(
                    **{
                        **score.__dict__,
                        "baseline_minutes": None,
                        "agent_assisted_minutes": None,
                    }
                )
            )

    summary = evaluate_phase5(
        cases,
        scores,
        repository_root=tmp_path,
        time_gate_waived=True,
    )

    assert summary["status"] == "passed"
    assert summary["time_reduction_ratio"] is None
    assert summary["time_gate_status"] == "waived_by_project_owner"


def test_phase5_gate_rejects_incomplete_or_fake_evaluation(tmp_path) -> None:
    (tmp_path / "case-1.json").write_text(
        json.dumps({"sources": [{"document_version_id": 1001, "path": "input.docx"}]}),
        encoding="utf-8",
    )
    case = _case(1, tmp_path)
    case = EvaluationCase(
        **{
            **case.__dict__,
            "generation_provider": "fake",
        }
    )

    score_rows = tuple(_score(1, section_code) for section_code in ENTRY_PLAN_SECTION_CODES)
    summary = evaluate_phase5((case,), score_rows, repository_root=tmp_path)

    assert summary["status"] == "failed"
    assert "INSUFFICIENT_EVALUATED_CASES:1/3" in summary["issues"]
    assert "REAL_PROVIDER_REQUIRED:B001" in summary["issues"]


def test_phase5_gate_rejects_blind_answer_as_generation_input(tmp_path) -> None:
    output_directory = tmp_path / "case-1"
    output_directory.mkdir()
    (tmp_path / "case-1.json").write_text(
        json.dumps({"sources": [{"document_version_id": 180, "path": "answer.docx"}]}),
        encoding="utf-8",
    )

    summary = evaluate_phase5(
        (_case(1, output_directory),),
        tuple(_score(1, section_code) for section_code in ENTRY_PLAN_SECTION_CODES),
        repository_root=tmp_path,
        blind_answer_version_ids={180},
    )

    assert "BLIND_ANSWER_USED_AS_INPUT:B001" in summary["issues"]


def test_load_scorecard_accepts_excel_gb18030_csv(tmp_path) -> None:
    path = tmp_path / "evaluation_scorecard.review.csv"
    headers = (
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
    )
    row = (
        "phase5-v1",
        "B001",
        "overview",
        "技术负责人",
        "2026-07-26 10:00",
        "5",
        "5",
        "5",
        "5",
        "5",
        "4",
        "4",
        "false",
        "false",
        "true",
        "false",
        "true",
        "0.1",
        "120",
        "45",
    )
    path.write_bytes((",".join(headers) + "\r\n" + ",".join(row) + "\r\n").encode("gb18030"))

    scorecard = load_scorecard(path)

    assert len(scorecard) == 1
    assert scorecard[0].reviewer == "技术负责人"


def test_load_scorecard_allows_blank_timing_only_with_explicit_waiver(tmp_path) -> None:
    path = tmp_path / "evaluation_scorecard.review.csv"
    path.write_text(
        (
            "evaluation_version,blind_case_id,section_code,reviewer,reviewed_at,"
            "factual_accuracy,source_traceability,clause_correctness,"
            "safety_technical_completeness,current_project_consistency,"
            "professional_usability,manual_editing_effort,major_fabricated_fact,"
            "major_safety_or_technical_omission,all_numbers_have_sources,"
            "historical_entity_contamination,rag_hit_at_3,changed_character_ratio,"
            "baseline_minutes,agent_assisted_minutes\r\n"
            "phase5-v2,B001,overview,lee,2026-07-26 18:30,5,5,5,5,5,4,4,"
            "false,false,true,false,true,0.3,,\r\n"
        ),
        encoding="utf-8",
    )

    scorecard = load_scorecard(path, time_gate_waived=True)

    assert scorecard[0].baseline_minutes is None
    assert scorecard[0].agent_assisted_minutes is None
