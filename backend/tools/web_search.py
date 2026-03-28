"""
Web Search Tool (Fallback)

Uses Google Custom Search API (100 free queries/day) to search for any
code, regulation, or medical billing term not found via structured APIs.

Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX in .env.
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

from config import get_settings

_GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
_TIMEOUT = 10.0


class WebSearchResult(BaseModel):
    query: str
    results: list[dict] = []  # [{title, snippet, link}]
    source: str = "Google Custom Search API"
    found: bool = True


async def web_search(query: str, num_results: int = 3) -> WebSearchResult:
    """
    Search the web for medical billing / insurance regulation information.

    Falls back gracefully if no API key is configured.
    """
    settings = get_settings()
    query = query.strip()

    if not settings.google_search_api_key or not settings.google_search_cx:
        return WebSearchResult(
            query=query,
            results=[],
            found=False,
            source="Google Search API (not configured — set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX)",
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _GOOGLE_SEARCH_URL,
                params={
                    "key": settings.google_search_api_key,
                    "cx": settings.google_search_cx,
                    "q": query,
                    "num": min(num_results, 10),
                },
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            results = [
                {
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "link": item.get("link", ""),
                }
                for item in items[:num_results]
            ]

            return WebSearchResult(
                query=query,
                results=results,
                found=bool(results),
            )

    except (httpx.HTTPError, KeyError):
        pass

    return WebSearchResult(
        query=query,
        results=[],
        found=False,
        source="Google Search API (request failed)",
    )
