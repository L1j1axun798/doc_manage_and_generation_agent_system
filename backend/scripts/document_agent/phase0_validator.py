from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_CSV_HEADERS: dict[str, tuple[str, ...]] = {
    "business_candidates.csv": (
        "business_type_code",
        "business_type_name",
        "candidate_unique_sample_count",
        "approved_sample_count",
        "recent_6_month_project_count",
        "selection_status",
        "evidence_source",
        "evidence_as_of",
        "verified_by",
        "notes",
    ),
    "sample_inventory.csv": (
        "sample_id",
        "document_version_id",
        "document_id",
        "business_type_code",
        "document_title",
        "original_filename",
        "sha256",
        "source_format",
        "storage_verified",
        "duplicate_of_sample_id",
        "technical_review_status",
        "approval_evidence",
        "usage_role",
        "blind_eligible",
        "notes",
    ),
    "blind_test_set.csv": (
        "blind_case_id",
        "sample_id",
        "business_type_code",
        "custodian",
        "isolated_at",
        "leakage_check_status",
        "approval_status",
        "notes",
    ),
    "template_inventory.csv": (
        "template_id",
        "document_version_id",
        "business_type_code",
        "client_code",
        "template_name",
        "source_kind",
        "sha256",
        "required_placeholders_verified",
        "minimum_render_verified",
        "approval_status",
        "approved_by",
        "notes",
    ),
    "field_dictionary.csv": (
        "field_code",
        "display_name",
        "data_type",
        "required",
        "source",
        "system_mapping",
        "example",
        "confirmation_method",
        "approval_status",
        "notes",
    ),
    "risk_labels.csv": (
        "risk_code",
        "risk_name",
        "trigger_facts",
        "evidence_required",
        "default_section_code",
        "severity",
        "approval_status",
        "source_evidence",
        "notes",
    ),
    "clause_applicability_matrix.csv": (
        "matrix_id",
        "risk_code",
        "section_code",
        "clause_code",
        "clause_version",
        "applicability_condition",
        "required_when_matched",
        "conflict_priority",
        "approval_status",
        "approved_by",
        "notes",
    ),
    "section_annotations.csv": (
        "annotation_id",
        "sample_id",
        "document_version_id",
        "section_code",
        "heading_text",
        "paragraph_start",
        "paragraph_end",
        "reusable_status",
        "contains_project_specific_data",
        "review_status",
        "reviewer",
        "notes",
    ),
    "model_configuration_decision.csv": (
        "capability",
        "provider",
        "service_class",
        "model_alias",
        "data_region",
        "supports_structured_json",
        "supports_timeout_cancel",
        "supports_request_id",
        "token_cost_tracking",
        "sensitive_prompt_logging",
        "security_review_status",
        "technical_approval_status",
        "approved_by",
        "approved_at",
        "notes",
    ),
    "expert_scoring_rubric.csv": (
        "criterion_code",
        "criterion_name",
        "scope",
        "score_min",
        "score_max",
        "weight_percent",
        "hard_gate",
        "pass_rule",
        "owner",
        "approval_status",
        "notes",
    ),
    "expert_scorecard.csv": (
        "evaluation_version",
        "blind_case_id",
        "section_code",
        "reviewer",
        "reviewed_at",
        "factual_accuracy",
        "source_traceability",
        "clause_correctness",
        "safety_technical_completeness",
        "current_project_consistency",
        "professional_usability",
        "manual_editing_effort",
        "major_fabricated_fact",
        "major_safety_or_technical_omission",
        "all_numbers_have_sources",
        "historical_entity_contamination",
        "rag_hit_at_3",
        "changed_character_ratio",
        "baseline_minutes",
        "agent_assisted_minutes",
        "review_comments",
    ),
    "signoff_record.csv": (
        "artifact_code",
        "artifact_name",
        "required_role",
        "decision",
        "approver",
        "approved_at",
        "evidence_reference",
        "notes",
    ),
}

