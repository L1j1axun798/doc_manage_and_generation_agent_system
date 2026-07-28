from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_ENGINE_IMPORT_ROOTS = frozenset(
    {
        "apps",
        "common",
        "config",
        "django",
        "django_rq",
        "redis",
        "rest_framework",
        "rq",
    }
)
FORBIDDEN_PROVIDER_IMPORT_ROOTS = frozenset(
    {
        "common",
        "config",
        "django",
        "django_rq",
        "redis",
        "rest_framework",
        "rq",
    }
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _absolute_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.partition(".")[0])
    return roots


def validate_architecture(root: Path) -> list[str]:
    issues: list[str] = []
    engine_root = root / "backend/apps/document_generation/engine"
    for path in sorted(engine_root.glob("*.py")):
        forbidden = _absolute_import_roots(path) & FORBIDDEN_ENGINE_IMPORT_ROOTS
        for import_root in sorted(forbidden):
            issues.append(f"ENGINE_FRAMEWORK_COUPLING:{path.name}:{import_root}")

    provider_root = root / "backend/apps/document_generation/providers"
    for path in sorted(provider_root.glob("*.py")):
        forbidden = _absolute_import_roots(path) & FORBIDDEN_PROVIDER_IMPORT_ROOTS
        for import_root in sorted(forbidden):
            issues.append(f"PROVIDER_FRAMEWORK_COUPLING:{path.name}:{import_root}")

    jobs = (root / "backend/apps/document_generation/jobs.py").read_text(encoding="utf-8")
    if "section_validator=ControlledSectionValidator()" not in jobs:
        issues.append("PRODUCTION_VALIDATOR_NOT_CONTROLLED")
    if "section_validator=BasicSectionValidator()" in jobs:
        issues.append("TEST_VALIDATOR_USED_IN_PRODUCTION")

    queues = (root / "backend/apps/document_generation/queues.py").read_text(encoding="utf-8")
    if '"apps.document_generation.jobs.run_generation_task",\n            task_id,' not in queues:
        issues.append("QUEUE_PAYLOAD_NOT_TASK_UUID_ONLY")

    project_page = (
        root / "fronted/src/modules/projects/pages/ProjectDetailPage.vue"
    ).read_text(encoding="utf-8")
    agent_imports = [
        line
        for line in project_page.splitlines()
        if "modules/document-generation/" in line
    ]
    if agent_imports:
        issues.append("FRONTEND_PROJECT_PAGE_OVERCOUPLED")

    generation_page = (
        root / "fronted/src/modules/document-generation/pages/DocumentGenerationPage.vue"
    ).read_text(encoding="utf-8")
    generation_page_imports = [
        line
        for line in generation_page.splitlines()
        if "modules/document-generation/" in line
        or "../components/DocumentGenerationPanel.vue" in line
    ]
    if generation_page_imports != [
        "import DocumentGenerationPanel from '../components/DocumentGenerationPanel.vue'"
    ]:
        issues.append("FRONTEND_AGENT_PAGE_INTEGRATION_INVALID")
    return issues


def main() -> int:
    issues = validate_architecture(_repository_root())
    if issues:
        print(f"[FAIL] Document Agent architecture: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("[PASS] Document Agent architecture boundaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
