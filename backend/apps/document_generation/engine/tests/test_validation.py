from __future__ import annotations

from apps.document_generation.engine.contracts import (
    AgentConversationContext,
    AgentTemplateContext,
    ClauseSelection,
    ConfirmedFact,
    GeneratedSection,
    PersonnelContext,
    RetrievalQuery,
    RetrievalResult,
    RiskProfile,
    SectionContext,
    SourceCitation,
    SourceLocator,
    ValidationSeverity,
)
from apps.document_generation.engine.sections import SectionContextBuilder
from apps.document_generation.engine.validation import (
    ControlledSectionValidator,
    fact_citation_coverage,
    normalize_section_provenance,
)


def _fact(
    field: str,
    value: object,
    paragraph_index: int,
) -> ConfirmedFact:
    return ConfirmedFact(
        field=field,
        value=value,
        value_type="string",
        source_document_version_id=134,
        locator=SourceLocator(paragraph_index=paragraph_index),
        confidence=1,
        confirmed_by=7,
    )


def _clause() -> ClauseSelection:
    return ClauseSelection(
        clause_id="M001",
        clause_code="FMTP-SAFE-HIGH-ALTITUDE",
        clause_version="internal-baseline-v1",
        section_code="safety_measures",
        text="入场前应确认高处作业许可和防坠落安排",
        matched_risk_codes=("high_altitude",),
    )


def _context(*, with_reference: bool = False) -> SectionContext:
    facts = (
        _fact("site_name", "当前风电场", 1),
        _fact("inspection_quantity", 12, 2),
    )
    query = RetrievalQuery(
        business_type="wind_turbine_inspection_four_measures_two_plans",
        section_code="safety_measures",
        query_text="高处作业",
    )
    retrieval = RetrievalResult(
        query=query,
        embedding_model_alias="fake",
        embedding_dimension=1,
    )
    return SectionContext(
        section_code="safety_measures",
        objective="编写安全措施",
        confirmed_facts=facts,
        risk_profile=RiskProfile(risk_codes=("high_altitude",)),
        clauses=(_clause(),),
        references=retrieval.sections if with_reference else (),
    )


def _valid_section() -> GeneratedSection:
    context = _context()
    return GeneratedSection(
        section_code="safety_measures",
        title="安全措施",
        paragraphs=(
            "本次入场计划在当前风电场开展工作，计划涉及12项检测。",
            context.clauses[0].text,
        ),
        citations=tuple(
            SourceCitation(
                source_document_version_id=fact.source_document_version_id,
                locator=fact.locator,
                fact_field=fact.field,
            )
            for fact in context.confirmed_facts
        ),
        used_fact_fields=("site_name", "inspection_quantity"),
        used_clause_ids=("M001",),
    )


def _error_codes(section: GeneratedSection, *, blacklist=()) -> set[str]:
    issues = ControlledSectionValidator(historical_entity_blacklist=blacklist).validate(
        section, _context()
    )
    return {issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR}


def test_valid_section_has_full_fact_coverage_and_empty_rag_is_only_warning() -> None:
    section = _valid_section()
    issues = ControlledSectionValidator().validate(section, _context())

    assert not [issue for issue in issues if issue.severity == ValidationSeverity.ERROR]
    assert [issue.code for issue in issues] == ["RETRIEVAL_EMPTY"]
    assert fact_citation_coverage((section,), _context().confirmed_facts) == 1.0


def test_validator_rejects_unconfirmed_values_and_model_added_clause() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "本次入场计划在当前风电场开展工作，计划涉及99项检测。",
                _clause().text,
            ),
            "used_clause_ids": ("M001", "MODEL-ADDED"),
        }
    )

    codes = _error_codes(section)

    assert "FACT_VALUE_NOT_RENDERED" in codes
    assert "UNSOURCED_NUMBER" in codes
    assert "UNAPPROVED_CLAUSE_USED" in codes


def test_validator_rejects_changed_or_missing_approved_clause() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": ("本次入场计划在当前风电场开展工作，计划涉及12项检测。",),
            "used_clause_ids": (),
        }
    )

    assert "REQUIRED_CLAUSE_MISSING" in _error_codes(section)


def test_validator_rejects_fact_value_written_without_provenance_declaration() -> None:
    section = _valid_section().model_copy(
        update={
            "used_fact_fields": ("inspection_quantity",),
            "citations": tuple(
                citation
                for citation in _valid_section().citations
                if citation.fact_field == "inspection_quantity"
            ),
        }
    )

    assert "UNDECLARED_FACT_USAGE" in _error_codes(section)


