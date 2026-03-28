"""
CMS Coverage Tool

Searches CMS National Coverage Determinations (NCDs) and Local Coverage
Determinations (LCDs) relevant to a claim. Used by the Regulation Agent
when a claim is denied for medical necessity.

API: CMS Coverage Database search via web
NCD endpoint: https://www.cms.gov/medicare-coverage-database/
"""
from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from tools.web_search import web_search

logger = logging.getLogger(__name__)

_CMS_NCD_SEARCH_URL = "https://www.cms.gov/medicare-coverage-database/api/ncd"
_TIMEOUT = 15.0


class CMSCoverageResult(BaseModel):
    query: str
    ncd_id: str = ""
    ncd_title: str = ""
    lcd_id: str = ""
    lcd_title: str = ""
    coverage_determination: str = ""
    criteria: list[str] = []
    coverage_url: str = ""
    source: str = "CMS Medicare Coverage Database"
    found: bool = False


async def search_cms_coverage(
    procedure_description: str = "",
    cpt_codes: list[str] | None = None,
    icd10_codes: list[str] | None = None,
) -> CMSCoverageResult:
    """
    Search CMS Coverage Database for NCDs/LCDs relevant to the claim.

    Falls back to web search if the CMS database API is unavailable.
    """
    cpt_codes = cpt_codes or []
    icd10_codes = icd10_codes or []

    # Build a targeted search query
    parts = []
    if procedure_description:
        parts.append(procedure_description)
    if cpt_codes:
        parts.append(f"CPT {' '.join(cpt_codes[:2])}")
    if icd10_codes:
        parts.append(f"ICD-10 {' '.join(icd10_codes[:2])}")

    query = " ".join(parts) if parts else "Medicare coverage determination"
    search_query = f"CMS Medicare NCD LCD coverage determination {query}"

    # Try the CMS coverage database search endpoint
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _CMS_NCD_SEARCH_URL,
                params={"keyword": query, "format": "json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", []) or data.get("data", [])
                if items:
                    first = items[0]
                    return CMSCoverageResult(
                        query=query,
                        ncd_id=str(first.get("ncdId", first.get("id", ""))),
                        ncd_title=first.get("title", ""),
                        coverage_determination=first.get("summary", first.get("description", "")),
                        coverage_url=first.get("url", "https://www.cms.gov/medicare-coverage-database/"),
                        found=True,
                    )
    except Exception as e:
        logger.debug(f"CMS NCD API unavailable: {e}")

    # Fallback: Google web search
    ws_result = await web_search(search_query, num_results=2)
    if ws_result.found and ws_result.results:
        first = ws_result.results[0]
        return CMSCoverageResult(
            query=query,
            ncd_title=first.get("title", ""),
            coverage_determination=first.get("snippet", ""),
            coverage_url=first.get("link", "https://www.cms.gov/medicare-coverage-database/"),
            source="CMS Coverage Database (via web search)",
            found=True,
        )

    return CMSCoverageResult(
        query=query,
        found=False,
        coverage_url="https://www.cms.gov/medicare-coverage-database/",
    )
