"""
Deadline Calculator

Computes appeal deadlines from the date of denial based on regulation type.

Rules:
  - ERISA post-service:    claimant has 180 days to appeal
  - ERISA pre-service:     claimant has 180 days to appeal
  - ACA/state:             claimant has 180 days internal, 4 months external
  - Medicaid:              claimant has 90 days for fair hearing
  - Expedited:             72 hours if urgent / concurrent care
"""
from __future__ import annotations

import logging
import datetime as dt
from typing import Optional

from pydantic import BaseModel

from extraction.schema import ClaimObject, RegulationType, SeverityTriage

logger = logging.getLogger(__name__)


class DeadlineInfo(BaseModel):
    deadline_date: Optional[dt.date] = None
    days_remaining: Optional[int] = None
    source: str = ""
    already_passed: bool = False


class AppealDeadlines(BaseModel):
    internal_appeal: DeadlineInfo = DeadlineInfo()
    external_review: DeadlineInfo = DeadlineInfo()
    expedited: DeadlineInfo = DeadlineInfo()
    expedited_available: bool = False
    expedited_qualifier: str = ""
    ics_events: list[dict] = []


def _days_remaining(deadline: dt.date) -> int:
    return (deadline - dt.date.today()).days


def _build_ics_event(title: str, event_date: dt.date, description: str) -> dict:
    """Build an ICS-compatible event dict for calendar export."""
    return {
        "title": title,
        "date": event_date.isoformat(),
        "description": description,
        "alarm_days_before": 14,
    }


def calculate_deadlines(
    claim: ClaimObject,
    severity: SeverityTriage = SeverityTriage.routine,
) -> AppealDeadlines:
    """
    Compute all appeal deadlines based on denial date and regulation type.
    """
    denial_date = claim.identification.date_of_denial
    regulation_type = claim.identification.erisa_or_state_regulated

    if denial_date is None:
        logger.warning("No date_of_denial on claim — cannot calculate deadlines")
        return AppealDeadlines()

    deadlines = AppealDeadlines()
    ics_events: list[dict] = []

    if regulation_type == RegulationType.erisa:
        # ERISA: 180 days from denial to file internal appeal
        internal_date = denial_date + dt.timedelta(days=180)
        days_left = _days_remaining(internal_date)
        deadlines.internal_appeal = DeadlineInfo(
            deadline_date=internal_date,
            days_remaining=days_left,
            source="ERISA § 503 / 29 CFR § 2560.503-1 — 180 days",
            already_passed=days_left < 0,
        )
        ics_events.append(_build_ics_event(
            "ERISA Internal Appeal Deadline",
            internal_date,
            "Last day to file internal ERISA appeal per 29 CFR § 2560.503-1",
        ))

        # Self-funded ERISA: no state external review; must sue under § 502(a)
        deadlines.external_review = DeadlineInfo(
            source="ERISA self-funded plans: file civil action under § 502(a) after exhausting internal appeals",
        )

    elif regulation_type in (RegulationType.state, RegulationType.unknown):
        # ACA § 2719 / state rules: 180 days internal, 4 months external
        internal_date = denial_date + dt.timedelta(days=180)
        days_left_internal = _days_remaining(internal_date)
        deadlines.internal_appeal = DeadlineInfo(
            deadline_date=internal_date,
            days_remaining=days_left_internal,
            source="ACA § 2719 / 45 CFR § 147.136 — 180 days",
            already_passed=days_left_internal < 0,
        )
        ics_events.append(_build_ics_event(
            "Internal Appeal Deadline",
            internal_date,
            "Last day to file internal appeal per ACA § 2719",
        ))

        # External review: 4 months (~122 days) from internal appeal denial
        external_date = internal_date + dt.timedelta(days=122)
        days_left_external = _days_remaining(external_date)
        deadlines.external_review = DeadlineInfo(
            deadline_date=external_date,
            days_remaining=days_left_external,
            source="ACA § 2719 — 4 months after internal appeal denial",
            already_passed=days_left_external < 0,
        )
        ics_events.append(_build_ics_event(
            "External Review Deadline (Estimated)",
            external_date,
            "Estimated last day to request external review per ACA § 2719. Actual deadline is 4 months from internal appeal denial date.",
        ))

    elif regulation_type == RegulationType.medicaid:
        # Medicaid: 90 days for fair hearing request
        internal_date = denial_date + dt.timedelta(days=90)
        days_left = _days_remaining(internal_date)
        deadlines.internal_appeal = DeadlineInfo(
            deadline_date=internal_date,
            days_remaining=days_left,
            source="42 CFR § 431.220 — 90 days from notice",
            already_passed=days_left < 0,
        )
        ics_events.append(_build_ics_event(
            "Medicaid Fair Hearing Deadline",
            internal_date,
            "Last day to request Medicaid fair hearing per 42 CFR § 431.220",
        ))

    # Expedited review
    expedited_qualifies = (
        severity == SeverityTriage.urgent or
        claim.appeal_rights.expedited_review_available is True
    )

    if expedited_qualifies:
        expedited_date = dt.date.today() + dt.timedelta(days=3)
        deadlines.expedited_available = True
        deadlines.expedited_qualifier = (
            "Patient is in an urgent clinical situation requiring immediate treatment decision"
            if severity == SeverityTriage.urgent
            else "Expedited review was noted as available in the denial notice"
        )
        deadlines.expedited = DeadlineInfo(
            deadline_date=expedited_date,
            days_remaining=3,
            source="ACA § 2719 / 29 CFR § 2560.503-1 — 72 hours for urgent care",
        )
        ics_events.append(_build_ics_event(
            "URGENT: Expedited Review Request",
            expedited_date,
            "Request expedited review immediately — insurer must respond within 72 hours",
        ))

    deadlines.ics_events = ics_events
    return deadlines