def test_normalizer_registers_confirmed_scalar_already_present_in_text() -> None:
    section = _valid_section().model_copy(
        update={
            "used_fact_fields": ("inspection_quantity",),
            "citations": tuple(
                citation
                for citation in _valid_section().citations
                if citation.fact_field == "inspection_quantity"
            ),
        }
    )

    normalized = normalize_section_provenance(section, _context())

    assert normalized.used_fact_fields == ("inspection_quantity", "site_name")
    assert {citation.fact_field for citation in normalized.citations} == {
        "inspection_quantity",
        "site_name",
    }
    assert "UNDECLARED_FACT_USAGE" not in _error_codes(normalized)


def test_normalizer_appends_exact_confirmed_value_for_declared_scalar() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": ("按当前项目要求组织入场。", _clause().text),
            "used_fact_fields": ("site_name",),
            "citations": (),
        }
    )

    normalized = normalize_section_provenance(section, _context())

    assert normalized.paragraphs[-1] == "当前项目计划确认信息：当前风电场"
    assert {citation.fact_field for citation in normalized.citations} == {"site_name"}
    assert "FACT_VALUE_NOT_RENDERED" not in _error_codes(normalized)


def test_normalizer_removes_unsourced_numeric_threshold_and_records_gap() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "本次入场计划在当前风电场开展工作，计划涉及12项检测。",
                "风速达到18m/s时停止作业。",
                _clause().text,
            )
        }
    )

    normalized = normalize_section_provenance(section, _context())

    assert all("18" not in paragraph for paragraph in normalized.paragraphs)
    assert any("确定性移除" in warning for warning in normalized.warnings)
    assert any("技术负责人" in item for item in normalized.missing_items)
    assert "UNSOURCED_NUMBER" not in _error_codes(normalized)


def test_revision_keeps_reviewer_confirmed_personnel_literals_and_verifies_change() -> None:
    original = _valid_section()
    context = _context().model_copy(
        update={
            "revision_instruction": "在岗位职责中加入张三，12345678。",
            "revision_required_literals": ("张三", "12345678"),
            "previous_content": "\n".join(original.paragraphs),
        }
    )
    revised = original.model_copy(
        update={
            "paragraphs": (
                *original.paragraphs,
                "张三负责现场协调，人员编号为12345678。",
            )
        }
    )

    normalized = normalize_section_provenance(revised, context)
    issues = ControlledSectionValidator().validate(normalized, context)
    error_codes = {issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR}

    assert "12345678" in "\n".join(normalized.paragraphs)
    assert "UNSOURCED_NUMBER" not in error_codes
    assert "REVISION_LITERAL_MISSING" not in error_codes
    assert "REVISION_CONTENT_UNCHANGED" not in error_codes


def test_revision_rejects_unchanged_content_and_missing_required_literals() -> None:
    original = _valid_section()
    context = _context().model_copy(
        update={
            "revision_instruction": "在岗位职责中加入张三，12345678。",
            "revision_required_literals": ("张三", "12345678"),
            "previous_content": "\n".join(original.paragraphs),
        }
    )

    issues = ControlledSectionValidator().validate(original, context)
    error_codes = {issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR}

    assert "REVISION_CONTENT_UNCHANGED" in error_codes
    assert "REVISION_LITERAL_MISSING" in error_codes


def test_normalizer_removes_forbidden_result_sentence_before_validation() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "本次入场计划在当前风电场开展工作，计划涉及12项检测。",
                "本章不形成检测结论。",
                _clause().text,
            )
        }
    )

    normalized = normalize_section_provenance(section, _context())

    assert all("检测结论" not in paragraph for paragraph in normalized.paragraphs)
    assert any("确定性移除" in warning for warning in normalized.warnings)
    assert "RESULT_CONTENT_FORBIDDEN" not in _error_codes(normalized)


def test_normalizer_marks_every_confirmed_quantity_use_as_planned() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "当前风电场检测数量为12项。",
                _clause().text,
            ),
        }
    )

    normalized = normalize_section_provenance(section, _context())

    assert normalized.paragraphs[0] == "计划当前风电场检测数量为12项。"
    assert any("入场前计划信息" in warning for warning in normalized.warnings)
    assert "PLANNING_LANGUAGE_REQUIRED" not in _error_codes(normalized)


