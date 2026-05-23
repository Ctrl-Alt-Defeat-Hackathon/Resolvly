"""
State DOI Search Tool

Primary source: curated `data/state_appeal_rules.json` for the top 10 states.
Fallback: live web search restricted to .gov domains for all other states.

This design makes appeal deadlines reliable and citation-ready for the top-10
states (covering ~65% of US population) while still serving the remaining 40
states through web search until they are curated.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tools.state_doi_lookup import get_doi_contact
from tools.web_search import web_search

logger = logging.getLogger(__name__)

_STATE_RULES_PATH = Path(__file__).parent.parent / "data" / "state_appeal_rules.json"
_STATE_RULES: dict[str, Any] = {}

try:
    with open(_STATE_RULES_PATH) as _f:
        _raw = json.load(_f)
        _STATE_RULES = {k: v for k, v in _raw.items() if not k.startswith("_")}
except Exception as _e:
    logger.warning(f"Could not load state_appeal_rules.json: {_e}")


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


def _curated_appeal_rules(state: str, rules_entry: dict[str, Any]) -> list[str]:
    """Build authoritative, citation-ready appeal rules from the curated JSON entry."""
    internal = rules_entry.get("internal_appeal_days", 180)
    external = rules_entry.get("external_review_days", 120)
    authority = rules_entry.get("external_review_authority", "your state Department of Insurance")
    statute = rules_entry.get("external_review_statute", "")
    source_url = rules_entry.get("source_url", "")
    notes = rules_entry.get("notes", "")
    citation = f" ({statute})" if statute else ""

    rules = [
        f"File an internal appeal with your insurer within {internal} days of the denial notice (ACA § 2719).",
        f"If the internal appeal is denied, request external independent review through the {authority}{citation} within {external} days of the internal denial.",
        "External review by an Independent Review Organization (IRO) is binding on the insurer and free for you.",
    ]
    if notes:
        rules.append(notes)
    if source_url:
        rules.append(f"Official source: {source_url}")
    return rules


async def _appeal_rules_from_web(state: str, doi_name: str) -> list[str]:
    """Web search fallback for states not in the curated JSON. Restricted to .gov domains."""
    rules: list[str] = []
    q = f"{doi_name} health insurance internal appeal deadline external review site:.gov"
    try:
        ws = await web_search(q, num_results=3)
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
    Fetch state DOI information for a claim.

    Primary source: curated state_appeal_rules.json (top 10 states).
    Fallback: live web search restricted to .gov domains for all other states.
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

    # Primary: serve curated appeal rules if this state is in the curated JSON
    curated = _STATE_RULES.get(state)
    if curated:
        result.appeal_rules = _curated_appeal_rules(state, curated)
        logger.info(f"State rules for {state}: served from curated JSON (verified {curated.get('last_verified', 'unknown')})")
    else:
        # Fallback: web search for states not yet curated
        logger.info(f"State rules for {state}: falling back to web search (not in curated JSON)")
        result.appeal_rules = await _appeal_rules_from_web(
            state, result.doi_name or f"{state} Department of Insurance"
        )
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
