from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from .contracts import FactCandidate, ParsedBlock, ParsedDocument, SourceLocator

REQUIRED_FACT_LABELS: Final[dict[str, str]] = {
    "project_name": "项目名称",
    "work_scope": "工作范围",
    "inspection_component_codes": "检测部件",
    "inspection_method_codes": "检测方法",
    "risk_evidence_items": "当前项目风险依据",
}

COMPONENT_CODE_LABELS: Final[dict[str, str]] = {
    "tower_weld": "塔筒焊缝",
    "tower_component": "塔筒部件",
    "high_strength_bolt": "高强度螺栓",
    "pitch_bearing": "变桨轴承",
    "blade_bolt": "叶片螺栓",
}

METHOD_CODE_LABELS: Final[dict[str, str]] = {
    "UT": "超声检测",
    "PAUT": "相控阵超声检测",
    "MT": "磁粉检测",
    "PT": "渗透检测",
    "VT": "目视检测",
    "ET": "涡流检测",
}

RISK_CODE_LABELS: Final[dict[str, str]] = {
    "high_altitude": "高处作业",
    "climbing_tower": "攀爬塔筒",
    "electrical_work": "电气作业",
    "temporary_power": "临时用电",
    "fire_hot_work": "消防或动火",
    "mechanical_injury": "机械伤害",
    "falling_object": "物体打击或高空坠物",
    "confined_space": "有限或狭小空间",
    "extreme_weather": "极端天气",
    "vehicle_traffic": "车辆交通",
    "environmental_pollution": "环境污染",
    "lifting_hoisting": "起吊或电动葫芦",
}

_COMPONENT_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "tower_weld": ("塔筒焊缝",),
    "tower_component": ("塔筒部件",),
    "high_strength_bolt": ("高强度螺栓",),
    "pitch_bearing": ("变桨轴承",),
    "blade_bolt": ("叶片螺栓",),
}

_METHOD_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "UT": ("超声波检测", "超声检测", "超声探伤", "电磁超声"),
    "PAUT": ("相控阵超声", "相控阵检测", "相控阵探伤"),
    "MT": ("磁粉检测", "磁粉探伤"),
    "PT": ("渗透检测", "渗透探伤"),
    "VT": ("目视检测", "外观检查", "目视检查"),
    "ET": ("涡流检测", "涡流探伤"),
}

_RISK_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "high_altitude": ("高处作业", "高空作业", "高空临边", "高空坠落"),
    "climbing_tower": ("攀爬塔筒", "攀爬风机", "人员登塔", "登塔作业", "涉及爬塔"),
    "electrical_work": ("电气作业", "设备带电", "存在触电"),
    "temporary_power": ("临时用电", "临时电源"),
    "fire_hot_work": ("动火作业", "现场明火"),
    "mechanical_injury": ("机械伤害",),
    "falling_object": ("高空坠物", "物体打击"),
    "confined_space": ("有限空间作业", "密闭空间", "窒息中毒"),
    "extreme_weather": ("大风暴雨", "冰冻天气", "极端天气"),
    "vehicle_traffic": ("驾驶车辆", "作业车辆", "车辆交通", "兼职司机"),
    "environmental_pollution": ("环境污染", "废油废液", "漏油"),
    "lifting_hoisting": ("起吊作业", "吊装作业", "电动葫芦"),
}


def infer_component_codes(text: str) -> tuple[str, ...]:
    return _matching_codes(text, _COMPONENT_TERMS)


def infer_method_codes(text: str) -> tuple[str, ...]:
    return _matching_codes(text, _METHOD_TERMS)


def infer_risk_codes(text: str) -> tuple[str, ...]:
    return _matching_codes(text, _RISK_TERMS)


