from __future__ import annotations

from hashlib import sha256
from pathlib import Path

IMPLEMENTATION_PATHS = (
    "backend/apps/document_generation/engine/contracts.py",
    "backend/apps/document_generation/engine/orchestrator.py",
    "backend/apps/document_generation/engine/rag.py",
    "backend/apps/document_generation/engine/rendering.py",
    "backend/apps/document_generation/engine/rules.py",
    "backend/apps/document_generation/engine/sections.py",
    "backend/apps/document_generation/engine/validation.py",
    "backend/apps/document_generation/providers/embedding.py",
    "backend/apps/document_generation/providers/llm.py",
    "backend/apps/document_generation/prompts/section_generation/v2.md",
    "backend/apps/document_generation/prompts/section_revision/v2.md",
    "backend/apps/document_generation/prompts/schema_repair/v1.md",
)


def compute_implementation_fingerprint(repository_root: Path | None = None) -> str:
    """Bind a Phase 5 review bundle to the exact generation implementation."""

    root = repository_root or Path(__file__).resolve().parents[3]
    digest = sha256()
    for relative_path in IMPLEMENTATION_PATHS:
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"implementation fingerprint input missing: {path}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