def test_normalizer_uses_controlled_entry_plan_section_title() -> None:
    section = _valid_section().model_copy(update={"title": "入场前计划"})

    normalized = normalize_section_provenance(section, _context())

    assert normalized.title == "安全措施"


def test_normalizer_humanizes_internal_component_and_risk_codes() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "塔筒焊缝（tower_weld）采用计划控制。",
                "high_altitude与climbing_tower风险应落实监护。",
            ),
        }
    )

    normalized = normalize_section_provenance(section, _context())
    text = "\n".join(normalized.paragraphs)

    assert "tower_weld" not in text
    assert "high_altitude" not in text
    assert "climbing_tower" not in text
    assert "塔筒焊缝" in text
    assert "高处作业与攀爬塔筒" in text


def test_planned_integer_does_not_match_digits_inside_another_number() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "本次入场计划在当前风电场开展工作，计划涉及12项检测。",
                "执行标准编号含2012版标识。",
                _clause().text,
            ),
        }
    )

    codes = _error_codes(section)

    assert "PLANNING_LANGUAGE_REQUIRED" not in codes


def test_validator_rejects_empty_section() -> None:
    section = GeneratedSection(
        section_code="safety_measures",
        title="安全措施",
        used_clause_ids=("M001",),
    )

    assert "SECTION_CONTENT_EMPTY" in _error_codes(section)


def test_validator_rejects_historical_entity_result_language_and_completed_quantity() -> None:
    section = _valid_section().model_copy(
        update={
            "paragraphs": (
                "历史风电场经检测发现12项缺陷。",
                _clause().text,
            )
        }
    )

    validator = ControlledSectionValidator(historical_entity_blacklist=("历史风电场",))
    issues = validator.validate(section, _context())
    codes = {issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR}

    assert "HISTORICAL_ENTITY_LEAKAGE" in codes
    assert "RESULT_CONTENT_FORBIDDEN" in codes
    assert "PLANNING_LANGUAGE_REQUIRED" in codes
    result_issue = next(issue for issue in issues if issue.code == "RESULT_CONTENT_FORBIDDEN")
    assert "经检测发现" in result_issue.message


def test_quality_context_rejects_short_and_unstructured_section() -> None:
    base_context = _context()
    retrieval = RetrievalResult(
        query=RetrievalQuery(
            business_type="wind_turbine_inspection_four_measures_two_plans",
            section_code="safety_measures",
            query_text="安全措施",
        ),
        embedding_model_alias="fake",
        embedding_dimension=1,
    )
    quality_context = SectionContextBuilder().build(
        section_code="safety_measures",
        confirmed_facts=base_context.confirmed_facts,
        risk_profile=base_context.risk_profile,
        clauses=base_context.clauses,
        retrieval=retrieval,
    )

    issues = ControlledSectionValidator().validate(_valid_section(), quality_context)
    codes = {issue.code for issue in issues if issue.severity == ValidationSeverity.ERROR}

    assert "必须覆盖：" in quality_context.objective
    assert "写作目标不少于3250个中文字符" in quality_context.objective
    assert "确定性最低门禁为2600个中文字符" in quality_context.objective
    assert "SECTION_CONTENT_TOO_SHORT" in codes
    assert "SECTION_STRUCTURE_INCOMPLETE" in codes


def test_section_context_includes_personnel_and_locked_template_constraints() -> None:
    base_context = _context()
    retrieval = RetrievalResult(
        query=RetrievalQuery(
            business_type="wind_turbine_inspection_four_measures_two_plans",
            section_code="organization_measures",
            query_text="组织措施",
        ),
        embedding_model_alias="fake",
        embedding_dimension=1,
    )
    conversation_context = AgentConversationContext(
        initial_message="重点核对人员分工",
        personnel=(PersonnelContext(id="8", name="项目成员", job_title="资料整理员"),),
        template=AgentTemplateContext(
            id="3",
            code="T001",
            name="甲方四措两案模板",
            filename="template.docx",
            version="v1",
            document_version_id=10,
        ),
    )

    context = SectionContextBuilder().build(
        section_code="organization_measures",
        confirmed_facts=base_context.confirmed_facts,
        risk_profile=base_context.risk_profile,
        clauses=base_context.clauses,
        retrieval=retrieval,
        conversation_context=conversation_context,
    )

    assert context.conversation_context.personnel[0].name == "项目成员"
    assert context.conversation_context.template is not None
    assert context.conversation_context.template.format_locked is True
    assert "严格使用当前批准模板" in context.objective
