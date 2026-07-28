from __future__ import annotations

import json
import re
from collections.abc import Sequence

from .contracts import (
    ENTRY_PLAN_SECTION_BLUEPRINTS,
    ENTRY_PLAN_SECTION_MIN_CHARACTERS,
    ENTRY_PLAN_SECTION_TITLES,
    ConfirmedFact,
    GeneratedSection,
    SectionContext,
    SourceCitation,
    ValidationIssue,
    ValidationSeverity,
)

FORBIDDEN_OUTPUT_MARKERS = (
    "经检测发现",
    "检测结果表明",
    "检测结论",
    "实测结果",
    "缺陷清单",
    "处理结果",
    "验收合格",
    "完工报告",
    "检测报告",
    "竣工资料",
)
PLANNING_MARKERS = ("计划", "拟", "预计", "安排", "范围", "入场", "涉及")
PLANNED_VALUE_FIELDS = frozenset(
    {
        "turbine_quantity",
        "inspection_quantity",
        "planned_start_date",
        "planned_end_date",
    }
)
NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?")
SUBHEADING_RE = re.compile(r"^(?:[（(][一二三四五六七八九十]+[）)]|[一二三四五六七八九十]+、)")
INTERNAL_CODE_LABELS = {
    "tower_weld": "塔筒焊缝",
    "high_strength_bolt": "高强度螺栓",
    "pitch_bearing": "变桨轴承",
    "blade_bolt": "叶片螺栓",
    "tower_component": "塔筒部件",
    "high_altitude": "高处作业",
    "climbing_tower": "攀爬塔筒",
    "mechanical_injury": "机械伤害",
    "vehicle_traffic": "车辆交通",
}


def section_text(section: GeneratedSection) -> str:
    parts = [section.title, *section.paragraphs]
    parts.extend(item for items in section.lists for item in items)
    parts.extend(
        cell for table in section.tables for row in (table.headers, *table.rows) for cell in row
    )
    return "\n".join(parts)


def _humanize_internal_codes(section: GeneratedSection) -> GeneratedSection:
    def humanize(text: str) -> str:
        for code, label in INTERNAL_CODE_LABELS.items():
            text = text.replace(f"（{code}）", "").replace(f"({code})", "")
            text = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(code)}(?![A-Za-z0-9_])",
                label,
                text,
            )
        return text

    return section.model_copy(
        update={
            "title": humanize(section.title),
            "paragraphs": tuple(humanize(paragraph) for paragraph in section.paragraphs),
            "lists": tuple(tuple(humanize(item) for item in items) for items in section.lists),
            "tables": tuple(
                table.model_copy(
                    update={
                        "headers": tuple(humanize(header) for header in table.headers),
                        "rows": tuple(tuple(humanize(cell) for cell in row) for row in table.rows),
                    }
                )
                for table in section.tables
            ),
        }
    )


def _value_text(fact: ConfirmedFact) -> str:
    if isinstance(fact.value, str):
        return fact.value
    if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool):
        return str(fact.value)
    return json.dumps(fact.value, ensure_ascii=False, sort_keys=True)


def _strip_unsupported_numeric_sentences(
    text: str,
    *,
    allowed_numbers: set[str],
) -> tuple[str, bool]:
    removed = False
    kept: list[str] = []
    for sentence in re.split(r"(?<=[。；！？\n])", text):
        unsupported = set(NUMBER_RE.findall(sentence)) - allowed_numbers
        if unsupported:
            removed = True
            continue
        kept.append(sentence)
    return "".join(kept).strip(), removed


def _strip_forbidden_sentences(text: str) -> tuple[str, bool]:
    removed = False
    kept: list[str] = []
    for sentence in re.split(r"(?<=[。；！？\n])", text):
        if any(marker in sentence for marker in FORBIDDEN_OUTPUT_MARKERS):
            removed = True
            continue
        kept.append(sentence)
    return "".join(kept).strip(), removed


def _contains_fact_value(text: str, fact: ConfirmedFact) -> bool:
    value_text = _value_text(fact)
    if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool):
        return value_text in NUMBER_RE.findall(text)
    return value_text in text


