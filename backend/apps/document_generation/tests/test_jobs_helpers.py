from __future__ import annotations

from ..engine.contracts import (
    ParsedBlock,
    ParsedBlockType,
    ParsedDocument,
    SourceLocator,
)
from ..jobs import _anchored_initial_candidates


def test_initial_system_facts_are_only_preserved_when_exactly_anchored() -> None:
    document = ParsedDocument(
        document_version_id=7,
        filename="source.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content_sha256="1" * 64,
        title="来源",
        blocks=(
            ParsedBlock(
                block_id="p0",
                block_type=ParsedBlockType.PARAGRAPH,
                text="项目名称：当前风场检测项目",
                locator=SourceLocator(paragraph_index=0),
            ),
        ),
    )

    candidates = _anchored_initial_candidates(
        [
            {
                "field": "project_name",
                "value": "当前风场检测项目",
                "value_type": "string",
            },
            {
                "field": "project_code",
                "value": "NOT-IN-SOURCE",
                "value_type": "string",
            },
        ],
        (document,),
    )

    assert [candidate.field for candidate in candidates] == ["project_name"]
    assert candidates[0].source_document_version_id == 7
    assert candidates[0].locator.paragraph_index == 0
