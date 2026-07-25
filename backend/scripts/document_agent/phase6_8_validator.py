from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.document_agent.architecture_validator import validate_architecture  # noqa: E402


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read(root: Path, relative_path: str) -> str:
    path = root / relative_path
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _require_files(root: Path, files: list[str], issues: list[str]) -> None:
    for relative_path in files:
        if not (root / relative_path).is_file():
            issues.append(f"MISSING_FILE:{relative_path}")


def _require_text(
    root: Path,
    relative_path: str,
    required: list[str],
    issues: list[str],
) -> None:
    text = _read(root, relative_path)
    for value in required:
        if value not in text:
            issues.append(f"MISSING_IMPLEMENTATION:{relative_path}:{value}")


def _validate_manifest(
    root: Path,
    phase: int,
    issues: list[str],
) -> None:
    relative_path = f"docs/document_agent/phase{phase}/phase{phase}_manifest.json"
    path = root / relative_path
    if not path.is_file():
        issues.append(f"MISSING_FILE:{relative_path}")
        return
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("phase") != phase:
        issues.append(f"MANIFEST_PHASE_MISMATCH:{phase}")
    if manifest.get("status") != "development_complete_feature_disabled":
        issues.append(f"MANIFEST_STATUS_INVALID:{phase}")
    if manifest.get("production_activation_allowed") is not False:
        issues.append(f"PRODUCTION_GATE_OPEN:{phase}")


def validate_phase6(root: Path) -> list[str]:
    issues: list[str] = []
    _validate_manifest(root, 6, issues)
    _require_files(
        root,
        [
            "backend/apps/document_generation/models.py",
            "backend/apps/document_generation/migrations/0001_initial.py",
            "backend/apps/document_generation/migrations/0002_generationtask_operation.py",
            "backend/apps/document_generation/repositories.py",
            "backend/apps/document_generation/services.py",
            "backend/apps/document_generation/selectors.py",
            "backend/apps/document_generation/permissions.py",
            "backend/apps/document_generation/serializers.py",
            "backend/apps/document_generation/views.py",
            "backend/apps/document_generation/urls.py",
            "backend/apps/document_generation/bootstrap.py",
            (
                "backend/apps/document_generation/management/commands/"
                "bootstrap_document_agent.py"
            ),
            (
                "backend/apps/document_generation/management/commands/"
                "check_document_agent_runtime.py"
            ),
        ],
        issues,
    )
    _require_text(
        root,
        "backend/apps/document_generation/models.py",
        [
            "class DocumentTemplate",
            "class ClauseBlock",
            "class KnowledgeSection",
            "class GenerationTask",
            "class GenerationSource",
            "class GeneratedSection",
            "class GenerationReview",
        ],
        issues,
    )
    _require_text(
        root,
        "backend/config/settings/base.py",
        [
            "DOCUMENT_AGENT_ENABLED=(bool, False)",
            "DOCUMENT_AGENT_PHASE5_APPROVED=(bool, False)",
        ],
        issues,
    )
    _require_text(
        root,
        "backend/config/settings/production.py",
        [
            "Document Agent未通过Phase 5门禁",
            "生产环境禁止启用Document Agent Fake Provider",
        ],
        issues,
    )
    return issues


def validate_phase7(root: Path) -> list[str]:
    issues: list[str] = []
    _validate_manifest(root, 7, issues)
    _require_files(
        root,
        [
            "backend/apps/document_generation/queues.py",
            "backend/apps/document_generation/jobs.py",
            "backend/apps/document_generation/recovery.py",
            "backend/apps/document_generation/management/commands/run_document_generation_worker.py",
        ],
        issues,
    )
    _require_text(
        root,
        "backend/requirements/base.txt",
        ["django-rq", "rq>=2.10", "redis>=8.0"],
        issues,
    )
    _require_text(
        root,
        "backend/apps/document_generation/queues.py",
        [
            'QUEUE_NAME = "document-generation"',
            '"apps.document_generation.jobs.run_generation_task"',
            "job_id=task_id",
            "Retry(max=2, interval=RETRY_INTERVALS)",
        ],
        issues,
    )
    _require_text(
        root,
        "backend/apps/document_generation/services.py",
        ["transaction.on_commit(lambda: queue_generation_task(str(locked.pk)))"],
        issues,
    )
    return issues


def validate_phase8(root: Path) -> list[str]:
    issues: list[str] = []
    _validate_manifest(root, 8, issues)
    _require_files(
        root,
        [
            "fronted/src/modules/document-generation/components/DocumentGenerationPanel.vue",
            "fronted/src/modules/document-generation/api/document-generation.api.ts",
            "fronted/src/modules/document-generation/document-generation.types.ts",
            "fronted/src/modules/document-generation/workflow.ts",
        ],
        issues,
    )
    _require_text(
        root,
        "fronted/src/modules/document-generation/workflow.ts",
        ["GENERATION_POLL_INTERVAL_MS = 2000", "isEligibleEntrySource"],
        issues,
    )
    _require_text(
        root,
        "fronted/src/modules/document-generation/components/DocumentGenerationPanel.vue",
        [
            "不生成检测报告、实测结论或完工报告",
            "这里不会新增合同上传入口",
            "逐章人工审核",
        ],
        issues,
    )
    _require_text(
        root,
        "fronted/src/modules/projects/pages/ProjectDetailPage.vue",
        ["入场资料编制（四措两案）", "featureFlags.documentAgent"],
        issues,
    )
    return issues


def validate_all(root: Path) -> dict[int, list[str]]:
    phase5 = json.loads(
        (root / "docs/document_agent/phase5/phase5_manifest.json").read_text(encoding="utf-8")
    )
    shared_issues: list[str] = []
    if phase5.get("evaluation_gate", {}).get("minimum_evaluated_case_count") != 3:
        shared_issues.append("PHASE5_MINIMUM_CASE_COUNT_NOT_THREE")
    if phase5.get("accelerated_downstream_development_authorized") is not True:
        shared_issues.append("ACCELERATED_DEVELOPMENT_NOT_AUTHORIZED")
    if phase5.get("production_activation_allowed") is not False:
        shared_issues.append("PHASE5_PRODUCTION_GATE_OPEN")
    architecture_issues = validate_architecture(root)
    return {
        6: [*shared_issues, *architecture_issues, *validate_phase6(root)],
        7: [*shared_issues, *validate_phase7(root)],
        8: [*shared_issues, *validate_phase8(root)],
    }


def main() -> int:
    results = validate_all(_repository_root())
    failed = False
    for phase, issues in results.items():
        if issues:
            failed = True
            print(f"[FAIL] Phase {phase}: {len(issues)} issue(s)")
            for issue in issues:
                print(f"- {issue}")
        else:
            print(f"[PASS] Phase {phase} development gate (feature disabled)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
