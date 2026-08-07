from apps.document_generation.engine.canonical_facts import (
    enrich_required_fact_candidates,
    validate_required_fact_value,
)
from apps.document_generation.engine.contracts import (
    FactCandidate,
    ParsedBlock,
    ParsedBlockType,
    ParsedDocument,
    SourceLocator,
)


def _document() -> ParsedDocument:
    return ParsedDocument(
        document_version_id=195,
        filename="入场方案.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content_sha256="1" * 64,
        title="入场方案",
        blocks=(
            ParsedBlock(
                block_id="195:p:23",
                block_type=ParsedBlockType.PARAGRAPH,
                text="主要内容包括27台风电机组的变桨轴承、高强度螺栓无损检测。",
                locator=SourceLocator(paragraph_index=23),
            ),
            ParsedBlock(
                block_id="195:p:30",
                block_type=ParsedBlockType.PARAGRAPH,
                text="对变桨轴承采用相控阵超声无损探伤，对螺栓采用电磁超声波检测。",
                locator=SourceLocator(paragraph_index=30),
            ),
            ParsedBlock(
                block_id="195:p:112",
                block_type=ParsedBlockType.PARAGRAPH,
                text="人员登塔并攀爬塔筒，存在高处作业风险。",
                locator=SourceLocator(paragraph_index=112),
            ),
        ),
    )


def test_enriches_source_anchored_required_candidates() -> None:
    initial = FactCandidate(
        field="project_name",
        value="妙香山项目",
        value_type="string",
        source_document_version_id=195,
        locator=SourceLocator(paragraph_index=0, text_quote="妙香山项目"),
        confidence=1,
    )

    candidates = enrich_required_fact_candidates((initial,), (_document(),))
    by_field = {candidate.field: candidate for candidate in candidates}

    assert by_field["work_scope"].locator.paragraph_index == 23
    assert by_field["inspection_component_codes"].value == [
        "high_strength_bolt",
        "pitch_bearing",
    ]
    assert by_field["inspection_method_codes"].value == ["UT", "PAUT"]
    assert {
        item["risk_code"] for item in by_field["risk_evidence_items"].value
    } >= {"high_altitude", "climbing_tower"}


def test_required_fact_value_validation_uses_controlled_codes() -> None:
    assert validate_required_fact_value("inspection_component_codes", []) == "检测部件至少选择一项"
    assert (
        validate_required_fact_value("inspection_method_codes", ["unknown"])
        == "检测方法中存在不支持的选项：unknown"
    )
    assert (
        validate_required_fact_value(
            "risk_evidence_items",
            [{"risk_code": "high_altitude", "evidence": ""}],
        )
        == "高处作业缺少事实依据"
    )
    assert validate_required_fact_value("risk_evidence_items", []) is None


def test_paut_wording_does_not_implicitly_add_plain_ut() -> None:
    document = _document().model_copy(
        update={
            "blocks": (
                ParsedBlock(
                    block_id="195:p:23",
                    block_type=ParsedBlockType.PARAGRAPH,
                    text="工作范围为10号机组叶片螺栓检测。",
                    locator=SourceLocator(paragraph_index=23),
                ),
                ParsedBlock(
                    block_id="195:p:30",
                    block_type=ParsedBlockType.PARAGRAPH,
                    text="叶片螺栓采用相控阵超声检测方法。",
                    locator=SourceLocator(paragraph_index=30),
                ),
            )
        },
    )

    candidates = enrich_required_fact_candidates((), (document,))
    by_field = {candidate.field: candidate for candidate in candidates}

    assert by_field["inspection_method_codes"].value == ["PAUT"]


