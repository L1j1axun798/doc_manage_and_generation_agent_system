from __future__ import annotations

import re

REVISION_LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
REVISION_PERSONNEL_PAIR_RE = re.compile(
    r"([\u4e00-\u9fff]{2,4})\s*[，,、:：]\s*(\d{6,})"
)
REVISION_FOLLOWUP_MARKERS = (
    "没有看到",
    "没看到",
    "没有修改",
    "未修改",
    "没有生效",
    "未生效",
    "没有体现",
    "未体现",
)


def revision_required_literals(instruction: str) -> tuple[str, ...]:
    literals: list[str] = []
    for name, number in REVISION_PERSONNEL_PAIR_RE.findall(instruction):
        literals.extend((name, number))
    literals.extend(REVISION_LONG_NUMBER_RE.findall(instruction))
    return tuple(dict.fromkeys(value.strip() for value in literals if value.strip()))


def is_revision_followup(instruction: str) -> bool:
    return any(marker in instruction for marker in REVISION_FOLLOWUP_MARKERS)
