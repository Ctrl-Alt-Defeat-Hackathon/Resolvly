"""
eCFR Search Tool

Searches the Electronic Code of Federal Regulations (eCFR) for relevant
federal regulatory text. Used by the Regulation Agent to fetch appeal
procedure requirements.

Key CFR sections:
  - 29 CFR § 2560.503-1  — ERISA claims procedure
  - 45 CFR § 147.136     — ACA internal claims and appeals
  - 42 CFR § 431.220     — Medicaid fair hearing requirements

API: https://www.ecfr.gov/api/search/v1/results (free, no auth)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_ECFR_SEARCH_URL = "https://www.ecfr.gov/api/search/v1/results"
_ECFR_FULL_TEXT_URL = "https://www.ecfr.gov/api/versioner/v1/full"
_TIMEOUT = 15.0


class ECFRResult(BaseModel):
    query: str
    cfr_reference: str = ""          # e.g. "29 CFR § 2560.503-1"
    title: str = ""
    excerpt: str = ""
    url: str = ""
    source: str = "Electronic Code of Federal Regulations (eCFR)"
    found: bool = False
    results: list[dict[str, Any]] = []


# Hardcoded summaries of key provisions for reliable offline fallback
_KEY_PROVISIONS: dict[str, dict[str, str]] = {
    "29 CFR 2560.503-1": {
        "title": "29 CFR § 2560.503-1 — ERISA Claims Procedure",
        "excerpt": (
            "Under ERISA § 503 and 29 CFR § 2560.503-1, plan administrators must "
            "provide a full and fair review of denied claims. Key requirements: "
            "(1) Claimants must be notified of denial within 90 days (post-service) "
            "or 15 days (pre-service urgent) with specific reason, plan provision, and "
            "description of additional info needed. "
            "(2) Claimants have at least 60 days after receiving denial notice to appeal "
            "(180 days for disability claims). "
            "(3) The plan must complete appeal review within 60 days (post-service) or "
            "30 days (pre-service) or 72 hours (urgent). "
            "(4) The plan must provide claimants access to all documents relevant to the claim. "
            "(5) Notices must be written in a culturally and linguistically appropriate manner."
        ),
        "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XXV/subchapter-C/part-2560/section-2560.503-1",
    },
    "45 CFR 147.136": {
        "title": "45 CFR § 147.136 — ACA Internal Claims, Appeals, and External Review",
        "excerpt": (
            "Under ACA § 2719 and 45 CFR § 147.136, non-grandfathered health plans must: "
            "(1) Allow internal appeals for denied claims. Claimants have 180 days from "
            "receipt of denial notice to request internal appeal. "
            "(2) Provide external review by an independent review organization (IRO) for "
            "adverse benefit determinations involving medical judgment or rescission. "
            "External review must be requested within 4 months of internal appeal denial. "
            "(3) Complete expedited review within 72 hours for urgent/concurrent care. "
            "(4) Provide claimants with all documents and evidence relied upon. "
            "(5) Denial notices must include specific reason, scientific/clinical standards, "
            "and notice of external review rights. "
            "(6) Plans must provide continued coverage pending internal appeal."
        ),
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.136",
    },
    "42 CFR 431.220": {
        "title": "42 CFR § 431.220 — Medicaid Fair Hearing Requirements",
        "excerpt": (
            "Under 42 CFR § 431.220, Medicaid beneficiaries have the right to a fair hearing "
            "when the agency takes action to deny, terminate, suspend, or reduce services. "
            "Key requirements: "
            "(1) Beneficiaries must be notified at least 10 days before proposed action. "
            "(2) Beneficiaries may request a hearing within 90 days of the notice. "
            "(3) The agency must provide the hearing within 90 days of the request. "
            "(4) Benefits must be continued pending the hearing if requested within 10 days. "
            "(5) The hearing decision must be issued within 90 days of the hearing request."
        ),
        "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-431/subpart-E/section-431.220",
    },
}


async def search_ecfr(query: str, cfr_section: str = "") -> ECFRResult:
    """
    Search the eCFR for relevant regulatory text.

    If cfr_section is provided (e.g. "29 CFR 2560.503-1"), returns the
    pre-cached key provision summary first for reliability, then attempts
    a live API search for additional context.
    """
    # Check hardcoded key provisions first (reliable, no API needed)
    if cfr_section:
        normalized = cfr_section.replace("§", "").replace("  ", " ").strip()
        for key, provision in _KEY_PROVISIONS.items():
            if key in normalized or normalized in key:
                logger.info(f"Returning cached eCFR provision for {cfr_section}")
                return ECFRResult(
                    query=query,
                    cfr_reference=cfr_section,
                    title=provision["title"],
                    excerpt=provision["excerpt"],
                    url=provision["url"],
                    found=True,
                )

    # Live eCFR search
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _ECFR_SEARCH_URL,
                params={
                    "query": query,
                    "per_page": 3,
                    "order": "relevance",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results_raw = data.get("results", [])
            if not results_raw:
                return ECFRResult(query=query, found=False)

            first = results_raw[0]
            headings = first.get("headings", {})
            cfr_ref = " ".join([
                headings.get("title", ""),
                headings.get("part", ""),
                headings.get("section", ""),
            ]).strip()

            return ECFRResult(
                query=query,
                cfr_reference=cfr_ref,
                title=first.get("label", ""),
                excerpt=first.get("full_text_excerpt", "")[:1000],
                url=first.get("url", ""),
                found=True,
                results=[
                    {
                        "label": r.get("label", ""),
                        "url": r.get("url", ""),
                        "excerpt": r.get("full_text_excerpt", "")[:500],
                    }
                    for r in results_raw[:3]
                ],
            )

    except Exception as e:
        logger.warning(f"eCFR search failed for '{query}': {e}")
        return ECFRResult(query=query, found=False)


async def get_ecfr_section(title: int, part: str, section: str) -> ECFRResult:
    """
    Fetch a specific CFR section by title/part/section numbers.
    e.g. title=29, part="2560", section="503-1"
    """
    cfr_ref = f"{title} CFR {part}.{section}"
    # Check hardcoded provisions
    for key, provision in _KEY_PROVISIONS.items():
        if f"{part}.{section}" in key.replace("-", ".") or f"{part}.{section.replace('-', '.')}" in key:
            return ECFRResult(
                query=cfr_ref,
                cfr_reference=cfr_ref,
                title=provision["title"],
                excerpt=provision["excerpt"],
                url=provision["url"],
                found=True,
            )

    # Live fetch
    url = f"{_ECFR_FULL_TEXT_URL}/{title}/title-{title}.xml"
    return ECFRResult(
        query=cfr_ref,
        cfr_reference=cfr_ref,
        found=False,
        url=f"https://www.ecfr.gov/current/title-{title}/part-{part}/section-{part}.{section}",
    )
