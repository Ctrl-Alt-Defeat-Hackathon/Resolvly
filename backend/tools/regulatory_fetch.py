"""
Live regulatory citations for the plan wizard — eCFR API only (no static law text).

Maps wizard routing profiles to eCFR search queries; returns authoritative URLs + excerpts.
"""
from __future__ import annotations

import logging
from typing import Any

from tools.ecfr_search import search_ecfr

logger = logging.getLogger(__name__)

_PROFILE_QUERIES: dict[str, list[str]] = {
    "erisa": [
        "2560.503-1 claims procedure employee benefit plan",
        "147.136 internal claims and appeals group health",
    ],
    "state_aca": [
        "147.136 internal claims appeals adverse benefit determination",
        "external review independent review organization health insurance",
    ],
    "medicaid": [
        "431.220 fair hearing Medicaid",
        "431.244 Medicaid managed care hearing",
    ],
}


async def fetch_applicable_laws_for_profile(profile: str) -> list[dict[str, Any]]:
    """
    Fetch applicable federal regulatory citations from the live eCFR search API.

    profile: erisa | state_aca | medicaid
    """
    queries = _PROFILE_QUERIES.get(profile, _PROFILE_QUERIES["state_aca"])
    laws: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for q in queries[:3]:
        try:
            res = await search_ecfr(q, cfr_section="")
            if not res.found:
                continue
            url = (res.url or "").strip()
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            label = res.cfr_reference or res.title or q
            laws.append(
                {
                    "law": label[:200],
                    "section": (res.title or "")[:200],
                    "relevance": (res.excerpt or "")[:600],
                    "url": url or "https://www.ecfr.gov/",
                    "source": res.source,
                }
            )
        except Exception as e:
            logger.warning("eCFR fetch failed for %r: %s", q, e)

    return laws
