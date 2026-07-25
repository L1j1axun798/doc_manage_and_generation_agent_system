from __future__ import annotations

from collections.abc import Sequence

from .engine.contracts import ConfirmedFact, RiskEvidence, RiskProfile
from .engine.errors import AgentError
from .models import ApprovalStatus, ClauseBlock


class ORMRiskProfiler:
    def build(self, facts: Sequence[ConfirmedFact]) -> RiskProfile:
        approved_codes = self._approved_risk_codes()
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
                risk_code = risk_code.strip()
                if risk_code not in approved_codes:
                    raise AgentError(
                        "RISK_CODE_UNAPPROVED",
                        f"风险编码 {risk_code} 没有已批准的适用条款",
                    )
                if not evidence.strip():
                    raise AgentError("RISK_EVIDENCE_INVALID", "风险证据说明不得为空")
                evidence_by_code.setdefault(
                    risk_code,
                    RiskEvidence(
                        risk_code=risk_code,
                        evidence=evidence.strip(),
                        source_document_version_id=fact.source_document_version_id,
                        locator=fact.locator,
                    ),
                )
        codes = tuple(sorted(evidence_by_code))
        return RiskProfile(
            risk_codes=codes,
            evidence=tuple(evidence_by_code[code] for code in codes),
        )

    @staticmethod
    def _approved_risk_codes() -> set[str]:
        approved: set[str] = set()
        conditions = ClauseBlock.objects.filter(
            is_active=True,
            approval_status=ApprovalStatus.APPROVED,
        ).values_list("risk_conditions", flat=True)
        for values in conditions:
            approved.update(
                value.strip() for value in values if isinstance(value, str) and value.strip()
            )
        return approved
