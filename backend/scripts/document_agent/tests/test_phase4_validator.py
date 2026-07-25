from __future__ import annotations

from pathlib import Path

from scripts.document_agent.phase4_validator import validate_phase4


def test_repository_phase4_freeze_and_completion_gates_pass() -> None:
    repository_root = Path(__file__).resolve().parents[4]

    assert validate_phase4(repository_root) == []
