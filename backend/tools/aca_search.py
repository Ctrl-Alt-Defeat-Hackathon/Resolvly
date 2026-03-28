"""
ACA Provisions Search Tool

Fetches ACA § 2719 internal/external review rules from HHS.gov and CMS.
Used by the Regulation Agent for marketplace, fully-insured employer, and
individual market plans.

Key provisions:
  - ACA § 2719 (codified at 42 U.S.C. § 300gg-19): Internal/external review
  - 45 CFR § 147.136: Internal claims and appeals
  - 45 CFR § 147.138: External review (state and federal processes)
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from tools.ecfr_search import search_ecfr

logger = logging.getLogger(__name__)


class ACAResult(BaseModel):
    appeal_process: list[str] = []
    internal_appeal_deadline_days: int = 180
    external_review_deadline_months: int = 4
    plan_internal_review_deadline_days: int = 60
    expedited_turnaround_hours: int = 72
    external_review_available: bool = True
    required_notice_elements: list[str] = []
    legal_citations: list[dict] = []
    source: str = "ACA § 2719 / 45 CFR § 147.136"
    source_url: str = "https://www.cms.gov/cciio/resources/fact-sheets-and-faqs/aca_implementation_faqs"
    raw_text: str = ""


_ACA_APPEAL_PROCESS = [
    "Request an internal appeal from your insurance plan within 180 days of receiving the denial notice",
    "The plan must complete the internal appeal within 60 days (post-service) or 30 days (pre-service)",
    "For urgent/concurrent care, request expedited review — the plan must decide within 72 hours",
    "If the internal appeal is denied, request external review by an Independent Review Organization (IRO)",
    "External review must be requested within 4 months of the internal appeal denial",
    "The IRO must complete standard external review within 45 days",
    "For urgent cases, expedited external review must be completed within 72 hours",
    "The IRO's decision is binding on the insurance plan",
    "You may also file a complaint with your state's Department of Insurance",
]

_ACA_REQUIRED_NOTICE_ELEMENTS = [
    "Specific reason for denial, including clinical rationale",
    "Reference to the specific plan provision or clinical standard on which denial is based",
    "A description of the scientific or clinical evidence used in decision",
    "Notice of the right to request an internal appeal",
    "Notice of the right to request external review by an IRO",
    "Notice of the right to file a complaint with the state Department of Insurance",
    "For urgent claims: notice of the right to request expedited external review simultaneously with internal appeal",
    "Contact information for the plan's appeals department",
    "Disclosure of any internal rule, guideline, or criteria relied upon",
]

_ACA_LEGAL_CITATIONS = [
    {
        "law": "ACA",
        "section": "§ 2719 (42 U.S.C. § 300gg-19)",
        "relevance": "Requires internal and external appeals for adverse benefit determinations",
        "url": "https://www.law.cornell.edu/uscode/text/42/300gg-19",
    },
    {
        "law": "45 CFR",
        "section": "§ 147.136",
        "relevance": "HHS regulation implementing ACA internal claims and appeals requirements",
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.136",
    },
    {
        "law": "45 CFR",
        "section": "§ 147.138",
        "relevance": "HHS regulation implementing ACA external review requirements",
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.138",
    },
]


async def search_aca_provisions(plan_type: str = "", denial_type: str = "") -> ACAResult:
    """
    Fetch ACA § 2719 internal/external review requirements.
    """
    ecfr_result = await search_ecfr(
        query="ACA internal external review appeal 2719",
        cfr_section="45 CFR 147.136",
    )

    raw_text = ecfr_result.excerpt if ecfr_result.found else ""

    plan_internal_review_deadline = 60
    if denial_type in ("pre_service", "preservice", "prior_authorization"):
        plan_internal_review_deadline = 30

    return ACAResult(
        appeal_process=_ACA_APPEAL_PROCESS,
        internal_appeal_deadline_days=180,
        external_review_deadline_months=4,
        plan_internal_review_deadline_days=plan_internal_review_deadline,
        expedited_turnaround_hours=72,
        external_review_available=True,
        required_notice_elements=_ACA_REQUIRED_NOTICE_ELEMENTS,
        legal_citations=_ACA_LEGAL_CITATIONS,
        raw_text=raw_text,
    )
