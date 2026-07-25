from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.document_agent.phase0_validator import (
    REQUIRED_CSV_HEADERS,
    REQUIRED_MODEL_CAPABILITIES,
    REQUIRED_SCORE_CRITERIA,
    REQUIRED_SIGNOFFS,
    validate_development_gate,
    validate_gate,
    validate_structure,
)


def _write_empty_phase0_fixture(base_dir: Path) -> None:
    base_dir.mkdir(parents=True)
    (base_dir / "README.md").write_text("# Phase 0 fixture\n", encoding="utf-8")
    (base_dir / "phase0_manifest.json").write_text(
        json.dumps(
            {
                "phase": 0,
                "status": "draft",
                "target_document_family": "fixture",
            }
        ),
        encoding="utf-8",
    )
    for filename, headers in REQUIRED_CSV_HEADERS.items():
        with (base_dir / filename).open("w", encoding="utf-8", newline="") as target:
            csv.writer(target).writerow(headers)


def _write_rows(base_dir: Path, filename: str, rows: list[dict[str, str]]) -> None:
    headers = REQUIRED_CSV_HEADERS[filename]
    with (base_dir / filename).open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=headers)
        writer.writeheader()
        writer.writerows({header: row.get(header, "") for header in headers} for row in rows)


def _complete_phase0_fixture(base_dir: Path) -> None:
    _write_empty_phase0_fixture(base_dir)
    (base_dir / "phase0_manifest.json").write_text(
        json.dumps(
            {
                "phase": 0,
                "status": "approved",
                "target_document_family": "fixture",
                "selected_business_type_code": "business_a",
            }
        ),
        encoding="utf-8",
    )
    _write_rows(
        base_dir,
        "business_candidates.csv",
        [
            {
                "business_type_code": "business_a",
                "business_type_name": "Business A",
                "candidate_unique_sample_count": "10",
                "approved_sample_count": "10",
                "recent_6_month_project_count": "3",
                "selection_status": "selected",
                "evidence_source": "approved register",
                "evidence_as_of": "2026-07-23",
                "verified_by": "technical owner",
            }
        ],
    )
    sample_rows = [
        {
            "sample_id": f"S{index:03d}",
            "document_version_id": str(index),
            "document_id": str(index),
            "business_type_code": "business_a",
            "document_title": f"Sample {index}",
            "original_filename": f"sample-{index}.docx",
            "sha256": f"{index:064x}",
            "source_format": "docx",
            "storage_verified": "yes",
            "technical_review_status": "approved",
            "approval_evidence": f"approval-{index}",
            "usage_role": "development" if index <= 5 else "blind",
            "blind_eligible": "no" if index <= 5 else "yes",
        }
        for index in range(1, 11)
    ]
    _write_rows(base_dir, "sample_inventory.csv", sample_rows)
    _write_rows(
        base_dir,
        "blind_test_set.csv",
        [
            {
                "blind_case_id": f"B{index:03d}",
                "sample_id": f"S{index:03d}",
                "business_type_code": "business_a",
                "custodian": "evaluation owner",
                "isolated_at": "2026-07-23",
                "leakage_check_status": "passed",
                "approval_status": "approved",
            }
            for index in range(6, 11)
        ],
    )
    _write_rows(
        base_dir,
        "template_inventory.csv",
        [
            {
                "template_id": f"T{index:03d}",
                "document_version_id": str(100 + index),
                "business_type_code": "business_a",
                "client_code": f"CLIENT-{index}",
                "template_name": f"Template {index}",
                "source_kind": "approved template",
                "sha256": f"{100 + index:064x}",
                "required_placeholders_verified": "yes",
                "minimum_render_verified": "yes",
                "approval_status": "approved",
                "approved_by": "technical owner",
            }
            for index in range(1, 3)
        ],
    )
    _write_rows(
        base_dir,
        "field_dictionary.csv",
        [
            {
                "field_code": "project_name",
                "display_name": "Project name",
                "data_type": "string",
                "required": "yes",
                "source": "existing_system",
                "example": "Example project",
                "confirmation_method": "human confirmation",
                "approval_status": "approved",
            }
        ],
    )
    _write_rows(
        base_dir,
        "risk_labels.csv",
        [
            {
                "risk_code": "risk_a",
                "risk_name": "Risk A",
                "trigger_facts": "Confirmed fact A",
                "evidence_required": "Evidence A",
                "default_section_code": "safety_measures",
                "severity": "high",
                "approval_status": "approved",
            }
        ],
    )
    _write_rows(
        base_dir,
        "clause_applicability_matrix.csv",
        [
            {
                "matrix_id": "M001",
                "risk_code": "risk_a",
                "section_code": "safety_measures",
                "clause_code": "CLAUSE-001",
                "clause_version": "v1",
                "applicability_condition": "Risk A matched",
                "required_when_matched": "yes",
                "conflict_priority": "confirmed_fact_over_history",
                "approval_status": "approved",
                "approved_by": "technical owner",
            }
        ],
    )
    _write_rows(
        base_dir,
        "section_annotations.csv",
        [
            {
                "annotation_id": f"A{index:03d}",
                "sample_id": f"S{index:03d}",
                "document_version_id": str(index),
                "section_code": "overview",
                "heading_text": "Overview",
                "paragraph_start": "1",
                "paragraph_end": "5",
                "reusable_status": "project_specific",
                "contains_project_specific_data": "yes",
                "review_status": "approved",
                "reviewer": "technical owner",
            }
            for index in range(1, 6)
        ],
    )
    _write_rows(
        base_dir,
        "model_configuration_decision.csv",
        [
            {
                "capability": capability,
                "provider": "approved-provider",
                "service_class": "cloud",
                "model_alias": f"approved-{capability}",
                "data_region": "approved-region",
                "supports_structured_json": "yes",
                "supports_timeout_cancel": "yes",
                "supports_request_id": "yes",
                "token_cost_tracking": "yes",
                "sensitive_prompt_logging": "prohibited",
                "security_review_status": "approved",
                "technical_approval_status": "approved",
                "approved_by": "security and technical owners",
                "approved_at": "2026-07-23",
            }
            for capability in sorted(REQUIRED_MODEL_CAPABILITIES)
        ],
    )
    _write_rows(
        base_dir,
        "expert_scoring_rubric.csv",
        [
            {
                "criterion_code": criterion,
                "criterion_name": criterion,
                "scope": "section",
                "score_min": "1",
                "score_max": "5",
                "weight_percent": "100" if criterion == "factual_accuracy" else "0",
                "hard_gate": "yes",
                "pass_rule": "approved rule",
                "owner": "technical owner",
                "approval_status": "approved",
            }
            for criterion in sorted(REQUIRED_SCORE_CRITERIA)
        ],
    )
    _write_rows(
        base_dir,
        "signoff_record.csv",
        [
            {
                "artifact_code": code,
                "artifact_name": code,
                "required_role": "technical owner",
                "decision": "approved",
                "approver": "technical owner",
                "approved_at": "2026-07-23",
                "evidence_reference": f"evidence-{code}",
            }
            for code in sorted(REQUIRED_SIGNOFFS)
        ],
    )