def _ensure_planning_language(
    text: str,
    *,
    planned_facts: Sequence[ConfirmedFact],
) -> tuple[str, bool]:
    if not any(_contains_fact_value(text, fact) for fact in planned_facts):
        return text, False
    if any(marker in text for marker in PLANNING_MARKERS):
        return text, False
    return f"计划{text}", True


def normalize_section_provenance(
    section: GeneratedSection,
    context: SectionContext,
) -> GeneratedSection:
    """Deterministically ground declared scalar facts and register exact fact provenance."""
    section = _humanize_internal_codes(section)
    facts_by_field = {fact.field: fact for fact in context.confirmed_facts}
    used_fields = list(dict.fromkeys(section.used_fact_fields))
    initial_text = section_text(section)
    scalar_fields_present = {
        fact.field
        for fact in context.confirmed_facts
        if not isinstance(fact.value, bool)
        and isinstance(fact.value, (str, int, float))
        and _value_text(fact) in initial_text
    }
    allowed_number_text = "\n".join(
        [
            *(
                _value_text(facts_by_field[field])
                for field in (*used_fields, *sorted(scalar_fields_present))
                if field in facts_by_field
            ),
            *(clause.text for clause in context.clauses),
        ]
    )
    allowed_numbers = set(NUMBER_RE.findall(allowed_number_text))
    numeric_content_removed = False
    forbidden_content_removed = False
    paragraphs: list[str] = []
    for paragraph in section.paragraphs:
        cleaned, forbidden_removed = _strip_forbidden_sentences(paragraph)
        cleaned, numeric_removed = _strip_unsupported_numeric_sentences(
            cleaned,
            allowed_numbers=allowed_numbers,
        )
        forbidden_content_removed = forbidden_content_removed or forbidden_removed
        numeric_content_removed = numeric_content_removed or numeric_removed
        if cleaned:
            paragraphs.append(cleaned)
    generated_lists: list[tuple[str, ...]] = []
    for items in section.lists:
        forbidden_items = {
            item for item in items if any(marker in item for marker in FORBIDDEN_OUTPUT_MARKERS)
        }
        unsupported_numeric_items = {
            item
            for item in items
            if item not in forbidden_items and bool(set(NUMBER_RE.findall(item)) - allowed_numbers)
        }
        kept_items = tuple(
            item
            for item in items
            if item not in forbidden_items and item not in unsupported_numeric_items
        )
        forbidden_content_removed = forbidden_content_removed or bool(forbidden_items)
        numeric_content_removed = numeric_content_removed or bool(unsupported_numeric_items)
        if kept_items:
            generated_lists.append(kept_items)
    generated_tables = []
    for table in section.tables:
        if any(
            any(marker in header for marker in FORBIDDEN_OUTPUT_MARKERS) for header in table.headers
        ):
            forbidden_content_removed = True
            continue
        if any(set(NUMBER_RE.findall(header)) - allowed_numbers for header in table.headers):
            numeric_content_removed = True
            continue
        forbidden_rows = {
            row
            for row in table.rows
            if any(any(marker in cell for marker in FORBIDDEN_OUTPUT_MARKERS) for cell in row)
        }
        unsupported_numeric_rows = {
            row
            for row in table.rows
            if row not in forbidden_rows
            and any(set(NUMBER_RE.findall(cell)) - allowed_numbers for cell in row)
        }
        kept_rows = tuple(
            row
            for row in table.rows
            if row not in forbidden_rows and row not in unsupported_numeric_rows
        )
        forbidden_content_removed = forbidden_content_removed or bool(forbidden_rows)
        numeric_content_removed = numeric_content_removed or bool(unsupported_numeric_rows)
        generated_tables.append(table.model_copy(update={"rows": kept_rows}))
    planned_facts = tuple(
        fact for fact in context.confirmed_facts if fact.field in PLANNED_VALUE_FIELDS
    )
    planning_language_added = False
    planned_paragraphs: list[str] = []
    for paragraph in paragraphs:
        planned_sentences: list[str] = []
        for sentence in re.split(r"(?<=[。；！？\n])", paragraph):
            normalized_sentence, changed = _ensure_planning_language(
                sentence,
                planned_facts=planned_facts,
            )
            planning_language_added = planning_language_added or changed
            planned_sentences.append(normalized_sentence)
        planned_paragraphs.append("".join(planned_sentences))
    paragraphs = planned_paragraphs
    planned_lists: list[tuple[str, ...]] = []
    for items in generated_lists:
        planned_items = []
        for item in items:
            normalized_item, changed = _ensure_planning_language(
                item,
                planned_facts=planned_facts,
            )
            planning_language_added = planning_language_added or changed
            planned_items.append(normalized_item)
        planned_lists.append(tuple(planned_items))
    generated_lists = planned_lists
    planned_tables = []
    for table in generated_tables:
        planned_headers = []
        for header in table.headers:
            normalized_header, changed = _ensure_planning_language(
                header,
                planned_facts=planned_facts,
            )
            planning_language_added = planning_language_added or changed
            planned_headers.append(normalized_header)
        planned_rows = []
        for row in table.rows:
            planned_row = []
            for cell in row:
                normalized_cell, changed = _ensure_planning_language(
                    cell,
                    planned_facts=planned_facts,
                )
                planning_language_added = planning_language_added or changed
                planned_row.append(normalized_cell)
            planned_rows.append(tuple(planned_row))
        planned_tables.append(
            table.model_copy(
                update={
                    "headers": tuple(planned_headers),
                    "rows": tuple(planned_rows),
                }
            )
        )
    generated_tables = planned_tables
    controlled_title = ENTRY_PLAN_SECTION_TITLES.get(
        section.section_code,
        section.title,
    )
    title, title_changed = _ensure_planning_language(
        controlled_title,
        planned_facts=planned_facts,
    )
    planning_language_added = planning_language_added or title_changed
    warnings = list(section.warnings)
    missing_items = list(section.missing_items)
    if numeric_content_removed:
        warning = "已确定性移除未经当前项目确认或批准条款支持的数值信息"
        if warning not in warnings:
            warnings.append(warning)
        missing = "被移除数值的当前项目依据需由技术负责人补充确认"
        if missing not in missing_items:
            missing_items.append(missing)
    if forbidden_content_removed:
        warning = "已确定性移除不属于入场计划的完工或报告语义"
        if warning not in warnings:
            warnings.append(warning)
        missing = "被移除内容如涉及入场计划，应由技术负责人按入场语义重新表述"
        if missing not in missing_items:
            missing_items.append(missing)
    if planning_language_added:
        warning = "已将确认数量或日期统一标注为入场前计划信息"
        if warning not in warnings:
            warnings.append(warning)
    section = section.model_copy(
        update={
            "title": title,
            "paragraphs": tuple(paragraphs),
            "lists": tuple(generated_lists),
            "tables": tuple(generated_tables),
            "warnings": tuple(warnings),
            "missing_items": tuple(missing_items),
        }
    )
    paragraphs = list(section.paragraphs)
    text = section_text(section)
    for field in used_fields:
        fact = facts_by_field.get(field)
        if (
            fact is None
            or isinstance(fact.value, bool)
            or not isinstance(fact.value, (str, int, float))
        ):
            continue
        value_text = _value_text(fact)
        if value_text not in text:
            grounded_sentence = f"当前项目计划确认信息：{value_text}"
            paragraphs.append(grounded_sentence)
            text = f"{text}\n{grounded_sentence}"
    for fact in context.confirmed_facts:
        if isinstance(fact.value, bool) or not isinstance(fact.value, (str, int, float)):
            continue
        if _value_text(fact) in text and fact.field not in used_fields:
            used_fields.append(fact.field)

    citations = list(section.citations)
    for field in used_fields:
        fact = facts_by_field.get(field)
        if fact is None:
            continue
        if any(
            citation.fact_field == field
            and citation.source_document_version_id == fact.source_document_version_id
            and citation.locator == fact.locator
            for citation in citations
        ):
            continue
        citations.append(
            SourceCitation(
                source_document_version_id=fact.source_document_version_id,
                locator=fact.locator,
                fact_field=field,
            )
        )
    return section.model_copy(
        update={
            "paragraphs": tuple(paragraphs),
            "used_fact_fields": tuple(used_fields),
            "citations": tuple(citations),
        }
    )


