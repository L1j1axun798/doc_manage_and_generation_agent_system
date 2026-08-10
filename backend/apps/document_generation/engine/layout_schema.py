from __future__ import annotations

from io import BytesIO
from typing import Any

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from .rendering import _section_code_for_heading


TABLE_SIGNATURES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("personnel_information", ("姓名", "人员", "岗位", "证书"), "organization_measures"),
    ("hazard_controls", ("危险源", "风险", "控制措施", "预控措施"), "risk_identification"),
    ("work_process_points", ("工序", "检测点", "检测项目", "检查项目"), "construction_plan"),
    ("inspection_tools", ("检测工具", "检测仪器", "仪器", "工具"), "technical_measures"),
    ("safety_equipment", ("安全器材", "安全工器具", "器材"), "safety_measures"),
    ("ppe_items", ("劳保", "防护用品", "个人防护"), "safety_measures"),
)
TABLE_SECTIONS = {block_key: section_code for block_key, _terms, section_code in TABLE_SIGNATURES}
APPROVED_DEFAULT_TABLE_STYLE = "approved_default_v1"


def default_table_slots(section_codes: set[str]) -> list[dict[str, Any]]:
    """Expose regression-tested section-end slots when a template has no table."""

    slots: list[dict[str, Any]] = []

    def add(block_key: str, section_code: str, headers: list[str] | None = None) -> None:
        if section_code not in section_codes:
            return
        slot: dict[str, Any] = {
            "block_key": block_key,
            "section_code": section_code,
            "anchor": "section_end",
            "style_source": APPROVED_DEFAULT_TABLE_STYLE,
        }
        if headers:
            slot["headers"] = headers
            slot["column_count"] = len(headers)
        slots.append(slot)

    add(
        "personnel_information",
        "organization_measures",
        ["序号", "姓名", "岗位/职务", "联系电话", "证书及有效期"],
    )
    risk_section = (
        "risk_identification"
        if "risk_identification" in section_codes
        else "safety_measures"
    )
    add("hazard_controls", risk_section)
    add("work_process_points", "construction_plan")
    add("inspection_tools", "technical_measures")
    add("safety_equipment", "safety_measures")
    add("ppe_items", "safety_measures")
    return slots


def _semantic_table_key(headers: list[str], section_code: str | None) -> str | None:
    joined = " ".join(headers)
    for block_key, terms, preferred_section in TABLE_SIGNATURES:
        if section_code == preferred_section and any(term in joined for term in terms):
            return block_key
    for block_key, terms, _preferred_section in TABLE_SIGNATURES:
        if any(term in joined for term in terms):
            return block_key
    return None


def infer_template_layout_schema(content: bytes) -> dict[str, Any]:
    """Infer only stable semantic anchors; unknown historical tables are ignored."""

    try:
        document = Document(BytesIO(content))
    except Exception:
        return {"version": 1, "table_slots": [], "image_slots": []}

    section_code: str | None = None
    table_index = 0
    table_slots: list[dict[str, Any]] = []
    known_sections: set[str] = set()
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            detected = _section_code_for_heading(block.text)
            if detected:
                section_code = detected
                known_sections.add(detected)
            continue
        if not isinstance(block, Table):
            continue
        headers = [" ".join(cell.text.split()) for cell in block.rows[0].cells] if block.rows else []
        block_key = _semantic_table_key(headers, section_code)
        if block_key and headers and not any(
            slot["block_key"] == block_key for slot in table_slots
        ):
            table_slots.append(
                {
                    "block_key": block_key,
                    "section_code": section_code or TABLE_SECTIONS[block_key],
                    "prototype_table_index": table_index,
                    "headers": headers,
                    "column_count": len(headers),
                }
            )
        table_index += 1

    if not table_slots:
        table_slots = default_table_slots(known_sections)

    image_slots = [
            {
                "block_key": "rescue_route",
                "section_code": "emergency_plan",
                "anchor": "section_end",
                "max_count": 1,
            },
            {
                "block_key": "height_escape_plan",
                "section_code": "emergency_plan",
                "anchor": "section_end",
                "max_count": 1,
            },
            {
                "block_key": "height_rescue_plan",
                "section_code": "emergency_plan",
                "anchor": "section_end",
                "max_count": 1,
            },
    ]
    return {
        "version": 2,
        "uses_approved_default_table_style": bool(
            table_slots
            and all(slot.get("style_source") == APPROVED_DEFAULT_TABLE_STYLE for slot in table_slots)
        ),
        "table_slots": table_slots,
        "image_slots": image_slots,
    }
