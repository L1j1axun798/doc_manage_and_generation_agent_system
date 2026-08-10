from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

from .contracts import (
    CompositionDecision,
    GeneratedSection,
    GeneratedTable,
    RetrievedSection,
    SectionContext,
)


TABLE_TITLES = {
    "personnel_information": "作业人员信息表",
    "hazard_controls": "现场危险源及控制措施表",
    "work_process_points": "作业工序和具体检测点项表",
    "inspection_tools": "检测工具清单",
    "safety_equipment": "安全器材表",
    "ppe_items": "检测人员劳保清单",
}

SECTION_TABLE_PRIORITY = {
    "organization_measures": ("personnel_information",),
    "risk_identification": ("hazard_controls",),
    "construction_plan": ("work_process_points",),
    "technical_measures": ("inspection_tools",),
    "safety_measures": ("safety_equipment", "ppe_items"),
}

CORE_TERMS = {
    "personnel_information": (("姓名", "人员"),),
    "hazard_controls": (("危险源", "危险点", "风险"), ("控制措施", "预控措施", "措施")),
    "work_process_points": (
        ("工序", "步骤", "检测项目"),
        ("检测点", "检测项目", "检查项目", "点项", "检测要求"),
    ),
    "inspection_tools": (("工具", "仪器", "设备", "名称"),),
    "safety_equipment": (("器材", "工器具", "名称"),),
    "ppe_items": (("劳保", "防护用品", "名称"),),
}

PROJECT_SPECIFIC_TERMS = (
    "数量",
    "设备编号",
    "仪器编号",
    "编号",
    "检验日期",
    "校验日期",
    "责任人",
    "备注",
)


def _slots(context: SectionContext) -> list[dict[str, object]]:
    template = context.conversation_context.template
    schema = template.layout_schema if template is not None else {}
    values = schema.get("table_slots", []) if isinstance(schema, Mapping) else []
    return [dict(value) for value in values if isinstance(value, Mapping)]


def _slot_for(context: SectionContext, block_key: str) -> dict[str, object] | None:
    return next(
        (
            slot
            for slot in _slots(context)
            if slot.get("block_key") == block_key
            and slot.get("section_code") == context.section_code
        ),
        None,
    )


def _table_rows(reference: RetrievedSection) -> tuple[tuple[str, ...], ...]:
    if reference.block_type == "table" and reference.structured_rows:
        return reference.structured_rows
    lines = [line.strip() for line in reference.text.splitlines() if line.strip()]
    if len(lines) < 2 or not all(" | " in line for line in lines):
        return ()
    rows = tuple(tuple(cell.strip() for cell in line.split(" | ")) for line in lines)
    return rows if len({len(row) for row in rows}) == 1 else ()


def _matches_key(block_key: str, headers: Sequence[str]) -> bool:
    joined = " ".join(headers)
    groups = CORE_TERMS[block_key]
    return all(any(term in joined for term in group) for group in groups)


def _core_indexes(block_key: str, headers: Sequence[str]) -> tuple[int, ...]:
    indexes: list[int] = []
    for terms in CORE_TERMS[block_key]:
        index = next(
            (idx for idx, header in enumerate(headers) if any(term in header for term in terms)),
            -1,
        )
        if index < 0:
            return ()
        indexes.append(index)
    return tuple(indexes)


def _clean_reference_rows(
    block_key: str,
    rows: Sequence[Sequence[str]],
) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]:
    if len(rows) < 2:
        return (), ()
    headers = tuple(" ".join(value.split()) for value in rows[0])
    if not headers or not _matches_key(block_key, headers):
        return (), ()
    core_indexes = _core_indexes(block_key, headers)
    if not core_indexes:
        return (), ()
    specific_indexes = {
        index
        for index, header in enumerate(headers)
        if any(term in header for term in PROJECT_SPECIFIC_TERMS)
    }
    clean_rows: list[tuple[str, ...]] = []
    missing_cells: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for source_row in rows[1:]:
        if len(source_row) != len(headers):
            continue
        values = [" ".join(str(value).split()) for value in source_row]
        for index in specific_indexes:
            values[index] = ""
        row = tuple(values)
        if any(not row[index] for index in core_indexes) or row in seen:
            continue
        seen.add(row)
        row_number = len(clean_rows) + 1
        for index in specific_indexes:
            missing_cells.append(f"{TABLE_TITLES[block_key]}：第{row_number}行“{headers[index]}”")
        clean_rows.append(row)
    return tuple(clean_rows), tuple(missing_cells)


def _personnel_table(context: SectionContext, slot: Mapping[str, object]) -> GeneratedTable | None:
    people = context.conversation_context.personnel
    if not people:
        return None
    configured_headers = slot.get("headers")
    headers = (
        tuple(str(value).strip() for value in configured_headers)
        if isinstance(configured_headers, list) and configured_headers
        else ("序号", "姓名", "岗位/职务", "联系电话", "证书及有效期")
    )
    rows: list[tuple[str, ...]] = []
    missing: list[str] = []
    for number, person in enumerate(people, start=1):
        prompt_role = _personnel_role_from_prompt(
            context.conversation_context.initial_message,
            person.name,
        )
        certificate_text = "；".join(
            f"{item.name} {item.certificate_number}"
            + (f"（有效期至{item.valid_until}）" if item.valid_until else "")
            for item in person.certifications
            if item.name and item.certificate_number
        )
        values: list[str] = []
        for header in headers:
            if "序" in header:
                value = str(number)
            elif "姓名" in header or "人员" in header:
                value = person.name
            elif "岗位" in header or "职务" in header or "工种" in header:
                value = person.job_title or prompt_role
            elif "部门" in header or "单位" in header:
                value = person.department
            elif "性别" in header:
                value = {"male": "男", "female": "女"}.get(person.gender, "")
            elif "身份证" in header:
                value = person.id_card_number
            elif "电话" in header or "联系" in header:
                value = person.phone or person.contact
            elif "证" in header or "资质" in header:
                value = certificate_text
            else:
                value = ""
            if not value and not ("姓名" in header or "人员" in header):
                missing.append(f"作业人员信息表：第{number}行“{header}”")
            values.append(value)
        if any(values):
            rows.append(tuple(values))
    return GeneratedTable(
        block_key="personnel_information",
        title=TABLE_TITLES["personnel_information"],
        insertion_reason=(
            "使用当前任务冻结的所选人员快照及用户明确岗位分工，"
            "且模板存在经过验证的人员表语义位置"
        ),
        headers=headers,
        rows=tuple(rows),
        missing_cells=tuple(missing),
        prototype_table_index=_as_non_negative_int(slot.get("prototype_table_index")),
    )


