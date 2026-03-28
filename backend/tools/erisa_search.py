"""
ERISA Search Tool

Fetches ERISA § 502/§ 503 appeal requirements from DOL.gov and eCFR.
Used by the Regulation Agent when claim is governed by ERISA (employer
self-funded plans).

Key provisions:
  - § 503: Claims procedure requirements
  - § 502: Civil enforcement / right to sue
  - 29 CFR § 2560.503-1: DOL regulation implementing § 503
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from tools.ecfr_search import search_ecfr

logger = logging.getLogger(__name__)


class ERISAResult(BaseModel):
    appeal_process: list[str] = []
    internal_appeal_deadline_days: int = 180
    plan_review_deadline_days: int = 60
    expedited_turnaround_hours: int = 72
    required_notice_elements: list[str] = []
    legal_citations: list[dict] = []
    source: str = "DOL ERISA § 503 / 29 CFR § 2560.503-1"
    source_url: str = "https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/erisa"
    raw_text: str = ""


_ERISA_APPEAL_PROCESS = [
    "File a written internal appeal with the plan administrator within 180 days of receiving the denial notice",
    "Request copies of all plan documents, benefit determination records, and internal guidelines relied upon (free of charge under ERISA § 104(b))",
    "Submit written comments, documents, and records supporting your claim",
    "The plan must complete its review within 60 days (post-service) or 30 days (pre-service) of receiving the appeal",
    "For urgent/concurrent care, the plan must decide within 72 hours",
    "If the internal appeal is denied, you have the right to file a civil action under ERISA § 502(a)",
    "For fully insured ERISA plans, external review may be available under state law",
]

_ERISA_REQUIRED_NOTICE_ELEMENTS = [
    "Specific reason(s) for denial",
    "Reference to specific plan provision(s) on which denial is based",
    "Description of any additional material or information necessary to perfect the claim",
    "Description of the plan's review procedures and time limits",
    "Right to bring civil action under ERISA § 502(a) following appeal denial",
    "Explanation of scientific or clinical judgment (for medical necessity/experimental denials)",
    "Statement of any internal rule, guideline, protocol, or criteria relied upon",
]

_ERISA_LEGAL_CITATIONS = [
    {
        "law": "ERISA",
        "section": "§ 503",
        "relevance": "Claims procedure requirements — plan must provide full and fair review",
        "url": "https://www.law.cornell.edu/uscode/text/29/1133",
    },
    {
        "law": "ERISA",
        "section": "§ 502(a)",
        "relevance": "Civil enforcement — right to bring action to recover benefits after exhausting appeals",
        "url": "https://www.law.cornell.edu/uscode/text/29/1132",
    },
    {
        "law": "29 CFR",
        "section": "§ 2560.503-1",
        "relevance": "DOL regulation implementing ERISA § 503 claims procedure requirements",
        "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XXV/subchapter-C/part-2560/section-2560.503-1",
    },
]


async def search_erisa(plan_type: str = "", denial_type: str = "") -> ERISAResult:
    """
    Fetch ERISA appeal requirements for the given plan/denial context.
    """
    ecfr_result = await search_ecfr(
        query="ERISA claims procedure appeal deadline 503",
        cfr_section="29 CFR 2560.503-1",
    )

    raw_text = ecfr_result.excerpt if ecfr_result.found else ""

    plan_review_deadline = 60
    if denial_type in ("pre_service", "preservice", "prior_authorization"):
        plan_review_deadline = 30

    return ERISAResult(
        appeal_process=_ERISA_APPEAL_PROCESS,
        internal_appeal_deadline_days=180,
        plan_review_deadline_days=plan_review_deadline,
        expedited_turnaround_hours=72,
        required_notice_elements=_ERISA_REQUIRED_NOTICE_ELEMENTS,
        legal_citations=_ERISA_LEGAL_CITATIONS,
        raw_text=raw_text,
    )
