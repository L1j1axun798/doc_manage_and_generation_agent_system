from pathlib import Path

from scripts.document_agent.phase6_8_validator import validate_all


def test_repository_phase6_to_phase8_development_gates_pass() -> None:
    repository_root = Path(__file__).resolve().parents[4]

    assert validate_all(repository_root) == {6: [], 7: [], 8: []}