class ControlledSectionValidator:
    def __init__(self, *, historical_entity_blacklist: Sequence[str] = ()) -> None:
        self.historical_entity_blacklist = tuple(
            sorted({value.strip() for value in historical_entity_blacklist if value.strip()})
        )

    def validate(
        self,
        section: GeneratedSection,
        context: SectionContext,
    ) -> Sequence[ValidationIssue]:
        issues: list[ValidationIssue] = []
        text = section_text(section)
        if not section.paragraphs and not section.lists and not section.tables:
            issues.append(
                self._error(
                    "SECTION_CONTENT_EMPTY",
                    "生成章节没有正文内容",
                    context,
                )
            )
        if section.section_code != context.section_code:
            issues.append(self._error("SECTION_CODE_MISMATCH", "章节编码与上下文不一致", context))

        if context.objective.startswith("质量结构要求："):
            minimum_characters = ENTRY_PLAN_SECTION_MIN_CHARACTERS.get(context.section_code)
            content_character_count = len(re.sub(r"\s+", "", text))
            if minimum_characters is not None and content_character_count < minimum_characters:
                issues.append(
                    self._error(
                        "SECTION_CONTENT_TOO_SHORT",
                        (
                            f"章节有效内容仅{content_character_count}字，"
                            f"最低完整度要求为{minimum_characters}字"
                        ),
                        context,
                    )
                )
            expected_topic_count = len(ENTRY_PLAN_SECTION_BLUEPRINTS.get(context.section_code, ()))
            subheading_count = sum(
                bool(SUBHEADING_RE.match(paragraph.strip())) for paragraph in section.paragraphs
            )
            if expected_topic_count and subheading_count < expected_topic_count:
                issues.append(
                    self._error(
                        "SECTION_STRUCTURE_INCOMPLETE",
                        (
                            f"章节仅包含{subheading_count}个规范小节标题，"
                            f"应覆盖{expected_topic_count}个章节要点"
                        ),
                        context,
                    )
                )

        for marker in FORBIDDEN_OUTPUT_MARKERS:
            if marker in text:
                issues.append(
                    self._error(
                        "RESULT_CONTENT_FORBIDDEN",
                        (
                            f"章节正文命中禁用词“{marker}”；"
                            "必须删除包含该词的整句，仅保留入场前计划内容"
                        ),
                        context,
                    )
                )
                break

        for entity in self.historical_entity_blacklist:
            if entity in text:
                issues.append(
                    self._error(
                        "HISTORICAL_ENTITY_LEAKAGE",
                        "生成章节包含历史项目专有信息",
                        context,
                    )
                )
                break

        facts_by_field = {fact.field: fact for fact in context.confirmed_facts}
        used_fields = set(section.used_fact_fields)
        unknown_fields = sorted(used_fields - facts_by_field.keys())
        if unknown_fields:
            issues.append(
                self._error(
                    "UNCONFIRMED_FACT_USED",
                    f"章节引用了未确认字段：{','.join(unknown_fields)}",
                    context,
                )
            )
        for field in sorted(used_fields & facts_by_field.keys()):
            fact = facts_by_field[field]
            citation_matches = any(
                citation.fact_field == field
                and citation.source_document_version_id == fact.source_document_version_id
                and citation.locator == fact.locator
                for citation in section.citations
            )
            if not citation_matches:
                issues.append(
                    self._error(
                        "FACT_CITATION_MISSING",
                        f"字段 {field} 缺少精确来源引用",
                        context,
                    )
                )
            value_text = _value_text(fact)
            if isinstance(fact.value, (str, int, float)) and value_text not in text:
                issues.append(
                    self._error(
                        "FACT_VALUE_NOT_RENDERED",
                        f"字段 {field} 的确认值未出现在章节中",
                        context,
                    )
                )
        for field in sorted(facts_by_field.keys() - used_fields):
            fact = facts_by_field[field]
            if not isinstance(fact.value, (str, int, float)) or isinstance(fact.value, bool):
                continue
            value_text = _value_text(fact)
            if value_text and value_text in text:
                issues.append(
                    self._error(
                        "UNDECLARED_FACT_USAGE",
                        f"字段 {field} 已写入正文但未登记事实引用",
                        context,
                    )
                )

        expected_clauses = {clause.clause_id: clause for clause in context.clauses}
        used_clause_ids = set(section.used_clause_ids)
        unexpected_clause_ids = sorted(used_clause_ids - expected_clauses.keys())
        if unexpected_clause_ids:
            issues.append(
                self._error(
                    "UNAPPROVED_CLAUSE_USED",
                    f"模型引用了未批准条款：{','.join(unexpected_clause_ids)}",
                    context,
                )
            )
        missing_clause_ids = sorted(expected_clauses.keys() - used_clause_ids)
        if missing_clause_ids:
            issues.append(
                self._error(
                    "REQUIRED_CLAUSE_MISSING",
                    f"缺少确定性条款：{','.join(missing_clause_ids)}",
                    context,
                )
            )
        for clause_id in sorted(expected_clauses.keys() & used_clause_ids):
            if expected_clauses[clause_id].text not in text:
                issues.append(
                    self._error(
                        "CLAUSE_TEXT_CHANGED",
                        f"条款 {clause_id} 未按批准文本原样保留",
                        context,
                    )
                )

        allowed_number_text = "\n".join(
            [
                *(
                    _value_text(facts_by_field[field])
                    for field in sorted(used_fields & facts_by_field.keys())
                ),
                *(clause.text for clause in context.clauses),
            ]
        )
        allowed_numbers = set(NUMBER_RE.findall(allowed_number_text))
        unsupported_numbers = sorted(set(NUMBER_RE.findall(text)) - allowed_numbers)
        if unsupported_numbers:
            issues.append(
                self._error(
                    "UNSOURCED_NUMBER",
                    f"章节包含无来源数字：{','.join(unsupported_numbers)}",
                    context,
                )
            )

        for fact in context.confirmed_facts:
            if fact.field not in PLANNED_VALUE_FIELDS:
                continue
            for sentence in re.split(r"[。；\n]", text):
                if _contains_fact_value(sentence, fact) and not any(
                    marker in sentence for marker in PLANNING_MARKERS
                ):
                    issues.append(
                        self._error(
                            "PLANNING_LANGUAGE_REQUIRED",
                            f"字段 {fact.field} 必须表达为计划范围或入场安排",
                            context,
                        )
                    )
                    break

        if not context.references:
            issues.append(
                ValidationIssue(
                    code="RETRIEVAL_EMPTY",
                    message="当前章节没有可用历史参考，已仅按确认事实和批准条款生成",
                    severity=ValidationSeverity.WARNING,
                    section_code=context.section_code,
                )
            )
        return tuple(issues)

    @staticmethod
    def _error(
        code: str,
        message: str,
        context: SectionContext,
    ) -> ValidationIssue:
        return ValidationIssue(
            code=code,
            message=message,
            severity=ValidationSeverity.ERROR,
            section_code=context.section_code,
        )


def fact_citation_coverage(
    sections: Sequence[GeneratedSection],
    facts: Sequence[ConfirmedFact],
) -> float:
    facts_by_field = {fact.field: fact for fact in facts}
    used = [
        (section, field)
        for section in sections
        for field in section.used_fact_fields
        if field in facts_by_field
    ]
    if not used:
        return 1.0
    cited = 0
    for section, field in used:
        fact = facts_by_field[field]
        cited += any(
            citation.fact_field == field
            and citation.source_document_version_id == fact.source_document_version_id
            and citation.locator == fact.locator
            for citation in section.citations
        )
    return cited / len(used)
