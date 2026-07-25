from __future__ import annotations

import json

import pytest
from docx import Document

from scripts.document_agent.phase5_fact_sheet import build_fact_sheet


def test_build_fact_sheet_writes_traceable_fact_paragraphs(tmp_path) -> None:
    input_path = tmp_path / "facts.json"
    input_path.write_text(
        json.dumps(
            {
                "case_id": "B-TEST",
                "title": "测试入场资料事实底稿",
                "document_version_id": 9001,
                "review_status": "transcribed_from_user_supplied_sources",
                "facts": [
                    {
                        "field": "project_name",
                        "label": "项目名称",
                        "value": "测试项目",
                        "value_type": "string",
                        "source_reference": "source.pdf 第2页",
                    },
                    {
                        "field": "inspection_quantity",
                        "label": "检测数量",
                        "value": 19,
                        "value_type": "integer",
                        "source_reference": "source.pdf 第1页",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "fact-sheet.docx"

    _, locators_path = build_fact_sheet(
        input_path=input_path,
        output_path=output_path,
    )

    document = Document(output_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    locators = json.loads(locators_path.read_text(encoding="utf-8"))
    assert locators["review_status"] == "transcribed_from_user_supplied_sources"
    assert len(locators["confirmed_facts"]) == 2
    for fact in locators["confirmed_facts"]:
        paragraph_index = fact["locator"]["paragraph_index"]
        assert paragraphs[paragraph_index].startswith(f"[{fact['field']}]")


def test_build_fact_sheet_rejects_duplicate_fields(tmp_path) -> None:
    input_path = tmp_path / "facts.json"
    fact = {
        "field": "project_name",
        "label": "项目名称",
        "value": "测试项目",
        "value_type": "string",
        "source_reference": "source.docx p1",
    }
    input_path.write_text(
        json.dumps(
            {
                "case_id": "B-TEST",
                "title": "测试入场资料事实底稿",
                "document_version_id": 9001,
                "review_status": "transcribed_from_user_supplied_sources",
                "facts": [fact, fact],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        build_fact_sheet(
            input_path=input_path,
            output_path=tmp_path / "fact-sheet.docx",
        )
