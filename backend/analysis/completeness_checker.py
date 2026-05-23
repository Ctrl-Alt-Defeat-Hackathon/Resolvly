"""
Denial Letter Completeness Checker

Validates denial letters against ACA § 2719 / ERISA § 503 required field
checklists. Produces a completeness score (0–1), list of missing fields,
and an escalation recommendation.

ACA § 2719 required elements in denial notices:
1. Specific reason for denial
2. Reference to specific plan provision
3. Scientific/clinical evidence used
4. Description of internal appeal process
5. Notice of external review rights
6. Notice of state DOI complaint rights
7. Contact info for insurer appeals
8. Statement of clinical criteria (for medical necessity denials)
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel

from extraction.schema import ClaimObject, RegulationType

logger = logging.getLogger(__name__)


class CompletenessResult(BaseModel):
    score: float               # 0.0 – 1.0
    missing_fields: list[str]
    present_fields: list[str]
    deficient: bool            # score < 0.75
    escalation_available: bool
    escalation_reason: str = ""
    regulation_standard: str = ""


def check_completeness(claim: ClaimObject) -> CompletenessResult:
    """
    Check how complete the denial letter is against regulatory requirements.

    Weighted scoring: critical fields (denial reason, clinical criteria) count 2×;
    all others count 1×.
    """
    regulation_type = claim.identification.erisa_or_state_regulated or RegulationType.unknown
    denial = claim.denial_reason
    appeal = claim.appeal_rights
    narrative_lower = (denial.denial_reason_narrative or "").lower()

    # (name, present, weight) — critical fields use weight=2
    checks: list[tuple[str, bool, int]] = [
        # Core denial info — critical (weight 2)
        (
            "Specific denial reason or narrative",
            bool(denial.denial_reason_narrative and len(denial.denial_reason_narrative) > 20),
            2,
        ),
        (
            "Clinical criteria or scientific evidence cited",
            bool(denial.clinical_criteria_cited or denial.medical_necessity_statement),
            2,
        ),
        # Standard required elements (weight 1)
        (
            "Reference to specific plan provision cited",
            bool(denial.plan_provision_cited),
            1,
        ),
        (
            "Claim adjustment reason code(s) provided",
            bool(denial.carc_codes),
            1,
        ),
        (
            "Internal appeal process described",
            bool(appeal.internal_appeal_deadline_stated),
            1,
        ),
        (
            "External review rights mentioned",
            bool(appeal.external_review_deadline_stated),
            1,
        ),
        (
            "Expedited review availability noted",
            appeal.expedited_review_available is True,
            1,
        ),
        (
            "Insurer appeals contact information provided",
            bool(
                appeal.insurer_appeals_contact_name
                or appeal.insurer_appeals_phone
                or appeal.insurer_appeals_address
            ),
            1,
        ),
        (
            "State insurance commissioner reference included",
            bool(appeal.state_commissioner_info_present),
            1,
        ),
    ]

    # ERISA-specific checks (weight 1 each)
    if regulation_type == RegulationType.erisa:
        # § 503 / 29 CFR § 2560.503-1: notice of civil action rights under § 502(a)
        erisa_502_mentioned = any(
            t in narrative_lower for t in ("502", "civil action", "federal court", "erisa")
        )
        checks.append(("ERISA § 502(a) civil action rights mentioned", erisa_502_mentioned, 1))

        # 29 CFR § 2560.503-1(g)(1)(vii): right to submit additional information during appeal
        right_to_submit = any(
            t in narrative_lower
            for t in ("additional information", "supporting documentation", "new evidence", "submit")
        )
        checks.append(("Right to submit additional information during appeal", right_to_submit, 1))

        # 29 CFR § 2560.503-1(h)(2)(iii): right to receive plan documents upon request
        plan_docs_mentioned = any(
            t in narrative_lower
            for t in ("plan documents", "summary plan description", "spd", "plan document")
        )
        checks.append(("Right to receive plan documents upon request", plan_docs_mentioned, 1))

    present = [name for name, present, _ in checks if present]
    missing = [name for name, present, _ in checks if not present]

    weighted_present = sum(w for _, p, w in checks if p)
    weighted_total = sum(w for _, _, w in checks)
    score = weighted_present / weighted_total if weighted_total else 0.0
    deficient = score < 0.75

    # Determine escalation availability
    escalation_available = deficient or len(missing) >= 3
    escalation_reason = ""
    if deficient:
        escalation_reason = (
            f"Denial letter is missing {len(missing)} of {len(checks)} required elements. "
            "A deficient denial notice may be grounds for escalation or complaint."
        )
        if regulation_type == RegulationType.erisa:
            escalation_reason += " Under ERISA § 503, a procedurally deficient denial is itself grounds for appeal."
        elif regulation_type in (RegulationType.state, RegulationType.unknown):
            escalation_reason += " Under ACA § 2719, missing required notice elements may be reported to your state Department of Insurance."

    regulation_standard = {
        RegulationType.erisa: "ERISA § 503 / 29 CFR § 2560.503-1",
        RegulationType.state: "ACA § 2719 / 45 CFR § 147.136",
        RegulationType.medicaid: "42 CFR § 431.206 — Medicaid Notice Requirements",
        RegulationType.unknown: "ACA § 2719 (assumed)",
    }.get(regulation_type, "ACA § 2719")

    return CompletenessResult(
        score=round(score, 2),
        missing_fields=missing,
        present_fields=present,
        deficient=deficient,
        escalation_available=escalation_available,
        escalation_reason=escalation_reason,
        regulation_standard=regulation_standard,
    )
