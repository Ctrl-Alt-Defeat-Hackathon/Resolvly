"""
Indiana DOI (IDOI) Search Tool

Provides Indiana Department of Insurance information for state-regulated
(fully-insured) health insurance claims. Indiana-first implementation.

Sources:
  - Static DOI contact data from state_doi_contacts.json
  - Web search fallback for specific IDOI regulatory content
  - IDOI website: https://www.in.gov/idoi/
"""
from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from tools.state_doi_lookup import get_doi_contact
from tools.web_search import web_search

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0


class IDOIResult(BaseModel):
    state: str
    doi_name: str = ""
    doi_phone: str = ""
    doi_address: str = ""
    doi_complaint_url: str = ""
    doi_website: str = ""
    external_review_url: str = ""
    consumer_guide_url: str = ""
    appeal_rules: list[str] = []
    state_deadlines: dict[str, str] = {}
    consumer_resources: list[dict] = []
    external_review_available: bool = True
    source: str = "State Department of Insurance"
    found: bool = False


# Indiana-specific appeal rules (state-regulated/fully-insured plans)
_INDIANA_APPEAL_RULES = [
    "Indiana law requires insurers to provide internal appeals for all adverse benefit determinations",
    "You have 180 days from the denial notice to file an internal appeal",
    "The insurer must respond to your appeal within 60 days (standard) or 72 hours (urgent/expedited)",
    "Indiana participates in the URAC-accredited external review process",
    "After exhausting internal appeals, you may request external review by an Independent Review Organization",
    "File a complaint with the Indiana Department of Insurance (IDOI) at any time",
    "IDOI investigates complaints against insurance companies for improper denials",
    "Indiana law requires coverage for emergency services without prior authorization",
]

_INDIANA_DEADLINES = {
    "internal_appeal": "180 days from denial notice",
    "insurer_response_standard": "60 days",
    "insurer_response_urgent": "72 hours",
    "external_review": "4 months after internal appeal denial",
    "external_review_decision": "45 days (standard) / 72 hours (expedited)",
    "complaint_to_idoi": "No strict deadline, but prompt filing recommended",
}

_INDIANA_CONSUMER_RESOURCES = [
    {
        "name": "IDOI Consumer Complaint",
        "description": "File a complaint against an insurer for improper denial",
        "url": "https://www.in.gov/idoi/consumers/file-a-complaint/",
    },
    {
        "name": "IDOI External Review",
        "description": "Request independent review of your insurer's decision",
        "url": "https://www.in.gov/idoi/consumers/health-insurance/external-review/",
    },
    {
        "name": "IDOI Health Insurance Consumer Guide",
        "description": "Guide to understanding your health insurance rights in Indiana",
        "url": "https://www.in.gov/idoi/consumers/health-insurance/",
    },
    {
        "name": "Indiana Legal Services",
        "description": "Free legal help for low-income Hoosiers with insurance problems",
        "url": "https://www.indianalegalservices.org/",
    },
]


async def search_idoi(state: str = "IN", query: str = "") -> IDOIResult:
    """
    Fetch state DOI information, with Indiana-specific detail for IN.
    """
    state = state.upper().strip()
    doi_contact = get_doi_contact(state)

    if not doi_contact:
        logger.warning(f"No DOI contact data found for state: {state}")
        return IDOIResult(state=state, found=False)

    result = IDOIResult(
        state=state,
        doi_name=doi_contact.get("name", ""),
        doi_phone=doi_contact.get("phone", ""),
        doi_address=doi_contact.get("address", ""),
        doi_complaint_url=doi_contact.get("complaint_url", ""),
        doi_website=doi_contact.get("website", ""),
        external_review_url=doi_contact.get("external_review_url", ""),
        consumer_guide_url=doi_contact.get("consumer_guide_url", ""),
        external_review_available=True,
        found=True,
    )

    # Indiana-specific enrichment
    if state == "IN":
        result.appeal_rules = _INDIANA_APPEAL_RULES
        result.state_deadlines = _INDIANA_DEADLINES
        result.consumer_resources = _INDIANA_CONSUMER_RESOURCES
    else:
        # Generic rules for other states based on ACA § 2719
        result.appeal_rules = [
            f"Contact the {doi_contact.get('name', 'state Department of Insurance')} for state-specific appeal rules",
            "Most states require insurers to accept internal appeals within 180 days of denial",
            "External review by an Independent Review Organization is available in most states",
            f"File a complaint at: {doi_contact.get('complaint_url', doi_contact.get('website', ''))}",
        ]
        result.state_deadlines = {
            "internal_appeal": "180 days (ACA minimum — check state rules)",
            "external_review": "4 months after internal appeal denial (ACA minimum)",
        }
        result.consumer_resources = [
            {
                "name": doi_contact.get("name", "State DOI"),
                "description": "Contact your state Department of Insurance for help",
                "url": doi_contact.get("website", ""),
            }
        ]

        # Try web search for state-specific content if query provided
        if query:
            ws_result = await web_search(
                f"{doi_contact.get('name', state + ' Department of Insurance')} {query} health insurance appeal",
                num_results=2,
            )
            if ws_result.found and ws_result.results:
                for r in ws_result.results[:2]:
                    result.consumer_resources.append({
                        "name": r.get("title", ""),
                        "description": r.get("snippet", ""),
                        "url": r.get("link", ""),
                    })

    return result