def _matching_codes(
    text: str,
    terms_by_code: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    return tuple(
        code
        for code, terms in terms_by_code.items()
        if any(term in text for term in terms)
    )


def enrich_required_fact_candidates(
    candidates: Sequence[FactCandidate],
    documents: Sequence[ParsedDocument],
) -> tuple[FactCandidate, ...]:
    """Add deterministic, source-anchored canonical candidates the UI requires."""

    enriched = list(candidates)
    fields = {candidate.field for candidate in enriched}
    blocks = [
        (document.document_version_id, block)
        for document in documents
        for block in document.blocks
        if block.text.strip()
    ]
    if not blocks:
        return tuple(enriched)

    scope_match = _best_scope_block(blocks)
    alias_scope = _first_candidate(enriched, ("work_scope", "target_component"))

    if "work_scope" not in fields:
        if scope_match is not None:
            document_version_id, block = scope_match
            enriched.append(
                _candidate_from_block(
                    field="work_scope",
                    value=block.text.strip(),
                    value_type="string",
                    document_version_id=document_version_id,
                    block=block,
                    confidence=0.9,
                )
            )
        elif alias_scope is not None:
            enriched.append(
                _candidate_from_alias(
                    alias_scope,
                    field="work_scope",
                    value=alias_scope.locator.text_quote or alias_scope.value,
                    value_type="string",
                )
            )

    if "inspection_component_codes" not in fields:
        component_matches = _catalog_matches(
            _scope_texts(scope_match, blocks),
            _COMPONENT_TERMS,
        )
        if component_matches:
            document_version_id, block = _first_matching_block(
                _scope_texts(scope_match, blocks),
                _COMPONENT_TERMS,
            )
            enriched.append(
                _candidate_from_block(
                    field="inspection_component_codes",
                    value=component_matches,
                    value_type="array",
                    document_version_id=document_version_id,
                    block=block,
                    confidence=0.9,
                )
            )

    if "inspection_method_codes" not in fields:
        method_blocks = [
            item
            for item in blocks
            if any(
                marker in item[1].text
                for marker in ("采用", "检测方法", "检测步骤", "检测标准")
            )
        ]
        method_matches = _method_matches(method_blocks)
        if method_matches:
            document_version_id, block = _first_matching_block(method_blocks, _METHOD_TERMS)
            enriched.append(
                _candidate_from_block(
                    field="inspection_method_codes",
                    value=method_matches,
                    value_type="array",
                    document_version_id=document_version_id,
                    block=block,
                    confidence=0.9,
                )
            )

    if "risk_evidence_items" not in fields:
        risk_items: list[dict[str, str]] = []
        first_risk_match: tuple[int, ParsedBlock] | None = None
        for risk_code, terms in _RISK_TERMS.items():
            matched = next(
                (item for item in blocks if any(term in item[1].text for term in terms)),
                None,
            )
            if matched is None:
                continue
            first_risk_match = first_risk_match or matched
            risk_items.append(
                {
                    "risk_code": risk_code,
                    "evidence": matched[1].text.strip()[:500],
                }
            )
        anchor = first_risk_match or scope_match or blocks[0]
        enriched.append(
            _candidate_from_block(
                field="risk_evidence_items",
                value=risk_items,
                value_type="array",
                document_version_id=anchor[0],
                block=anchor[1],
                confidence=0.85 if risk_items else 0.5,
            )
        )
    return tuple(enriched)


def validate_required_fact_value(field: str, value: Any) -> str | None:
    if field in {"project_name", "work_scope"}:
        if not isinstance(value, str) or not value.strip():
            return f"{REQUIRED_FACT_LABELS[field]}不能为空"
        return None
    if field == "inspection_component_codes":
        return _validate_code_list(
            value,
            allowed=COMPONENT_CODE_LABELS,
            label=REQUIRED_FACT_LABELS[field],
            allow_empty=False,
        )
    if field == "inspection_method_codes":
        return _validate_code_list(
            value,
            allowed=METHOD_CODE_LABELS,
            label=REQUIRED_FACT_LABELS[field],
            allow_empty=False,
        )
    if field == "risk_evidence_items":
        if not isinstance(value, list):
            return "当前项目风险依据必须为列表"
        for item in value:
            if not isinstance(item, dict):
                return "当前项目风险依据中的每一项都必须包含风险类型和依据"
            risk_code = item.get("risk_code")
            evidence = item.get("evidence")
            if risk_code not in RISK_CODE_LABELS:
                return f"存在不支持的风险类型：{risk_code}"
            if not isinstance(evidence, str) or not evidence.strip():
                return f"{RISK_CODE_LABELS[risk_code]}缺少事实依据"
    return None


def _validate_code_list(
    value: Any,
    *,
    allowed: dict[str, str],
    label: str,
    allow_empty: bool,
) -> str | None:
    if not isinstance(value, list) or (not allow_empty and not value):
        return f"{label}至少选择一项"
    invalid = [item for item in value if not isinstance(item, str) or item not in allowed]
    if invalid:
        return f"{label}中存在不支持的选项：{', '.join(map(str, invalid))}"
    return None


def _best_scope_block(
    blocks: Sequence[tuple[int, ParsedBlock]],
) -> tuple[int, ParsedBlock] | None:
    scored: list[tuple[int, int, ParsedBlock]] = []
    component_terms = tuple(term for terms in _COMPONENT_TERMS.values() for term in terms)
    for document_version_id, block in blocks:
        text = block.text
        score = 0
        score += 4 if any(term in text for term in component_terms) else 0
        score += 3 if any(term in text for term in ("主要内容包括", "工作范围", "检测范围")) else 0
        score += 2 if "检测" in text else 0
        score += 1 if any(unit in text for unit in ("台风电机组", "台机组", "号机组")) else 0
        if score >= 6:
            scored.append((score, document_version_id, block))
    if not scored:
        return None
    _, document_version_id, block = max(scored, key=lambda item: item[0])
    return document_version_id, block


def _scope_texts(
    scope_match: tuple[int, ParsedBlock] | None,
    blocks: Sequence[tuple[int, ParsedBlock]],
) -> list[tuple[int, ParsedBlock]]:
    preferred = [scope_match] if scope_match is not None else []
    preferred.extend(
        item
        for item in blocks
        if any(marker in item[1].text for marker in ("检测范围", "主要内容包括", "项目探伤作业"))
        and item != scope_match
    )
    return preferred or list(blocks)


def _catalog_matches(
    blocks: Sequence[tuple[int, ParsedBlock]],
    catalog: dict[str, tuple[str, ...]],
) -> list[str]:
    text = "\n".join(block.text for _, block in blocks)
    return [
        code
        for code, terms in catalog.items()
        if any(term in text for term in terms)
    ]


def _method_matches(
    blocks: Sequence[tuple[int, ParsedBlock]],
) -> list[str]:
    text = "\n".join(block.text for _, block in blocks)
    paut_terms = _METHOD_TERMS["PAUT"]
    has_paut = any(term in text for term in paut_terms)
    non_paut_text = text
    for term in paut_terms:
        non_paut_text = non_paut_text.replace(term, "")
    has_ut = any(term in non_paut_text for term in _METHOD_TERMS["UT"])
    return [
        code
        for code, matched in (("UT", has_ut), ("PAUT", has_paut))
        if matched
    ]


def _first_matching_block(
    blocks: Sequence[tuple[int, ParsedBlock]],
    catalog: dict[str, tuple[str, ...]],
) -> tuple[int, ParsedBlock]:
    all_terms = tuple(term for terms in catalog.values() for term in terms)
    return next(item for item in blocks if any(term in item[1].text for term in all_terms))


def _first_candidate(
    candidates: Sequence[FactCandidate],
    fields: Sequence[str],
) -> FactCandidate | None:
    for field in fields:
        candidate = next((item for item in candidates if item.field == field), None)
        if candidate is not None:
            return candidate
    return None


def _candidate_from_alias(
    candidate: FactCandidate,
    *,
    field: str,
    value: Any,
    value_type: str,
) -> FactCandidate:
    return FactCandidate(
        field=field,
        value=value,
        value_type=value_type,
        source_document_version_id=candidate.source_document_version_id,
        locator=candidate.locator,
        confidence=min(candidate.confidence, 0.85),
    )


def _candidate_from_block(
    *,
    field: str,
    value: Any,
    value_type: str,
    document_version_id: int,
    block: ParsedBlock,
    confidence: float,
) -> FactCandidate:
    locator = block.locator.model_copy(
        update={"text_quote": block.text.strip()[:200]},
    )
    return FactCandidate(
        field=field,
        value=value,
        value_type=value_type,
        source_document_version_id=document_version_id,
        locator=SourceLocator.model_validate(locator),
        confidence=confidence,
    )
