from __future__ import annotations

import re
from collections.abc import Sequence

from .engine.contracts import ParsedBlock

SECTION_HEADING_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "risk_identification",
        ("风险辨识", "风险识别", "危险源辨识", "危险点分析", "风险预控", "风险分析"),
    ),
    ("emergency_plan", ("应急预案", "应急处置", "应急措施", "事故应急")),
    ("environmental_measures", ("环境保护", "文明施工", "环保措施", "绿色施工")),
    ("organization_measures", ("组织措施", "组织机构", "组织保障", "人员组织", "岗位职责")),
    ("safety_measures", ("安全措施", "安全管理", "安全保障", "安全要求")),
    ("technical_measures", ("技术措施", "技术要求", "技术方案", "检测工艺", "质量控制")),
    ("construction_plan", ("施工方案", "作业方案", "检测方案", "实施方案", "施工方法", "作业流程")),
    ("overview", ("工程概况", "项目概况", "编制依据", "工作范围", "项目简介")),
)


def blocks_for_section(
    blocks: Sequence[ParsedBlock],
    section_code: str,
) -> tuple[ParsedBlock, ...]:
    return tuple(
        block for block in blocks if classify_heading_path(block.heading_path) == section_code
    )


def classify_heading_path(heading_path: Sequence[str]) -> str | None:
    for heading in reversed(heading_path):
        normalized = re.sub(r"[\s　]+", "", heading)
        for section_code, keywords in SECTION_HEADING_KEYWORDS:
            if any(keyword in normalized for keyword in keywords):
                return section_code
    return None
