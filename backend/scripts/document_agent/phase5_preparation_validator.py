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


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def validate_phase5_preparation(repository_root: Path) -> list[str]:
    phase0_dir = repository_root / "docs" / "document_agent" / "phase0"
    phase5_dir = repository_root / "docs" / "document_agent" / "phase5"
    manifest = json.loads((phase5_dir / "phase5_manifest.json").read_text(encoding="utf-8"))
    issues: list[str] = []
    if manifest.get("status") not in {
        "blocked_waiting_for_evaluation_inputs",
        "evaluation_in_progress",
        "real_generation_completed_awaiting_expert_review",
        "approved",
    }:
        issues.append("PHASE5_STATUS_INVALID")

    freeze = manifest.get("pre_evaluation_freeze", {})
    checks = {
        "phase4_manifest": (
            "docs/document_agent/phase4/phase4_manifest.json",
            freeze.get("current_phase4_manifest_sha256")
            or freeze.get("phase4_manifest_sha256"),
        ),
        "knowledge_index_builder": (
            "backend/scripts/document_agent/phase3_evaluator.py",
            freeze.get("knowledge_index_builder_sha256"),
        ),
        "offline_cli": (
            "backend/scripts/document_agent/phase5_cli.py",
            freeze.get("offline_cli_sha256"),
        ),
        "evaluation_harness": (
            "backend/scripts/document_agent/phase5_evaluator.py",
            freeze.get("evaluation_harness_sha256"),
        ),
        "implementation_fingerprint_helper": (
            "backend/scripts/document_agent/fingerprints.py",
            freeze.get("implementation_fingerprint_helper_sha256"),
        ),
        "review_scorecard_builder": (
            "backend/scripts/document_agent/phase5_scorecard_builder.py",
            freeze.get("review_scorecard_builder_sha256"),
        ),
        "provider_healthcheck": (
            "backend/scripts/document_agent/provider_healthcheck.py",
            freeze.get("provider_healthcheck_sha256"),
        ),
    }
    for name, (relative_path, expected_hash) in checks.items():
        path = repository_root / relative_path
        if not path.is_file() or _sha256(path) != expected_hash:
            issues.append(f"FREEZE_HASH_MISMATCH:{name}")

    blind_rows = [
        row
        for row in _csv_rows(phase0_dir / "blind_test_set.csv")
        if row["approval_status"] == "approved"
    ]
    case_rows = _csv_rows(phase5_dir / "evaluation_cases.csv")
    expected_pairs = {(row["blind_case_id"], row["sample_id"]) for row in blind_rows}
    actual_pairs = {(row["blind_case_id"], row["answer_sample_id"]) for row in case_rows}
    if actual_pairs != expected_pairs:
        issues.append("BLIND_CASE_REGISTRY_MISMATCH")
    if len(actual_pairs) != len(case_rows):
        issues.append("DUPLICATE_EVALUATION_CASE")
    if manifest.get("blind_case_count") != len(blind_rows):
        issues.append("BLIND_CASE_COUNT_MISMATCH")
    ready_count = sum(row["input_bundle_status"] == "ready" for row in case_rows)
    if manifest.get("paired_current_project_input_bundle_count") != ready_count:
        issues.append("PAIRED_INPUT_COUNT_MISMATCH")

    phase0_scorecard_header = (
        (phase0_dir / "expert_scorecard.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    )
    phase5_scorecard_header = (
        (phase5_dir / "evaluation_scorecard.csv").read_text(encoding="utf-8-sig").splitlines()[0]
    )
    if phase5_scorecard_header != phase0_scorecard_header:
        issues.append("SCORECARD_SCHEMA_MISMATCH")
    return issues


def main() -> int:
    issues = validate_phase5_preparation(_repository_root())
    if issues:
        print(f"[FAIL] Phase 5 preparation validation: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[PASS] Phase 5 preparation is frozen and structurally complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
