from __future__ import annotations

import pytest

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    FactCandidate,
    SourceLocator,
)
from apps.document_generation.engine.errors import (
    AgentError,
    FactsIncompleteError,
    SourcePurposeMismatchError,
)
from apps.document_generation.engine.facts import FactMergeService, RequiredFactGate


def _candidate(
    *,
    field: str = "site_name",
    value: object = "当前场站",
    version_id: int = 1,
    confidence: float = 0.9,
) -> FactCandidate:
    return FactCandidate(
        field=field,
        value=value,
        value_type="string",
        source_document_version_id=version_id,
        locator=SourceLocator(paragraph_index=version_id),
        confidence=confidence,
    )


def _confirmed(
    *,
    field: str,
    value: object,
    version_id: int = 1,
) -> ConfirmedFact:
    return ConfirmedFact(
        **_candidate(
            field=field,
            value=value,
            version_id=version_id,
            confidence=1,
        ).model_dump(),
        confirmed_by=7,
    )


def test_same_fact_from_multiple_sources_merges_with_all_evidence() -> None:
    result = FactMergeService().merge(
        (
            _candidate(version_id=1, confidence=0.8),
            _candidate(version_id=2, confidence=0.95),
        )
    )

    assert result.conflicts == ()
    assert len(result.merged) == 1
    assert result.merged[0].value == "当前场站"
    assert result.merged[0].confidence == 0.95
    assert {evidence.source_document_version_id for evidence in result.merged[0].evidence} == {1, 2}


def test_conflicting_fact_values_are_not_automatically_selected() -> None:
    result = FactMergeService().merge(
        (
            _candidate(value="场站A", version_id=1),
            _candidate(value="场站B", version_id=2),
        )
    )

    assert result.merged == ()
    assert len(result.conflicts) == 1
    assert {candidate.value for candidate in result.conflicts[0].candidates} == {
        "场站A",
        "场站B",
    }


def test_canonical_multi_value_facts_are_combined_instead_of_reported_as_conflicts() -> None:
    result = FactMergeService().merge(
        (
            _candidate(
                field="inspection_method_codes",
                value=["UT"],
                version_id=1,
            ),
            _candidate(
                field="inspection_method_codes",
                value=["PAUT", "UT"],
                version_id=2,
            ),
        )
    )

    assert result.conflicts == ()
    assert result.merged[0].value == ["PAUT", "UT"]
    assert {item.source_document_version_id for item in result.merged[0].evidence} == {1, 2}


def test_completion_result_candidate_is_rejected_instead_of_promoted() -> None:
    result = FactMergeService().merge(
        (
            _candidate(
                field="work_scope",
                value="经检测发现塔筒存在异常",
            ),
        )
    )

    assert result.merged == ()
    assert result.rejected[0].reason_code == "RESULT_FACT_FORBIDDEN"


def test_required_fact_gate_rejects_missing_conditional_and_conflicting_values() -> None:
    gate = RequiredFactGate()
    quantity = _confirmed(field="inspection_quantity", value=12)

    with pytest.raises(FactsIncompleteError) as missing:
        gate.validate((quantity,), required_fields=("project_name",))
    assert set(missing.value.details["missing_fields"]) == {
        "project_name",
        "inspection_unit",
    }

    with pytest.raises(AgentError, match="多个已确认值") as conflict:
        gate.validate(
            (
                _confirmed(field="site_name", value="场站A", version_id=1),
                _confirmed(field="site_name", value="场站B", version_id=2),
            ),
            required_fields=(),
        )
    assert conflict.value.code == "FACT_CONFIRMATION_CONFLICT"


def test_required_fact_gate_rejects_confirmed_result_language() -> None:
    with pytest.raises(SourcePurposeMismatchError):
        RequiredFactGate().validate(
            (
                _confirmed(
                    field="work_scope",
                    value="检测结论为设备存在缺陷",
                ),
            ),
            required_fields=(),
        )