DEVELOPMENT_REQUIRED_SIGNOFFS = {
    "business_selection",
    "sample_inventory",
    "field_dictionary",
    "risk_and_clauses",
    "template_inventory",
    "model_configuration",
    "expert_scoring",
    "phase1_3_development",
}
REQUIRED_SIGNOFFS = DEVELOPMENT_REQUIRED_SIGNOFFS | {
    "blind_test_set",
    "phase0_completion",
}
REQUIRED_MODEL_CAPABILITIES = {"llm", "embedding"}
REQUIRED_SCORE_CRITERIA = {
    "factual_accuracy",
    "source_traceability",
    "clause_correctness",
    "safety_technical_completeness",
    "current_project_consistency",
    "professional_usability",
    "manual_editing_effort",
    "overall_time_reduction",
}
DEVELOPMENT_USAGE_ROLES = {"development", "prompt", "rules", "template_tuning"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError("Manifest root must be an object")
    return value


def validate_structure(base_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    if not base_dir.is_dir():
        return [Issue("PHASE0_DIRECTORY_MISSING", f"目录不存在：{base_dir}")]

    readme_path = base_dir / "README.md"
    if not readme_path.is_file():
        issues.append(Issue("README_MISSING", "缺少 README.md"))

    manifest_path = base_dir / "phase0_manifest.json"
    if not manifest_path.is_file():
        issues.append(Issue("MANIFEST_MISSING", "缺少 phase0_manifest.json"))
    else:
        try:
            manifest = _load_manifest(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(Issue("MANIFEST_INVALID", f"Manifest 无法读取：{exc}"))
        else:
            if manifest.get("phase") != 0:
                issues.append(Issue("MANIFEST_PHASE_INVALID", "Manifest phase 必须为 0"))
            if not str(manifest.get("target_document_family", "")).strip():
                issues.append(
                    Issue("MANIFEST_TARGET_MISSING", "Manifest 缺少 target_document_family")
                )

    for filename, expected_headers in REQUIRED_CSV_HEADERS.items():
        path = base_dir / filename
        if not path.is_file():
            issues.append(Issue("CSV_MISSING", f"缺少 {filename}"))
            continue
        try:
            with path.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.reader(source)
                actual_headers = tuple(next(reader, []))
                malformed_row = next(
                    (
                        line
                        for line, row in enumerate(reader, start=2)
                        if len(row) != len(actual_headers)
                    ),
                    None,
                )
        except (OSError, csv.Error) as exc:
            issues.append(Issue("CSV_INVALID", f"{filename} 无法读取：{exc}"))
            continue
        if actual_headers != expected_headers:
            issues.append(
                Issue(
                    "CSV_HEADERS_INVALID",
                    f"{filename} 表头不符合约定；应为 {','.join(expected_headers)}",
                )
            )
        if malformed_row is not None:
            issues.append(
                Issue("CSV_ROW_INVALID", f"{filename} 第 {malformed_row} 行列数与表头不一致")
            )
    return issues


def _parse_count(
    row: dict[str, str],
    field: str,
    *,
    record_name: str,
    issues: list[Issue],
    required: bool = True,
) -> int | None:
    raw_value = row.get(field, "")
    if not raw_value and not required:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        issues.append(Issue("COUNT_INVALID", f"{record_name}.{field} 必须是非负整数"))
        return None
    if value < 0:
        issues.append(Issue("COUNT_INVALID", f"{record_name}.{field} 必须是非负整数"))
        return None
    return value


def _validate_business_selection(
    *,
    businesses: list[dict[str, str]],
    samples: list[dict[str, str]],
    issues: list[Issue],
) -> str | None:
    selected_rows = [row for row in businesses if row["selection_status"] == "selected"]
    if len(selected_rows) != 1:
        issues.append(Issue("BUSINESS_SELECTION_COUNT", "必须且只能选择一个一期业务"))

    approved_unique_counts = Counter(
        row["business_type_code"]
        for row in samples
        if row["technical_review_status"] == "approved"
        and not row["duplicate_of_sample_id"]
        and row["storage_verified"] == "yes"
    )
    candidate_unique_counts = Counter(
        row["business_type_code"]
        for row in samples
        if not row["duplicate_of_sample_id"] and row["storage_verified"] == "yes"
    )

    approved_counts: dict[str, int] = {}
    recent_counts: dict[str, int | None] = {}
    for row in businesses:
        code = row["business_type_code"]
        record_name = f"business:{code or '<blank>'}"
        candidate_count = _parse_count(
            row,
            "candidate_unique_sample_count",
            record_name=record_name,
            issues=issues,
        )
        approved_count = _parse_count(
            row,
            "approved_sample_count",
            record_name=record_name,
            issues=issues,
        )
        recent_count = _parse_count(
            row,
            "recent_6_month_project_count",
            record_name=record_name,
            issues=issues,
            required=False,
        )
        if candidate_count is not None and candidate_count != candidate_unique_counts[code]:
            issues.append(
                Issue(
                    "CANDIDATE_COUNT_MISMATCH",
                    f"{code} 的候选样本数与 sample_inventory.csv 不一致",
                )
            )
        if approved_count is not None:
            approved_counts[code] = approved_count
            if approved_count != approved_unique_counts[code]:
                issues.append(
                    Issue(
                        "APPROVED_COUNT_MISMATCH",
                        f"{code} 的合格样本数与 sample_inventory.csv 不一致",
                    )
                )
        recent_counts[code] = recent_count

    if len(selected_rows) != 1 or not approved_counts:
        return None

    selected_code = selected_rows[0]["business_type_code"]
    maximum_approved = max(approved_counts.values())
    top_codes = {
        code
        for code, approved_count in approved_counts.items()
        if approved_count == maximum_approved
    }
    if selected_code not in top_codes:
        issues.append(Issue("BUSINESS_SAMPLE_RULE_FAILED", "一期业务不是合格样本数量最多的业务"))
        return selected_code

    if len(top_codes) > 1:
        if any(recent_counts.get(code) is None for code in top_codes):
            issues.append(
                Issue(
                    "RECENT_VOLUME_EVIDENCE_MISSING",
                    "合格样本数并列时必须填写近6个月已完成业务项目数",
                )
            )
        else:
            maximum_recent = max(recent_counts[code] or 0 for code in top_codes)
            recent_winners = {
                code for code in top_codes if (recent_counts[code] or 0) == maximum_recent
            }
            if selected_code not in recent_winners:
                issues.append(
                    Issue(
                        "BUSINESS_VOLUME_RULE_FAILED",
                        "一期业务不是并列候选中近6个月业务量最高的业务",
                    )
                )
            elif len(recent_winners) > 1:
                issues.append(
                    Issue(
                        "BUSINESS_TIE_UNRESOLVED",
                        "样本数和近6个月业务量仍并列，需技术负责人书面决定",
                    )
                )
    return selected_code


def _approved_samples(
    samples: list[dict[str, str]],
    selected_business: str | None,
    issues: list[Issue],
) -> dict[str, dict[str, str]]:
    approved: dict[str, dict[str, str]] = {}
    seen_hashes: set[str] = set()
    for row in samples:
        if row["technical_review_status"] != "approved":
            continue
        sample_id = row["sample_id"]
        if row["business_type_code"] != selected_business:
            continue
        if row["duplicate_of_sample_id"]:
            continue
        if row["storage_verified"] != "yes":
            issues.append(Issue("SAMPLE_STORAGE_UNVERIFIED", f"{sample_id} 未验证物理文件"))
            continue
        if row["source_format"] != "docx":
            issues.append(Issue("SAMPLE_FORMAT_UNSUPPORTED", f"{sample_id} 尚未受控转换为 docx"))
            continue
        digest = row["sha256"]
        if not SHA256_RE.fullmatch(digest):
            issues.append(Issue("SAMPLE_SHA256_INVALID", f"{sample_id} 的 SHA-256 无效"))
            continue
        if digest in seen_hashes:
            issues.append(Issue("SAMPLE_HASH_DUPLICATE", f"{sample_id} 与其他合格样本哈希重复"))
            continue
        if not row["approval_evidence"]:
            issues.append(Issue("SAMPLE_APPROVAL_EVIDENCE_MISSING", f"{sample_id} 缺少审核证据"))
        seen_hashes.add(digest)
        approved[sample_id] = row

    if not 5 <= len(approved) <= 20:
        issues.append(Issue("APPROVED_SAMPLE_COUNT", "一期业务必须有5至20份合格唯一DOCX样本"))
    return approved


def _validate_blind_set(
    *,
    blind_rows: list[dict[str, str]],
    samples_by_id: dict[str, dict[str, str]],
    approved_samples: dict[str, dict[str, str]],
    selected_business: str | None,
    issues: list[Issue],
) -> None:
    approved_blind = [row for row in blind_rows if row["approval_status"] == "approved"]
    unique_sample_ids = {row["sample_id"] for row in approved_blind}
    if len(approved_blind) != len(unique_sample_ids):
        issues.append(Issue("BLIND_DUPLICATE", "盲测清单包含重复样本"))
    if len(unique_sample_ids) < 5:
        issues.append(Issue("BLIND_SAMPLE_COUNT", "盲测集至少需要5份已批准样本"))

    for row in approved_blind:
        sample_id = row["sample_id"]
        sample = samples_by_id.get(sample_id)
        if sample_id not in approved_samples:
            issues.append(Issue("BLIND_SAMPLE_NOT_ELIGIBLE", f"{sample_id} 不是合格一期样本"))
        if row["business_type_code"] != selected_business:
            issues.append(Issue("BLIND_BUSINESS_MISMATCH", f"{sample_id} 不属于选定一期业务"))
        if not row["blind_case_id"] or not row["custodian"] or not row["isolated_at"]:
            issues.append(Issue("BLIND_CUSTODY_INCOMPLETE", f"{sample_id} 缺少隔离保管信息"))
        if row["leakage_check_status"] != "passed":
            issues.append(Issue("BLIND_LEAKAGE_CHECK_FAILED", f"{sample_id} 未通过泄漏检查"))
        if sample is not None and sample["usage_role"] != "blind":
            issues.append(Issue("BLIND_USAGE_ROLE_MISMATCH", f"{sample_id} 未标记为 blind"))
        if sample is not None and sample["usage_role"] in DEVELOPMENT_USAGE_ROLES:
            issues.append(Issue("BLIND_DEVELOPMENT_OVERLAP", f"{sample_id} 被用于开发或调优"))


def _validate_templates(
    rows: list[dict[str, str]],
    selected_business: str | None,
    issues: list[Issue],
) -> None:
    approved = [
        row
        for row in rows
        if row["approval_status"] == "approved" and row["business_type_code"] == selected_business
    ]
    if not 2 <= len(approved) <= 3:
        issues.append(Issue("APPROVED_TEMPLATE_COUNT", "一期业务必须批准2至3套优先甲方模板"))
    for row in approved:
        template_id = row["template_id"]
        if not row["client_code"] or not row["approved_by"]:
            issues.append(Issue("TEMPLATE_APPROVAL_INCOMPLETE", f"{template_id} 缺少甲方或批准人"))


def _validate_fields(rows: list[dict[str, str]], issues: list[Issue]) -> None:
    if not rows:
        issues.append(Issue("FIELD_DICTIONARY_EMPTY", "字段字典不能为空"))
        return
    field_codes = [row["field_code"] for row in rows]
    duplicate_codes = sorted(code for code, count in Counter(field_codes).items() if count > 1)
    for code in duplicate_codes:
        issues.append(Issue("FIELD_CODE_DUPLICATE", f"{code or '<blank>'} 字段编码重复"))
    for row in rows:
        code = row["field_code"] or "<blank>"
        if row["approval_status"] != "approved":
            issues.append(Issue("FIELD_NOT_APPROVED", f"{code} 尚未批准"))
        if row["required"] not in {"yes", "no", "conditional"}:
            issues.append(Issue("FIELD_REQUIRED_INVALID", f"{code}.required 取值无效"))
        for field in ("display_name", "data_type", "source", "example", "confirmation_method"):
            if not row[field]:
                issues.append(Issue("FIELD_METADATA_INCOMPLETE", f"{code}.{field} 不能为空"))
        if row["required"] == "conditional" and not row["notes"]:
            issues.append(Issue("FIELD_CONDITION_MISSING", f"{code} 缺少条件必填说明"))


def _validate_risks_and_clauses(
    risk_rows: list[dict[str, str]],
    clause_rows: list[dict[str, str]],
    issues: list[Issue],
) -> None:
    approved_risks = {row["risk_code"] for row in risk_rows if row["approval_status"] == "approved"}
    if not approved_risks:
        issues.append(Issue("APPROVED_RISK_EMPTY", "至少需要一个已批准风险标签"))
    for row in risk_rows:
        if row["approval_status"] != "approved":
            issues.append(Issue("RISK_NOT_APPROVED", f"{row['risk_code']} 尚未批准"))
        for field in ("risk_name", "trigger_facts", "evidence_required", "default_section_code"):
            if not row[field]:
                issues.append(
                    Issue("RISK_METADATA_INCOMPLETE", f"{row['risk_code']}.{field} 不能为空")
                )

    mapped_risks: set[str] = set()
    for row in clause_rows:
        if row["approval_status"] != "approved":
            issues.append(Issue("CLAUSE_NOT_APPROVED", f"{row['matrix_id']} 尚未批准"))
            continue
        if row["risk_code"] not in approved_risks:
            issues.append(
                Issue(
                    "CLAUSE_RISK_INVALID",
                    f"{row['matrix_id']} 引用了未批准或不存在的风险 {row['risk_code']}",
                )
            )
        if row["clause_code"].startswith("TBD-") or not row["clause_code"]:
            issues.append(Issue("CLAUSE_CODE_TBD", f"{row['matrix_id']} 缺少正式条款编码"))
        if not row["clause_version"]:
            issues.append(Issue("CLAUSE_VERSION_MISSING", f"{row['matrix_id']} 缺少条款版本"))
        if not row["approved_by"]:
            issues.append(Issue("CLAUSE_APPROVER_MISSING", f"{row['matrix_id']} 缺少批准人"))
        mapped_risks.add(row["risk_code"])
    for risk_code in sorted(approved_risks - mapped_risks):
        issues.append(Issue("RISK_WITHOUT_CLAUSE", f"{risk_code} 没有已批准适用条款"))


def _validate_annotations(
    rows: list[dict[str, str]],
    approved_samples: dict[str, dict[str, str]],
    issues: list[Issue],
) -> None:
    annotation_ids = [row["annotation_id"] for row in rows]
    for annotation_id, count in Counter(annotation_ids).items():
        if count > 1:
            issues.append(
                Issue("SECTION_ANNOTATION_DUPLICATE", f"{annotation_id or '<blank>'} 标注编号重复")
            )
    rows_by_sample: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_sample.setdefault(row["sample_id"], []).append(row)
    blind_sample_ids = {
        sample_id
        for sample_id, sample in approved_samples.items()
        if sample["usage_role"] == "blind"
    }
    for sample_id in sorted(blind_sample_ids & rows_by_sample.keys()):
        issues.append(
            Issue(
                "BLIND_ANNOTATION_LEAKAGE",
                f"{sample_id} 是盲测样本，不得出现在章节标注中",
            )
        )

    development_samples = {
        sample_id: sample
        for sample_id, sample in approved_samples.items()
        if sample["usage_role"] in DEVELOPMENT_USAGE_ROLES
    }
    for sample_id in development_samples:
        annotations = rows_by_sample.get(sample_id, [])
        if not annotations:
            issues.append(Issue("SECTION_ANNOTATION_MISSING", f"{sample_id} 未标注章节"))
            continue
        for row in annotations:
            if row["document_version_id"] != development_samples[sample_id]["document_version_id"]:
                issues.append(
                    Issue(
                        "SECTION_DOCUMENT_VERSION_MISMATCH",
                        f"{row['annotation_id']} 的文档版本与样本清单不一致",
                    )
                )
            if row["review_status"] != "approved" or not row["reviewer"]:
                issues.append(
                    Issue("SECTION_ANNOTATION_NOT_APPROVED", f"{row['annotation_id']} 尚未审核")
                )
            if row["reusable_status"] not in {"reusable", "project_specific", "excluded"}:
                issues.append(
                    Issue(
                        "SECTION_REUSE_STATUS_UNRESOLVED",
                        f"{row['annotation_id']} 未确定可复用状态",
                    )
                )
            if row["contains_project_specific_data"] not in {"yes", "no"}:
                issues.append(
                    Issue(
                        "SECTION_PROJECT_DATA_UNRESOLVED",
                        f"{row['annotation_id']} 未确认项目专有信息",
                    )
                )
            try:
                paragraph_start = int(row["paragraph_start"])
                paragraph_end = int(row["paragraph_end"])
            except ValueError:
                issues.append(
                    Issue(
                        "SECTION_BOUNDARY_INVALID",
                        f"{row['annotation_id']} 的段落边界必须是整数",
                    )
                )
            else:
                if paragraph_start < 0 or paragraph_end < paragraph_start:
                    issues.append(
                        Issue(
                            "SECTION_BOUNDARY_INVALID",
                            f"{row['annotation_id']} 的段落边界无效",
                        )
                    )


def _validate_model_decision(rows: list[dict[str, str]], issues: list[Issue]) -> None:
    capabilities = [row["capability"] for row in rows]
    for capability, count in Counter(capabilities).items():
        if count > 1:
            issues.append(
                Issue("MODEL_CAPABILITY_DUPLICATE", f"{capability or '<blank>'} 配置决定重复")
            )
    rows_by_capability = {row["capability"]: row for row in rows}
    missing = REQUIRED_MODEL_CAPABILITIES - rows_by_capability.keys()
    for capability in sorted(missing):
        issues.append(Issue("MODEL_CAPABILITY_MISSING", f"缺少 {capability} 配置决定"))
    for capability in sorted(REQUIRED_MODEL_CAPABILITIES & rows_by_capability.keys()):
        row = rows_by_capability[capability]
        if not row["provider"] or not row["model_alias"] or not row["data_region"]:
            issues.append(Issue("MODEL_DECISION_INCOMPLETE", f"{capability} 服务决定不完整"))
        if row["security_review_status"] != "approved":
            issues.append(Issue("MODEL_SECURITY_NOT_APPROVED", f"{capability} 未通过安全审核"))
        if row["technical_approval_status"] != "approved":
            issues.append(Issue("MODEL_TECHNICAL_NOT_APPROVED", f"{capability} 未通过技术审核"))
        if not row["approved_by"] or not row["approved_at"]:
            issues.append(Issue("MODEL_APPROVER_MISSING", f"{capability} 缺少批准记录"))
        if row["sensitive_prompt_logging"] != "prohibited":
            issues.append(
                Issue("MODEL_SENSITIVE_LOGGING_INVALID", f"{capability} 必须禁止敏感日志")
            )


def _validate_score_rubric(rows: list[dict[str, str]], issues: list[Issue]) -> None:
    criteria = {row["criterion_code"] for row in rows}
    for criterion in sorted(REQUIRED_SCORE_CRITERIA - criteria):
        issues.append(Issue("SCORE_CRITERION_MISSING", f"评分表缺少 {criterion}"))
    if len(criteria) != len(rows):
        issues.append(Issue("SCORE_CRITERION_DUPLICATE", "评分维度编码必须唯一"))
    total_weight = 0
    for row in rows:
        code = row["criterion_code"] or "<blank>"
        if row["approval_status"] != "approved":
            issues.append(Issue("SCORE_RUBRIC_NOT_APPROVED", f"{code} 尚未批准"))
        if row["hard_gate"] not in {"yes", "no"}:
            issues.append(Issue("SCORE_HARD_GATE_INVALID", f"{code}.hard_gate 取值无效"))
        if not row["pass_rule"] or not row["owner"]:
            issues.append(Issue("SCORE_METADATA_INCOMPLETE", f"{code} 缺少通过规则或负责人"))
        try:
            score_min = int(row["score_min"])
            score_max = int(row["score_max"])
            weight = int(row["weight_percent"])
        except ValueError:
            issues.append(Issue("SCORE_NUMBER_INVALID", f"{code} 的分值或权重必须是整数"))
            continue
        if score_min >= score_max or weight < 0:
            issues.append(Issue("SCORE_NUMBER_INVALID", f"{code} 的分值范围或权重无效"))
        total_weight += weight
    if rows and total_weight != 100:
        issues.append(Issue("SCORE_WEIGHT_INVALID", "评分权重合计必须为100"))


def _validate_signoffs(
    rows: list[dict[str, str]],
    issues: list[Issue],
    required_signoffs: set[str],
) -> None:
    rows_by_code = {row["artifact_code"]: row for row in rows}
    for code in sorted(required_signoffs):
        row = rows_by_code.get(code)
        if row is None:
            issues.append(Issue("SIGNOFF_MISSING", f"缺少 {code} 签字项"))
            continue
        if row["decision"] != "approved":
            issues.append(Issue("SIGNOFF_PENDING", f"{code} 尚未签字批准"))
        elif not row["approver"] or not row["approved_at"] or not row["evidence_reference"]:
            issues.append(Issue("SIGNOFF_INCOMPLETE", f"{code} 的批准记录不完整"))


def _validate_phase0(
    base_dir: Path,
    *,
    require_blind_set: bool,
) -> list[Issue]:
    issues = validate_structure(base_dir)
    if issues:
        return issues

    manifest = _load_manifest(base_dir / "phase0_manifest.json")
    manifest_status = manifest.get("status")
    if require_blind_set and manifest_status != "approved":
        issues.append(Issue("MANIFEST_NOT_APPROVED", "Manifest status 必须为 approved"))
    elif not require_blind_set and manifest_status not in {"baseline_ready", "approved"}:
        issues.append(
            Issue(
                "MANIFEST_NOT_BASELINE_READY",
                "Manifest status 必须为 baseline_ready 或 approved",
            )
        )

    data = {filename: _read_csv(base_dir / filename) for filename in REQUIRED_CSV_HEADERS}
    businesses = data["business_candidates.csv"]
    samples = data["sample_inventory.csv"]
    selected_business = _validate_business_selection(
        businesses=businesses,
        samples=samples,
        issues=issues,
    )
    manifest_business = str(manifest.get("selected_business_type_code", "")).strip()
    if selected_business and manifest_business != selected_business:
        issues.append(
            Issue(
                "MANIFEST_BUSINESS_MISMATCH",
                "Manifest 的一期业务编码与业务候选清单不一致",
            )
        )
    approved_samples = _approved_samples(samples, selected_business, issues)
    if require_blind_set:
        samples_by_id = {row["sample_id"]: row for row in samples}
        _validate_blind_set(
            blind_rows=data["blind_test_set.csv"],
            samples_by_id=samples_by_id,
            approved_samples=approved_samples,
            selected_business=selected_business,
            issues=issues,
        )
    _validate_templates(data["template_inventory.csv"], selected_business, issues)
    _validate_fields(data["field_dictionary.csv"], issues)
    _validate_risks_and_clauses(
        data["risk_labels.csv"],
        data["clause_applicability_matrix.csv"],
        issues,
    )
    _validate_annotations(data["section_annotations.csv"], approved_samples, issues)
    _validate_model_decision(data["model_configuration_decision.csv"], issues)
    _validate_score_rubric(data["expert_scoring_rubric.csv"], issues)
    required_signoffs = REQUIRED_SIGNOFFS if require_blind_set else DEVELOPMENT_REQUIRED_SIGNOFFS
    _validate_signoffs(data["signoff_record.csv"], issues, required_signoffs)
    return issues


def validate_development_gate(base_dir: Path) -> list[Issue]:
    return _validate_phase0(base_dir, require_blind_set=False)


def validate_gate(base_dir: Path) -> list[Issue]:
    return _validate_phase0(base_dir, require_blind_set=True)


def _default_phase0_dir() -> Path:
    repository_root = Path(__file__).resolve().parents[3]
    return repository_root / "docs" / "document_agent" / "phase0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Document Agent Phase 0 artifacts.")
    parser.add_argument(
        "--mode",
        choices=("structure", "development", "gate"),
        default="gate",
        help=(
            "structure checks schemas; development allows Phase 1-3; "
            "gate checks full Phase 0 completion before Phase 4."
        ),
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=_default_phase0_dir(),
        help="Phase 0 artifact directory.",
    )
    args = parser.parse_args(argv)

    base_dir = args.base_dir.resolve()
    validators = {
        "structure": validate_structure,
        "development": validate_development_gate,
        "gate": validate_gate,
    }
    issues = validators[args.mode](base_dir)
    if issues:
        print(f"[FAIL] Phase 0 {args.mode} validation: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue.code}: {issue.message}")
        return 1

    print(f"[PASS] Phase 0 {args.mode} validation: {base_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
