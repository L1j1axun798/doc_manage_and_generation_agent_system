from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit_log
from apps.documents.models import DocumentVersion
from common.storage import LocalDocumentStorage

from .engine.contracts import ENTRY_PLAN_SECTION_CODES, KnowledgeChunk
from .models import (
    BUSINESS_TYPE,
    ApprovalStatus,
    ClauseBlock,
    DocumentTemplate,
    KnowledgeSection,
)

DEFAULT_REQUIRED_FACT_FIELDS = (
    "project_name",
    "work_scope",
    "inspection_component_codes",
    "inspection_method_codes",
    "risk_evidence_items",
)


@dataclass(frozen=True)
class BootstrapPaths:
    template_inventory: Path
    clause_matrix: Path
    clause_blocks: Path
    knowledge_index: Path


@dataclass(frozen=True)
class BootstrapResult:
    templates_created: int
    templates_updated: int
    clauses_created: int
    clauses_updated: int
    knowledge_created: int
    knowledge_updated: int
    dry_run: bool


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"初始化文件不存在：{path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _approved_rows(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    approved = [row for row in rows if row.get("approval_status", "").strip() == "approved"]
    if not approved:
        raise ValueError(f"初始化文件没有已批准记录：{path}")
    return approved


def _load_knowledge(path: Path) -> tuple[KnowledgeChunk, ...]:
    if not path.is_file():
        raise ValueError(f"RAG知识索引不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("RAG知识索引必须是非空JSON数组")
    return tuple(KnowledgeChunk.model_validate(item) for item in payload)


def _verify_template_version(row: dict[str, str]) -> DocumentVersion:
    version_id = int(row["document_version_id"])
    version = DocumentVersion.objects.select_related("document").get(pk=version_id)
    expected_sha256 = row["sha256"].strip().lower()
    if version.sha256.lower() != expected_sha256:
        raise ValueError(f"模板 {row['template_id']} 的数据库SHA-256与清单不一致")
    storage = LocalDocumentStorage()
    path = storage.resolve(version.storage_path)
    if not path.is_file():
        raise ValueError(f"模板 {row['template_id']} 的物理文件不存在")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError(f"模板 {row['template_id']} 的物理文件SHA-256与清单不一致")
    return version


def _ensure_common_business_type(rows: list[dict[str, str]]) -> None:
    invalid = sorted(
        {
            row.get("business_type_code", BUSINESS_TYPE).strip()
            for row in rows
            if row.get("business_type_code", BUSINESS_TYPE).strip() != BUSINESS_TYPE
        }
    )
    if invalid:
        raise ValueError(f"发现一期范围之外的业务类型：{', '.join(invalid)}")


@transaction.atomic
def bootstrap_document_agent(
    *,
    actor: Any,
    paths: BootstrapPaths,
    dry_run: bool = False,
) -> BootstrapResult:
    if not getattr(actor, "is_active", False):
        raise ValueError("批准人必须是有效用户")

    template_rows = _approved_rows(paths.template_inventory)
    matrix_rows = _approved_rows(paths.clause_matrix)
    clause_rows = _approved_rows(paths.clause_blocks)
    knowledge_chunks = _load_knowledge(paths.knowledge_index)
    _ensure_common_business_type(template_rows)
    matrix_by_id = {row["matrix_id"]: row for row in matrix_rows}
    now = timezone.now()

    template_created = 0
    template_updated = 0
    for row in template_rows:
        if row.get("required_placeholders_verified") != "yes":
            raise ValueError(f"模板 {row['template_id']} 未通过占位符检查")
        if row.get("minimum_render_verified") != "yes":
            raise ValueError(f"模板 {row['template_id']} 未通过最小渲染检查")
        version = _verify_template_version(row)
        template_defaults = {
            "client_name": "",
            "business_type": BUSINESS_TYPE,
            "document_version": version,
            "field_mapping": {
                "client_code": row.get("client_code", "").strip(),
                "template_name": row.get("template_name", "").strip(),
                "source_kind": row.get("source_kind", "").strip(),
                "required_placeholders": [],
                "privacy_mode": "styles_and_page_setup_only",
            },
            "section_order": list(ENTRY_PLAN_SECTION_CODES),
            "required_fact_fields": list(DEFAULT_REQUIRED_FACT_FIELDS),
            "is_active": True,
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": actor,
            "approved_at": now,
        }
        _, created = DocumentTemplate.objects.update_or_create(
            code=row["template_id"].strip(),
            version="phase0-v1",
            create_defaults={**template_defaults, "created_by": actor},
            defaults=template_defaults,
        )
        template_created += int(created)
        template_updated += int(not created)

    clause_created = 0
    clause_updated = 0
    seen_matrix_ids: set[str] = set()
    for row in clause_rows:
        matrix_id = row["matrix_id"].strip()
        matrix = matrix_by_id.get(matrix_id)
        if matrix is None:
            raise ValueError(f"条款 {row['clause_code']} 缺少已批准适用矩阵")
        if (
            matrix["clause_code"].strip() != row["clause_code"].strip()
            or matrix["clause_version"].strip() != row["clause_version"].strip()
            or matrix["section_code"].strip() != row["section_code"].strip()
        ):
            raise ValueError(f"条款 {row['clause_code']} 与适用矩阵不一致")
        seen_matrix_ids.add(matrix_id)
        clause_defaults = {
            "business_type": BUSINESS_TYPE,
            "section_code": row["section_code"].strip(),
            "text": row["text"].strip(),
            "risk_conditions": [matrix["risk_code"].strip()],
            "is_active": True,
            "approval_status": ApprovalStatus.APPROVED,
            "approved_by": actor,
            "approved_at": now,
        }
        _, created = ClauseBlock.objects.update_or_create(
            code=row["clause_code"].strip(),
            version=row["clause_version"].strip(),
            create_defaults={**clause_defaults, "created_by": actor},
            defaults=clause_defaults,
        )
        clause_created += int(created)
        clause_updated += int(not created)
    unused_matrix_ids = sorted(set(matrix_by_id) - seen_matrix_ids)
    if unused_matrix_ids:
        raise ValueError(f"适用矩阵缺少批准条款正文：{', '.join(unused_matrix_ids)}")

    source_version_ids = {chunk.source_document_version_id for chunk in knowledge_chunks}
    existing_version_ids = set(
        DocumentVersion.objects.filter(pk__in=source_version_ids).values_list("pk", flat=True)
    )
    missing_version_ids = sorted(source_version_ids - existing_version_ids)
    if missing_version_ids:
        raise ValueError(f"RAG知识引用的文档版本不存在：{missing_version_ids}")

    knowledge_created = 0
    knowledge_updated = 0
    for chunk in knowledge_chunks:
        if chunk.business_type != BUSINESS_TYPE or chunk.approval_status != "approved":
            raise ValueError(f"知识块 {chunk.chunk_id} 不属于一期已批准知识")
        _, created = KnowledgeSection.objects.update_or_create(
            chunk_id=chunk.chunk_id,
            defaults={
                "source_document_version_id": chunk.source_document_version_id,
                "business_type": chunk.business_type,
                "client_code": chunk.client_code or "",
                "section_code": chunk.section_code,
                "heading_path": list(chunk.heading_path),
                "paragraph_start": chunk.paragraph_start,
                "paragraph_end": chunk.paragraph_end,
                "locator": {
                    "heading_path": list(chunk.heading_path),
                    "paragraph_start": chunk.paragraph_start,
                    "paragraph_end": chunk.paragraph_end,
                },
                "text": chunk.text,
                "block_type": chunk.block_type,
                "structured_content": {
                    "rows": [list(row) for row in chunk.structured_rows]
                },
                "content_sha256": chunk.content_sha256,
                "component_tags": list(chunk.component_tags),
                "method_tags": list(chunk.method_tags),
                "risk_tags": list(chunk.risk_tags),
                "embedding": list(chunk.embedding),
                "embedding_model_alias": chunk.embedding_model_alias,
                "embedding_dimension": chunk.embedding_dimension,
                "is_active": True,
                "approval_status": ApprovalStatus.APPROVED,
                "approved_by": actor,
                "approved_at": now,
            },
        )
        knowledge_created += int(created)
        knowledge_updated += int(not created)

    result = BootstrapResult(
        templates_created=template_created,
        templates_updated=template_updated,
        clauses_created=clause_created,
        clauses_updated=clause_updated,
        knowledge_created=knowledge_created,
        knowledge_updated=knowledge_updated,
        dry_run=dry_run,
    )
    if dry_run:
        transaction.set_rollback(True)
    else:
        audit_log(
            user=actor,
            action="document_generation.bootstrap",
            resource_type="DocumentAgentBaseline",
            resource_id="phase0-v1",
            result="success",
            after_data={
                "templates_created": result.templates_created,
                "templates_updated": result.templates_updated,
                "clauses_created": result.clauses_created,
                "clauses_updated": result.clauses_updated,
                "knowledge_created": result.knowledge_created,
                "knowledge_updated": result.knowledge_updated,
            },
        )
    return result
