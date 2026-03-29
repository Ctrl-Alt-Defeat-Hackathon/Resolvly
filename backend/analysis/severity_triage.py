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

    Urgent:         < 30 days to deadline OR expedited review noted OR amount > $10,000
    Time-Sensitive: < 60 days to deadline OR amount > $3,000
    Routine:        otherwise
    """
    urgent_signals = 0
    time_sensitive_signals = 0

    # Signal 1: Days remaining until deadline
    if internal_deadline:
        days_left = (internal_deadline - date.today()).days
        if days_left < 0:
            # Already passed — still flag as urgent to prompt action
            urgent_signals += 3
        elif days_left < 30:
            urgent_signals += 2
        elif days_left < 60:
            time_sensitive_signals += 1

    # Signal 2: Denied amount
    denied = claim.financial.denied_amount
    if denied is not None:
        if denied >= 10000:
            urgent_signals += 1
        elif denied >= 3000:
            time_sensitive_signals += 1

    # Signal 3: Expedited review explicitly noted in denial letter
    if claim.appeal_rights.expedited_review_available is True:
        urgent_signals += 1

    # Signal 4: Prior auth denial — often time-sensitive (patient awaiting treatment)
    if claim.denial_reason.prior_auth_status in ("required_not_obtained", "denied"):
        time_sensitive_signals += 1

    # Signal 5: Ongoing treatment / medical necessity denial
    # Inferred from denial narrative keywords
    narrative = (claim.denial_reason.denial_reason_narrative or "").lower()
    urgent_keywords = ["emergency", "urgent", "life-threatening", "hospitalized", "icu", "surgery scheduled"]
    if any(kw in narrative for kw in urgent_keywords):
        urgent_signals += 2

    # Classify
    if urgent_signals >= 2:
        return SeverityTriage.urgent
    elif urgent_signals >= 1 or time_sensitive_signals >= 2:
        return SeverityTriage.time_sensitive
    else:
        return SeverityTriage.routine
