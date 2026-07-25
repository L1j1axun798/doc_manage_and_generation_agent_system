# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from apps.document_generation.engine.contracts import ConfirmedFact

BUSINESS_TYPE = "wind_turbine_inspection_four_measures_two_plans"
SECTION_CODES = (
    "overview",
    "organization_measures",
    "construction_plan",
    "technical_measures",
    "safety_measures",
    "risk_identification",
    "emergency_plan",
    "environmental_measures",
)
BASE_REQUIRED_FIELDS = {
    "project_name",
    "work_scope",
    "risk_evidence_items",
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _repo_relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _approved_template_hash(
    *,
    repository_root: Path,
    template_id: str,
) -> str:
    inventory_path = (
        repository_root / "docs" / "document_agent" / "phase0" / "template_inventory.csv"
    )
    with inventory_path.open(encoding="utf-8-sig", newline="") as source:
        matching = [
            row
            for row in csv.DictReader(source)
            if row["template_id"] == template_id and row["approval_status"] == "approved"
        ]
    if len(matching) != 1:
        raise ValueError(f"approved template not found or duplicated: {template_id}")
    if matching[0]["business_type_code"] != BUSINESS_TYPE:
        raise ValueError(f"template business type mismatch: {template_id}")
    return matching[0]["sha256"]


def build_offline_input(
    *,
    locators_path: Path,
    template_id: str,
    template_path: Path,
    output_path: Path,
    repository_root: Path | None = None,
) -> Path:
    repository_root = (repository_root or _repository_root()).resolve()
    payload = json.loads(locators_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("locator sidecar must contain a JSON object")
    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id is required")
    document_version_id = payload.get("document_version_id")
    if not isinstance(document_version_id, int) or document_version_id <= 0:
        raise ValueError("document_version_id must be a positive integer")
    fact_sheet_path_value = payload.get("fact_sheet_path")
    if not isinstance(fact_sheet_path_value, str) or not fact_sheet_path_value.strip():
        raise ValueError("fact_sheet_path is required")
    fact_sheet_path = Path(fact_sheet_path_value).resolve()
    expected_fact_sheet_hash = payload.get("fact_sheet_sha256")
    if not isinstance(expected_fact_sheet_hash, str) or _sha256(fact_sheet_path) != (
        expected_fact_sheet_hash.lower()
    ):
        raise ValueError("fact sheet hash mismatch")

    raw_facts = payload.get("confirmed_facts")
    facts = TypeAdapter(tuple[ConfirmedFact, ...]).validate_python(raw_facts)
    fields = {fact.field for fact in facts}
    missing = sorted(BASE_REQUIRED_FIELDS - fields)
    if missing:
        raise ValueError(f"base required fields missing: {','.join(missing)}")
    if {fact.source_document_version_id for fact in facts} != {document_version_id}:
        raise ValueError("confirmed facts must point to the fact sheet document version")

    approved_hash = _approved_template_hash(
        repository_root=repository_root,
        template_id=template_id,
    )
    if _sha256(template_path) != approved_hash:
        raise ValueError(f"template hash does not match approved inventory: {template_id}")

    output_payload: dict[str, Any] = {
        "request_id": f"phase5-{case_id}-smoke-v1",
        "idempotency_key": f"phase5-{case_id}-smoke-v1",
        "business_type": BUSINESS_TYPE,
        "template_id": template_id,
        "template_path": _repo_relative(template_path, repository_root),
        "template_required_placeholders": [],
        "sources": [
            {
                "document_version_id": document_version_id,
                "path": _repo_relative(fact_sheet_path, repository_root),
            }
        ],
        "confirmed_facts": [fact.model_dump(mode="json") for fact in facts],
        "required_fact_fields": sorted(fields),
        "section_codes": list(SECTION_CODES),
        "historical_entity_blacklist": [],
        "knowledge_json_path": None,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a reproducible Phase 5 offline input from a fact-sheet sidecar.",
    )
    parser.add_argument("--locators", type=Path, required=True)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--template-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output_path = build_offline_input(
        locators_path=args.locators.resolve(),
        template_id=args.template_id,
        template_path=args.template_path.resolve(),
        output_path=args.output.resolve(),
    )
    print(f"[PASS] Phase 5 offline input: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