def _personnel_role_from_prompt(message: str, personnel_name: str) -> str:
    if not message.strip() or not personnel_name.strip():
        return ""
    name_pattern = re.escape(personnel_name.strip())
    for raw_line in message.splitlines():
        line = raw_line.strip().lstrip("-•* ")
        match = re.match(
            rf"(?P<role>[^：:]{{1,30}})[：:]\s*{name_pattern}(?:\s*[；;，,。]|\s*$)",
            line,
        )
        if match:
            return " ".join(match.group("role").split())
    return ""


def _as_non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _reference_table(
    context: SectionContext,
    block_key: str,
    slot: Mapping[str, object],
) -> GeneratedTable | None:
    candidates: list[tuple[int, RetrievedSection, tuple[tuple[str, ...], ...], tuple[str, ...]]] = []
    active_risks = set(context.risk_profile.risk_codes)
    for reference in context.references:
        raw_rows = _table_rows(reference)
        clean_rows, missing = _clean_reference_rows(block_key, raw_rows)
        if len(clean_rows) < 2:
            continue
        if block_key == "hazard_controls" and reference.risk_tags:
            if not active_risks.intersection(reference.risk_tags):
                continue
        score = len(clean_rows) * 10 + len(reference.component_tags) + len(reference.method_tags)
        candidates.append((score, reference, clean_rows, missing))
    if not candidates:
        return None
    _score, reference, rows, missing = max(candidates, key=lambda item: item[0])
    headers = _table_rows(reference)[0]
    return GeneratedTable(
        block_key=block_key,
        title=TABLE_TITLES[block_key],
        insertion_reason="结构化RAG表格与当前章节和风险/检测语境匹配，且有效内容不少于两行",
        source_chunk_ids=(reference.chunk_id,),
        missing_cells=missing,
        prototype_table_index=_as_non_negative_int(slot.get("prototype_table_index")),
        headers=headers,
        rows=rows,
    )


def compose_section(section: GeneratedSection, context: SectionContext) -> GeneratedSection:
    """Select grounded structured blocks without asking the model to control layout."""

    configured_keys = tuple(
        str(slot.get("block_key"))
        for slot in _slots(context)
        if slot.get("section_code") == context.section_code and slot.get("block_key")
    )
    keys = configured_keys or SECTION_TABLE_PRIORITY.get(context.section_code, ())
    selected: list[GeneratedTable] = []
    decisions: list[CompositionDecision] = []
    missing_items = list(section.missing_items)
    for block_key in keys:
        slot = _slot_for(context, block_key)
        if slot is None:
            decisions.append(
                CompositionDecision(
                    block_key=block_key,
                    block_type="table",
                    selected=False,
                    reason="当前模板没有经过语义识别的可复用表格位置",
                )
            )
            continue
        table = (
            _personnel_table(context, slot)
            if block_key == "personnel_information"
            else _reference_table(context, block_key, slot)
        )
        if table is None:
            decisions.append(
                CompositionDecision(
                    block_key=block_key,
                    block_type="table",
                    selected=False,
                    reason=(
                        "当前任务未选择人员"
                        if block_key == "personnel_information"
                        else "没有找到核心字段完整、至少两行且与当前任务适用的结构化RAG表格"
                    ),
                )
            )
            continue
        selected.append(table)
        missing_items.extend(item for item in table.missing_cells if item not in missing_items)
        decisions.append(
            CompositionDecision(
                block_key=block_key,
                block_type="table",
                selected=True,
                reason=table.insertion_reason,
                source_chunk_ids=table.source_chunk_ids,
                missing_items=table.missing_cells,
            )
        )
    image_decisions: list[CompositionDecision] = []
    template = context.conversation_context.template
    if context.section_code == "emergency_plan" and template is not None:
        image_slots = template.layout_schema.get("image_slots", [])
        for slot in image_slots if isinstance(image_slots, list) else []:
            if not isinstance(slot, Mapping) or slot.get("section_code") != "emergency_plan":
                continue
            block_key = str(slot.get("block_key") or "").strip()
            if block_key:
                image_decisions.append(
                    CompositionDecision(
                        block_key=block_key,
                        block_type="image",
                        selected=False,
                        reason="尚未由用户确认路线或从管理员审核图库选择适用图片",
                    )
                )
    return section.model_copy(
        update={
            "tables": tuple(selected),
            "composition_decisions": tuple(
                [
                    decision
                    for decision in section.composition_decisions
                    if decision.block_type not in {"table", "image"}
                ]
                + decisions
                + image_decisions
            ),
            "missing_items": tuple(missing_items),
        }
    )
