from __future__ import annotations

from pathlib import Path

from scripts.document_agent.architecture_validator import validate_architecture


def test_document_agent_architecture_boundaries() -> None:
    repository_root = Path(__file__).resolve().parents[4]

    assert validate_architecture(repository_root) == []
