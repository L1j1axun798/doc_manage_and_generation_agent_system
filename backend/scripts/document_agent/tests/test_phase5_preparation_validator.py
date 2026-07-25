from __future__ import annotations

from pathlib import Path

from scripts.document_agent.phase5_preparation_validator import (
    validate_phase5_preparation,
)


def test_repository_phase5_preparation_is_frozen_and_consistent() -> None:
    repository_root = Path(__file__).resolve().parents[4]

    assert validate_phase5_preparation(repository_root) == []
