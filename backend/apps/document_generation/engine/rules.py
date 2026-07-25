from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .contracts import (
    ClauseSelection,
    ConfirmedFact,
    RiskEvidence,
    RiskProfile,
)
from .errors import AgentError


@dataclass(frozen=True)
class ApprovedRiskDefinition:
    risk_code: str
    risk_name: str
    default_section_code: str
    severity: str


@dataclass(frozen=True)
class ApprovedClauseBlock:
    clause_code: str
    clause_version: str
    section_code: str
    text: str


class DeterministicRiskProfiler:
    def __init__(self, definitions: Sequence[ApprovedRiskDefinition]) -> None:
        self.definitions = {definition.risk_code: definition for definition in definitions}
        if not self.definitions:
            raise ValueError("at least one approved risk definition is required")

    @classmethod
    def from_csv(cls, path: Path) -> DeterministicRiskProfiler:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["approval_status"] == "approved"]
        return cls(
            [
                ApprovedRiskDefinition(
                    risk_code=row["risk_code"],
                    risk_name=row["risk_name"],
                    default_section_code=row["default_section_code"],
                    severity=row["severity"],
                )
                for row in rows
            ]
        )

    def build(self, facts: Sequence[ConfirmedFact]) -> RiskProfile:
        evidence_by_code: dict[str, RiskEvidence] = {}
        for fact in facts:
            if fact.field != "risk_evidence_items":
                continue
            if not isinstance(fact.value, list):
                raise AgentError("RISK_EVIDENCE_INVALID", "风险证据必须为列表")
            for item in fact.value:
                if not isinstance(item, dict):
                    raise AgentError("RISK_EVIDENCE_INVALID", "风险证据条目必须为对象")
                risk_code = item.get("risk_code")
                evidence = item.get("evidence")
                if not isinstance(risk_code, str) or not isinstance(evidence, str):
                    raise AgentError("RISK_EVIDENCE_INVALID", "风险证据缺少编码或说明")
                if risk_code not in self.definitions:
                    raise AgentError(
                        "RISK_CODE_UNAPPROVED",
                        f"风险编码 {risk_code} 未经过一期批准",
                    )
                if not evidence.strip():
                    raise AgentError("RISK_EVIDENCE_INVALID", "风险证据说明不得为空")
                evidence_by_code.setdefault(
                    risk_code,
                    RiskEvidence(
                        risk_code=risk_code,
                        evidence=evidence,
                        source_document_version_id=fact.source_document_version_id,
                        locator=fact.locator,
                    ),
                )
        risk_codes = tuple(sorted(evidence_by_code))
        return RiskProfile(
            risk_codes=risk_codes,
            evidence=tuple(evidence_by_code[code] for code in risk_codes),
        )


class ApprovedClauseRepository:
    def __init__(
        self,
        *,
        risk_to_clause_ids: Sequence[tuple[str, str]],
        clause_blocks: Sequence[tuple[str, ApprovedClauseBlock]],
    ) -> None:
        self._risk_to_clause_ids = tuple(risk_to_clause_ids)
        self._blocks_by_id = dict(clause_blocks)
        missing = {
            clause_id
            for _, clause_id in self._risk_to_clause_ids
            if clause_id not in self._blocks_by_id
        }
        if missing:
            raise ValueError(f"approved clause text missing for: {sorted(missing)}")

    @classmethod
    def from_csv(
        cls,
        *,
        matrix_path: Path,
        clause_blocks_path: Path,
    ) -> ApprovedClauseRepository:
        with clause_blocks_path.open(encoding="utf-8-sig", newline="") as handle:
            block_rows = [
                row for row in csv.DictReader(handle) if row["approval_status"] == "approved"
            ]
        block_ids = [row["matrix_id"] for row in block_rows]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("approved clause block IDs must be unique")
        if any(not row["text"].strip() for row in block_rows):
            raise ValueError("approved clause block text must not be empty")
        blocks = {
            row["matrix_id"]: ApprovedClauseBlock(
                clause_code=row["clause_code"],
                clause_version=row["clause_version"],
                section_code=row["section_code"],
                text=row["text"],
            )
            for row in block_rows
        }
        with matrix_path.open(encoding="utf-8-sig", newline="") as handle:
            matrix_rows = [
                row
                for row in csv.DictReader(handle)
                if row["approval_status"] == "approved" and row["required_when_matched"] == "yes"
            ]
        mappings: list[tuple[str, str]] = []
        for row in matrix_rows:
            block = blocks.get(row["matrix_id"])
            if block is None:
                raise ValueError(f"missing approved clause block for {row['matrix_id']}")
            if (
                block.clause_code != row["clause_code"]
                or block.clause_version != row["clause_version"]
                or block.section_code != row["section_code"]
            ):
                raise ValueError(f"clause metadata mismatch for {row['matrix_id']}")
            mappings.append((row["risk_code"], row["matrix_id"]))
        return cls(
            risk_to_clause_ids=mappings,
            clause_blocks=tuple(blocks.items()),
        )

    def select(
        self,
        risk_profile: RiskProfile,
        section_code: str,
    ) -> Sequence[ClauseSelection]:
        selected: list[ClauseSelection] = []
        active_risks = set(risk_profile.risk_codes)
        for risk_code, clause_id in self._risk_to_clause_ids:
            block = self._blocks_by_id[clause_id]
            if risk_code not in active_risks or block.section_code != section_code:
                continue
            selected.append(
                ClauseSelection(
                    clause_id=clause_id,
                    clause_code=block.clause_code,
                    clause_version=block.clause_version,
                    section_code=block.section_code,
                    text=block.text,
                    matched_risk_codes=(risk_code,),
                )
            )
        return tuple(selected)
