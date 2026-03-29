"""
Indiana DOI (IDOI) Search Tool

Uses official DOI contact URLs from state_doi_contacts.json (per implementation plan)
and augments appeal guidance with live web search against authoritative domains — not
static legal prose maintained in code.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from tools.state_doi_lookup import get_doi_contact
from tools.web_search import web_search

logger = logging.getLogger(__name__)


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


def _official_consumer_links(doi: dict[str, Any]) -> list[dict[str, str]]:
    """Build resource list from JSON config URLs only (government sources)."""
    out: list[dict[str, str]] = []
    for key, label in (
        ("website", "Official DOI website"),
        ("complaint_url", "File a complaint"),
        ("external_review_url", "External review information"),
        ("consumer_guide_url", "Consumer guides & health insurance help"),
    ):
        url = (doi.get(key) or "").strip()
        if url:
            out.append({"name": label, "description": f"Official state regulator: {doi.get('name', 'DOI')}", "url": url})
    return out


async def _appeal_rules_from_web(state: str, doi_name: str) -> list[str]:
    """Short snippets from web search (official / educational pages); no hardcoded statutes."""
    rules: list[str] = []
    q = f"{doi_name} health insurance internal appeal deadline site:.gov"
    if state == "IN":
        q = "Indiana Department of Insurance health insurance appeal external review site:in.gov"
    try:
        ws = await web_search(q, num_results=4)
        if ws.found and ws.results:
            for r in ws.results:
                snippet = (r.get("snippet") or "").strip()
                title = (r.get("title") or "").strip()
                if len(snippet) > 30:
                    line = f"{title}: {snippet}" if title else snippet
                    rules.append(line[:600])
        if not rules:
            rules.append(
                f"Refer to {doi_name}'s current consumer publications and your denial letter "
                "for appeal deadlines — regulatory timelines vary by plan type (ERISA vs ACA)."
            )
    except Exception as e:
        logger.warning("Web search for appeal rules failed: %s", e)
        rules.append(
            "Use your insurer's denial notice and your state Department of Insurance "
            "consumer site for the most current appeal and external-review steps."
        )
    return rules


async def search_idoi(state: str = "IN", query: str = "") -> IDOIResult:
    """
    Fetch state DOI information; enrich appeal guidance via web search, not hardcoded law text.
    """
    state = state.upper().strip()
    doi_contact = get_doi_contact(state)

    if not doi_contact:
        logger.warning("No DOI contact data found for state: %s", state)
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

    result.consumer_resources = _official_consumer_links(doi_contact)

    # State-specific deadlines: avoid inventing IC citations — point to DOI + live snippets
    result.state_deadlines = {
        "note": "Confirm deadlines on your denial notice and your state DOI consumer site; "
        "federal ACA/ERISA timelines depend on plan type.",
    }

    if state == "IN":
        result.appeal_rules = await _appeal_rules_from_web(state, result.doi_name or "Indiana Department of Insurance")
        if query:
            extra = await web_search(f"site:in.gov idoi {query}", num_results=2)
            if extra.found and extra.results:
                for r in extra.results:
                    sn = (r.get("snippet") or "").strip()
                    if sn:
                        result.appeal_rules.append(sn[:500])
    else:
        result.appeal_rules = await _appeal_rules_from_web(state, result.doi_name or "Department of Insurance")
        if query:
            ws_result = await web_search(
                f"{doi_contact.get('name', state + ' Department of Insurance')} {query} health insurance appeal",
                num_results=2,
            )
            if ws_result.found and ws_result.results:
                for r in ws_result.results[:2]:
                    result.consumer_resources.append(
                        {
                            "name": r.get("title", ""),
                            "description": r.get("snippet", ""),
                            "url": r.get("link", ""),
                        }
                    )

    return result