def test_user_prompt_is_deterministically_mapped_to_key_project_facts() -> None:
    prompt = ParsedDocument(
        document_version_id=0,
        filename="用户本次编制要求.prompt",
        mime_type="application/x-wind-doc-agent-prompt",
        content_sha256="2" * 64,
        title="用户本次编制要求",
        blocks=(
            ParsedBlock(
                block_id="prompt:p:0",
                block_type=ParsedBlockType.PARAGRAPH,
                text="项目名称：苍南风场年度检修",
                locator=SourceLocator(paragraph_index=0),
            ),
            ParsedBlock(
                block_id="prompt:p:2",
                block_type=ParsedBlockType.PARAGRAPH,
                text="用户本次编制要求：仅开展塔筒焊缝超声探伤，涉及人员登塔作业。",
                locator=SourceLocator(paragraph_index=2),
            ),
        ),
    )

    candidates = enrich_required_fact_candidates(
        (),
        (_document(), prompt),
        preferred_source_document_version_id=0,
    )
    prompt_facts = {
        candidate.field: candidate
        for candidate in candidates
        if candidate.source_document_version_id == 0
    }

    assert prompt_facts["project_name"].value == "苍南风场年度检修"
    assert prompt_facts["work_scope"].value == "仅开展塔筒焊缝超声探伤，涉及人员登塔作业。"
    assert prompt_facts["inspection_component_codes"].value == ["tower_weld"]
    assert prompt_facts["inspection_method_codes"].value == ["UT"]
    assert prompt_facts["risk_evidence_items"].value == [
        {
            "risk_code": "climbing_tower",
            "evidence": "用户本次编制要求：仅开展塔筒焊缝超声探伤，涉及人员登塔作业。",
        }
    ]


def test_long_multiline_prompt_uses_details_after_the_opening_instruction() -> None:
    prompt = ParsedDocument(
        document_version_id=0,
        filename="用户本次编制要求.prompt",
        mime_type="application/x-wind-doc-agent-prompt",
        content_sha256="3" * 64,
        title="用户本次编制要求",
        blocks=(
            ParsedBlock(
                block_id="prompt:p:0",
                block_type=ParsedBlockType.PARAGRAPH,
                text="项目名称：系统项目名称",
                locator=SourceLocator(paragraph_index=0),
            ),
            ParsedBlock(
                block_id="prompt:p:2",
                block_type=ParsedBlockType.PARAGRAPH,
                text="用户本次编制要求：请严格沿用甲方模板，不改变整体结构。",
                locator=SourceLocator(paragraph_index=2),
            ),
            ParsedBlock(
                block_id="prompt:p:3",
                block_type=ParsedBlockType.PARAGRAPH,
                text=(
                    "本次项目为“新疆哈密御风风机主轴超声探伤项目”，"
                    "主要工作内容为对风电机组主轴检测区域进行超声探伤检测，工期按现场确定。"
                ),
                locator=SourceLocator(paragraph_index=3),
            ),
            ParsedBlock(
                block_id="prompt:p:4",
                block_type=ParsedBlockType.PARAGRAPH,
                text="重点考虑车辆伤害、触电、火灾、大风天气和机械伤害。",
                locator=SourceLocator(paragraph_index=4),
            ),
        ),
    )

    wrong_model_candidate = FactCandidate(
        field="inspection_component_codes",
        value=["pitch_bearing"],
        value_type="array",
        source_document_version_id=0,
        locator=SourceLocator(paragraph_index=3),
        confidence=0.9,
    )
    candidates = enrich_required_fact_candidates(
        (wrong_model_candidate,),
        (prompt,),
        preferred_source_document_version_id=0,
    )
    by_field = {candidate.field: candidate for candidate in candidates}

    assert by_field["project_name"].value == "新疆哈密御风风机主轴超声探伤项目"
    assert by_field["work_scope"].value == "对风电机组主轴检测区域进行超声探伤检测"
    assert by_field["inspection_component_codes"].value == ["main_shaft"]
    assert by_field["inspection_method_codes"].value == ["UT"]
    assert {
        item["risk_code"] for item in by_field["risk_evidence_items"].value
    } >= {
        "vehicle_traffic",
        "electrical_work",
        "fire_hot_work",
        "extreme_weather",
        "mechanical_injury",
    }
