from __future__ import annotations

from pathlib import Path

import pytest

from apps.document_generation.engine.contracts import ConfirmedFact, SourceLocator
from apps.document_generation.engine.errors import AgentError
from apps.document_generation.engine.rules import (
    ApprovedClauseRepository,
    DeterministicRiskProfiler,
)


def _phase0_path(filename: str) -> Path:
    root = Path(__file__).resolve().parents[5]
    return root / "docs" / "document_agent" / "phase0" / filename


def _phase4_path(filename: str) -> Path:
    root = Path(__file__).resolve().parents[5]
    return root / "docs" / "document_agent" / "phase4" / filename


def _risk_fact(items: list[dict[str, str]]) -> ConfirmedFact:
    return ConfirmedFact(
        field="risk_evidence_items",
        value=items,
        value_type="list[object]",
        source_document_version_id=134,
        locator=SourceLocator(paragraph_index=20),
        confidence=1,
        confirmed_by=7,
    )


def test_every_approved_phase0_risk_has_a_deterministic_clause_path() -> None:
    profiler = DeterministicRiskProfiler.from_csv(_phase0_path("risk_labels.csv"))
    repository = ApprovedClauseRepository.from_csv(
        matrix_path=_phase0_path("clause_applicability_matrix.csv"),
        clause_blocks_path=_phase4_path("approved_clause_blocks.csv"),
    )
    risk_codes = sorted(profiler.definitions)
    profile = profiler.build(
        (
            _risk_fact(
                [
                    {"risk_code": code, "evidence": f"{code}-current-project-evidence"}
                    for code in risk_codes
                ]
            ),
        )
    )
    clauses = tuple(
        clause
        for section_code in (
            "safety_measures",
            "environmental_measures",
            "emergency_plan",
        )
        for clause in repository.select(profile, section_code)
    )

    assert len(profile.risk_codes) == 12
    assert len(clauses) == 16
    assert {risk_code for clause in clauses for risk_code in clause.matched_risk_codes} == set(
        risk_codes
    )
    assert all(clause.text for clause in clauses)


def test_unapproved_risk_code_never_reaches_clause_selection() -> None:
    profiler = DeterministicRiskProfiler.from_csv(_phase0_path("risk_labels.csv"))

    with pytest.raises(AgentError) as captured:
        profiler.build((_risk_fact([{"risk_code": "invented_risk", "evidence": "模型自行添加"}]),))

    assert captured.value.code == "RISK_CODE_UNAPPROVED"
