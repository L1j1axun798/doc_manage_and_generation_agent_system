from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.document_generation.engine.contracts import (
    ConfirmedFact,
    GenerationRequest,
    SourceLocator,
)


def test_generation_request_rejects_report_purpose(
    generation_request: GenerationRequest,
) -> None:
    payload = generation_request.model_dump()
    payload["document_purpose"] = "inspection_report"

    with pytest.raises(ValidationError, match="entry_four_measures_two_plans"):
        GenerationRequest.model_validate(payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "inspection_result",
        "measured_result",
        "detection_conclusion",
        "defect_list",
        "检测结论",
    ],
)
def test_fact_contract_rejects_completion_result_fields(field_name: str) -> None:
    with pytest.raises(ValidationError, match="result and conclusion fields"):
        ConfirmedFact(
            field=field_name,
            value="不应进入入场方案",
            value_type="string",
            source_document_version_id=1,
            locator=SourceLocator(paragraph_index=0),
            confidence=1,
            confirmed_by=1,
        )


def test_contract_rejects_unknown_fields(generation_request: GenerationRequest) -> None:
    payload = generation_request.model_dump()
    payload["inspection_conclusion"] = "合格"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GenerationRequest.model_validate(payload)
