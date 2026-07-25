from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_phase4(repository_root: Path) -> list[str]:
    manifest_path = repository_root / "docs" / "document_agent" / "phase4" / "phase4_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues: list[str] = []
    if manifest.get("status") != "approved_for_blind_evaluation":
        issues.append("PHASE4_STATUS_NOT_APPROVED")
    if manifest.get("blind_content_accessed_during_development") is not False:
        issues.append("BLIND_ISOLATION_BROKEN")

    freeze = manifest.get("freeze", {})
    checks = {
        "fact_extraction_prompt": (
            "backend/apps/document_generation/prompts/fact_extraction/v1.md",
            freeze.get("fact_extraction_prompt", {}).get("sha256"),
        ),
        "section_generation_prompt": (
            "backend/apps/document_generation/prompts/section_generation/v1.md",
            freeze.get("section_generation_prompt", {}).get("sha256"),
        ),
        "section_revision_prompt": (
            "backend/apps/document_generation/prompts/section_revision/v1.md",
            freeze.get("section_revision_prompt", {}).get("sha256"),
        ),
        "schema_repair_prompt": (
            "backend/apps/document_generation/prompts/schema_repair/v1.md",
            freeze.get("schema_repair_prompt", {}).get("sha256"),
        ),
        "field_dictionary": (
            "docs/document_agent/phase0/field_dictionary.csv",
            freeze.get("field_dictionary_sha256"),
        ),
        "risk_labels": (
            "docs/document_agent/phase0/risk_labels.csv",
            freeze.get("risk_labels_sha256"),
        ),
        "clause_matrix": (
            "docs/document_agent/phase0/clause_applicability_matrix.csv",
            freeze.get("clause_matrix_sha256"),
        ),
        "section_annotations": (
            "docs/document_agent/phase0/section_annotations.csv",
            freeze.get("section_annotations_sha256"),
        ),
        "model_configuration_decision": (
            "docs/document_agent/phase0/model_configuration_decision.csv",
            freeze.get("model_configuration_decision_sha256"),
        ),
        "expert_scoring_rubric": (
            "docs/document_agent/phase0/expert_scoring_rubric.csv",
            freeze.get("expert_scoring_rubric_sha256"),
        ),
        "template_inventory": (
            "docs/document_agent/phase0/template_inventory.csv",
            freeze.get("template_inventory_sha256"),
        ),
        "approved_clause_blocks": (
            "docs/document_agent/phase4/approved_clause_blocks.csv",
            freeze.get("approved_clause_blocks_sha256"),
        ),
        "contracts_implementation": (
            "backend/apps/document_generation/engine/contracts.py",
            freeze.get("contracts_implementation_sha256"),
        ),
        "errors_implementation": (
            "backend/apps/document_generation/engine/errors.py",
            freeze.get("errors_implementation_sha256"),
        ),
        "facts_implementation": (
            "backend/apps/document_generation/engine/facts.py",
            freeze.get("facts_implementation_sha256"),
        ),
        "parsing_implementation": (
            "backend/apps/document_generation/engine/parsing.py",
            freeze.get("parsing_implementation_sha256"),
        ),
        "ports_implementation": (
            "backend/apps/document_generation/engine/ports.py",
            freeze.get("ports_implementation_sha256"),
        ),
        "rendering_implementation": (
            "backend/apps/document_generation/engine/rendering.py",
            freeze.get("rendering_implementation_sha256"),
        ),
        "rules_implementation": (
            "backend/apps/document_generation/engine/rules.py",
            freeze.get("rules_implementation_sha256"),
        ),
        "orchestrator_implementation": (
            "backend/apps/document_generation/engine/orchestrator.py",
            freeze.get("orchestrator_implementation_sha256"),
        ),
        "sections_implementation": (
            "backend/apps/document_generation/engine/sections.py",
            freeze.get("sections_implementation_sha256"),
        ),
        "llm_provider_implementation": (
            "backend/apps/document_generation/providers/llm.py",
            freeze.get("llm_provider_implementation_sha256"),
        ),
        "embedding_provider_implementation": (
            "backend/apps/document_generation/providers/embedding.py",
            freeze.get("embedding_provider_implementation_sha256"),
        ),
        "rag_implementation": (
            "backend/apps/document_generation/engine/rag.py",
            freeze.get("rag_implementation_sha256"),
        ),
        "validation_implementation": (
            "backend/apps/document_generation/engine/validation.py",
            freeze.get("validation_implementation_sha256"),
        ),
    }
    for name, (relative_path, expected_hash) in checks.items():
        path = repository_root / relative_path
        if not path.is_file() or _sha256(path) != expected_hash:
            issues.append(f"FREEZE_HASH_MISMATCH:{name}")

    risk_path = repository_root / "docs/document_agent/phase0/risk_labels.csv"
    with risk_path.open(encoding="utf-8-sig", newline="") as source:
        approved_risks = [
            row for row in csv.DictReader(source) if row["approval_status"] == "approved"
        ]
    clause_path = (
        repository_root / "docs" / "document_agent" / "phase4" / "approved_clause_blocks.csv"
    )
    with clause_path.open(encoding="utf-8-sig", newline="") as source:
        approved_clauses = [
            row for row in csv.DictReader(source) if row["approval_status"] == "approved"
        ]
    gates = manifest.get("completion_gates", {})
    if len(approved_risks) != gates.get("approved_risk_rule_count"):
        issues.append("RISK_RULE_COUNT_MISMATCH")
    if len(approved_clauses) != gates.get("approved_clause_block_count"):
        issues.append("CLAUSE_BLOCK_COUNT_MISMATCH")
    if gates.get("fact_citation_coverage") != 1.0:
        issues.append("FACT_CITATION_GATE_FAILED")
    if gates.get("model_can_select_or_create_clauses") is not False:
        issues.append("MODEL_CLAUSE_AUTHORITY_INVALID")
    return issues


def main() -> int:
    issues = validate_phase4(_repository_root())
    if issues:
        print(f"[FAIL] Phase 4 validation: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[PASS] Phase 4 validation: freeze and completion gates are intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
