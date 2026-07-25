from __future__ import annotations

import csv
import json
from hashlib import sha256

import pytest

from scripts.document_agent.phase5_input_builder import build_offline_input


def _fact(field, value, paragraph_index):
    return {
        "field": field,
        "value": value,
        "value_type": "list[object]" if isinstance(value, list) else "string",
        "source_document_version_id": 9001,
        "locator": {"paragraph_index": paragraph_index},
        "confidence": 1,
        "confirmed_by": 1,
    }


def _prepare_repository(tmp_path):
    repository_root = tmp_path / "repository"
    inventory = repository_root / "docs" / "document_agent" / "phase0"
    inventory.mkdir(parents=True)
    template = tmp_path / "template.docx"
    template.write_bytes(b"approved-template")
    with (inventory / "template_inventory.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as target:
        writer = csv.DictWriter(
            target,
            fieldnames=[
                "template_id",
                "business_type_code",
                "sha256",
                "approval_status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "template_id": "T001",
                "business_type_code": ("wind_turbine_inspection_four_measures_two_plans"),
                "sha256": sha256(template.read_bytes()).hexdigest(),
                "approval_status": "approved",
            }
        )
    return repository_root, template


def test_build_offline_input_checks_hash_and_writes_all_sections(tmp_path) -> None:
    repository_root, template = _prepare_repository(tmp_path)
    fact_sheet = tmp_path / "fact-sheet.docx"
    fact_sheet.write_bytes(b"fact-sheet")
    locators = tmp_path / "locators.json"
    locators.write_text(
        json.dumps(
            {
                "case_id": "B001",
                "document_version_id": 9001,
                "fact_sheet_path": str(fact_sheet),
                "fact_sheet_sha256": sha256(fact_sheet.read_bytes()).hexdigest(),
                "confirmed_facts": [
                    _fact("project_name", "测试项目", 1),
                    _fact("work_scope", "测试范围", 2),
                    _fact("risk_evidence_items", [], 3),
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = build_offline_input(
        locators_path=locators,
        template_id="T001",
        template_path=template,
        output_path=tmp_path / "input.json",
        repository_root=repository_root,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["template_id"] == "T001"
    assert payload["required_fact_fields"] == [
        "project_name",
        "risk_evidence_items",
        "work_scope",
    ]
    assert len(payload["section_codes"]) == 8


def test_build_offline_input_rejects_modified_fact_sheet(tmp_path) -> None:
    repository_root, template = _prepare_repository(tmp_path)
    fact_sheet = tmp_path / "fact-sheet.docx"
    fact_sheet.write_bytes(b"modified")
    locators = tmp_path / "locators.json"
    locators.write_text(
        json.dumps(
            {
                "case_id": "B001",
                "document_version_id": 9001,
                "fact_sheet_path": str(fact_sheet),
                "fact_sheet_sha256": "0" * 64,
                "confirmed_facts": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        build_offline_input(
            locators_path=locators,
            template_id="T001",
            template_path=template,
            output_path=tmp_path / "input.json",
            repository_root=repository_root,
        )
