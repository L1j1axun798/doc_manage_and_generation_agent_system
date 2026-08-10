from apps.document_generation.engine.content_composition import compose_section
from apps.document_generation.engine.contracts import (
    AgentConversationContext,
    AgentTemplateContext,
    GeneratedSection,
    PersonnelContext,
    RetrievedSection,
    RiskProfile,
    SectionContext,
)


def _template(table_slots: list[dict[str, object]]) -> AgentTemplateContext:
    return AgentTemplateContext(
        id="1",
        code="T001",
        name="测试模板",
        filename="template.docx",
        version="1",
        document_version_id=1,
        layout_schema={"table_slots": table_slots},
    )


def test_personnel_table_uses_frozen_snapshot_and_tracks_blank_cells() -> None:
    context = SectionContext(
        section_code="organization_measures",
        objective="组织措施",
        confirmed_facts=(),
        risk_profile=RiskProfile(),
        conversation_context=AgentConversationContext(
            personnel=(PersonnelContext(id="7", name="脱敏人员", phone="13800000000"),),
            template=_template(
                [
                    {
                        "block_key": "personnel_information",
                        "section_code": "organization_measures",
                        "prototype_table_index": 2,
                        "headers": ["序号", "姓名", "岗位", "联系电话"],
                    }
                ]
            ),
        ),
    )

    result = compose_section(
        GeneratedSection(section_code=context.section_code, title="组织措施"),
        context,
    )

    assert len(result.tables) == 1
    assert result.tables[0].rows == (("1", "脱敏人员", "", "13800000000"),)
    assert result.tables[0].prototype_table_index == 2
    assert any("岗位" in item for item in result.tables[0].missing_cells)
    assert result.composition_decisions[0].selected is True


def test_hazard_table_requires_two_grounded_rows_and_blanks_project_columns() -> None:
    reference = RetrievedSection(
        chunk_id="risk-table",
        source_document_version_id=9,
        section_code="risk_identification",
        heading_path=("风险辨识",),
        text="危险源 | 控制措施 | 责任人\n高处坠落 | 双钩安全带全程挂设 | 历史人员\n工具坠落 | 使用防坠绳 | 历史人员",
        similarity=0.9,
        final_score=0.9,
        risk_tags=("high_altitude",),
        block_type="table",
        structured_rows=(
            ("危险源", "控制措施", "责任人"),
            ("高处坠落", "双钩安全带全程挂设", "历史人员"),
            ("工具坠落", "使用防坠绳", "历史人员"),
        ),
    )
    context = SectionContext(
        section_code="risk_identification",
        objective="风险辨识",
        confirmed_facts=(),
        risk_profile=RiskProfile(risk_codes=("high_altitude",)),
        references=(reference,),
        conversation_context=AgentConversationContext(
            template=_template(
                [
                    {
                        "block_key": "hazard_controls",
                        "section_code": "risk_identification",
                        "prototype_table_index": 4,
                    }
                ]
            )
        ),
    )

    result = compose_section(
        GeneratedSection(section_code=context.section_code, title="风险辨识"),
        context,
    )

    assert result.tables[0].rows == (
        ("高处坠落", "双钩安全带全程挂设", ""),
        ("工具坠落", "使用防坠绳", ""),
    )
    assert result.tables[0].source_chunk_ids == ("risk-table",)
    assert len(result.tables[0].missing_cells) == 2


def test_table_is_omitted_when_template_has_no_semantic_slot() -> None:
    context = SectionContext(
        section_code="organization_measures",
        objective="组织措施",
        confirmed_facts=(),
        risk_profile=RiskProfile(),
        conversation_context=AgentConversationContext(
            personnel=(PersonnelContext(id="7", name="脱敏人员"),),
            template=_template([]),
        ),
    )

    result = compose_section(
        GeneratedSection(section_code=context.section_code, title="组织措施"),
        context,
    )

    assert result.tables == ()
    assert result.composition_decisions[0].selected is False
    assert "模板" in result.composition_decisions[0].reason


def test_personnel_table_uses_explicit_role_assignment_from_frozen_prompt() -> None:
    context = SectionContext(
        section_code="organization_measures",
        objective="组织措施",
        confirmed_facts=(),
        risk_profile=RiskProfile(),
        conversation_context=AgentConversationContext(
            initial_message="项目负责人：脱敏人员；\n安全负责人：另一人员。",
            personnel=(PersonnelContext(id="7", name="脱敏人员"),),
            template=_template(
                [
                    {
                        "block_key": "personnel_information",
                        "section_code": "organization_measures",
                        "style_source": "approved_default_v1",
                        "headers": ["序号", "姓名", "岗位/职务"],
                    }
                ]
            ),
        ),
    )

    result = compose_section(
        GeneratedSection(section_code=context.section_code, title="组织措施"),
        context,
    )

    assert result.tables[0].rows == (("1", "脱敏人员", "项目负责人"),)