def test_repository_phase0_assets_have_valid_structure() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    phase0_dir = repository_root / "docs" / "document_agent" / "phase0"

    assert validate_structure(phase0_dir) == []


def test_repository_phase0_development_gate_passes() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    phase0_dir = repository_root / "docs" / "document_agent" / "phase0"

    assert validate_development_gate(phase0_dir) == []


def test_repository_phase0_gate_passes() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    phase0_dir = repository_root / "docs" / "document_agent" / "phase0"

    assert validate_gate(phase0_dir) == []


def test_gate_rejects_structurally_valid_but_incomplete_draft(tmp_path: Path) -> None:
    phase0_dir = tmp_path / "phase0"
    _write_empty_phase0_fixture(phase0_dir)

    issue_codes = {issue.code for issue in validate_gate(phase0_dir)}

    assert "MANIFEST_NOT_APPROVED" in issue_codes
    assert "BUSINESS_SELECTION_COUNT" in issue_codes
    assert "APPROVED_SAMPLE_COUNT" in issue_codes
    assert "BLIND_SAMPLE_COUNT" in issue_codes
    assert "APPROVED_TEMPLATE_COUNT" in issue_codes
    assert "FIELD_DICTIONARY_EMPTY" in issue_codes
    assert "APPROVED_RISK_EMPTY" in issue_codes


def test_structure_reports_changed_csv_contract(tmp_path: Path) -> None:
    phase0_dir = tmp_path / "phase0"
    _write_empty_phase0_fixture(phase0_dir)
    (phase0_dir / "blind_test_set.csv").write_text("wrong,headers\n", encoding="utf-8")

    issues = validate_structure(phase0_dir)

    assert any(issue.code == "CSV_HEADERS_INVALID" for issue in issues)


def test_gate_accepts_complete_and_approved_fixture(tmp_path: Path) -> None:
    phase0_dir = tmp_path / "phase0"
    _complete_phase0_fixture(phase0_dir)

    assert validate_gate(phase0_dir) == []


def test_gate_rejects_blind_sample_in_section_annotations(tmp_path: Path) -> None:
    phase0_dir = tmp_path / "phase0"
    _complete_phase0_fixture(phase0_dir)
    annotations_path = phase0_dir / "section_annotations.csv"
    with annotations_path.open(encoding="utf-8", newline="") as source:
        annotations = list(csv.DictReader(source))
    annotations.append(
        {
            "annotation_id": "A006",
            "sample_id": "S006",
            "document_version_id": "6",
            "section_code": "overview",
            "heading_text": "Overview",
            "paragraph_start": "1",
            "paragraph_end": "5",
            "reusable_status": "project_specific",
            "contains_project_specific_data": "yes",
            "review_status": "approved",
            "reviewer": "technical owner",
        }
    )
    _write_rows(phase0_dir, "section_annotations.csv", annotations)

    issue_codes = {issue.code for issue in validate_gate(phase0_dir)}

    assert "BLIND_ANNOTATION_LEAKAGE" in issue_codes
