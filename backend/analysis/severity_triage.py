"""
Severity Triage

Classifies claim urgency as Urgent / Time-Sensitive / Routine based on:
  - Days remaining until appeal deadline
  - Denied amount
  - Expedited review eligibility
  - Clinical context (ongoing treatment, urgent condition)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from extraction.schema import ClaimObject, SeverityTriage

logger = logging.getLogger(__name__)


def triage_severity(
    claim: ClaimObject,
    internal_deadline: Optional[date] = None,
) -> SeverityTriage:
    """
    Classify the urgency of the claim denial.

    Immediate urgent rules (bypass scoring):
      - Appeal deadline already passed
      - Expedited review explicitly noted in denial letter

    Continuous score rules (urgent ≥ 2, time-sensitive ≥ 1):
      - Days: max(0, (60 - days_left) / 30)   [0.0 – 2.0+]
      - Financial: $50k+ → +3, $10k+ → +2, $3k+ → +1
      - ICD-10 clinical urgency: oncology (C00-C97), pregnancy (O00-O9A), transplant (Z94) → +2
      - Narrative keywords (emergency, ICU, …) → +2
      - Prior auth denied → +0.5
    """
    # Immediate urgent: deadline passed or expedited review flagged
    if internal_deadline and (internal_deadline - date.today()).days < 0:
        return SeverityTriage.urgent
    if claim.appeal_rights.expedited_review_available is True:
        return SeverityTriage.urgent

    score = 0.0

    # Days remaining — continuous scoring
    if internal_deadline:
        days_left = (internal_deadline - date.today()).days
        score += max(0.0, (60 - days_left) / 30)

    # Financial stakes
    denied = claim.financial.denied_amount
    if denied is not None:
        if denied >= 50_000:
            score += 3
        elif denied >= 10_000:
            score += 2
        elif denied >= 3_000:
            score += 1

    # ICD-10 clinical urgency signals
    icd10_codes = claim.service_billing.icd10_diagnosis_codes
    for code in icd10_codes:
        c = code.upper()
        if not c:
            continue
        if c[0] == "C":            # Malignant neoplasms C00–C97
            score += 2
            break
    for code in icd10_codes:
        c = code.upper()
        if c and c[0] == "O":      # Pregnancy / obstetric O00–O9A
            score += 2
            break
    for code in icd10_codes:
        if code.upper().startswith("Z94"):   # Transplanted organ status
            score += 2
            break

    # Narrative urgency keywords
    narrative = (claim.denial_reason.denial_reason_narrative or "").lower()
    urgent_keywords = ["emergency", "urgent", "life-threatening", "hospitalized", "icu", "surgery scheduled"]
    if any(kw in narrative for kw in urgent_keywords):
        score += 2

    # Prior auth denied — patient may be awaiting treatment
    if claim.denial_reason.prior_auth_status in ("required_not_obtained", "denied"):
        score += 0.5

    # Classify
    if score >= 2:
        return SeverityTriage.urgent
    elif score >= 1:
        return SeverityTriage.time_sensitive
    else:
        return SeverityTriage.routine
