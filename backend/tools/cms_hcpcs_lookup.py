"""
HCPCS / CPT Code Lookup Tool

Resolves HCPCS Level II and CPT procedure codes to their official descriptions
using the NLM Clinical Tables API.

- HCPCS Level II (alphanumeric, e.g. A0425): NLM Clinical Tables API
- CPT codes (5-digit numeric, e.g. 99213): The NLM HCPCS table does not include
  CPT codes (AMA licensing), so we fall back to web search for CPT descriptions.
"""
from __future__ import annotations

import re

import httpx
from pydantic import BaseModel

_NLM_HCPCS_URL = "https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search"
_TIMEOUT = 10.0

# CPT: 4 digits + alphanumeric (standard + category II/III); HCPCS II: A–V + 4 digits
_CPT_RE = re.compile(r"^[0-9]{4}[0-9A-Z]$", re.IGNORECASE)
_HCPCS_RE = re.compile(r"^[A-V][0-9]{4}$", re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:CPT|HCPCS|PROC(?:EDURE)?\s*CODE)\s*[:\s#-]*",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"\b([0-9]{4}[0-9A-Z]|[A-V][0-9]{4})\b", re.IGNORECASE)


class HCPCSResult(BaseModel):
    code: str
    description: str
    code_type: str = "unknown"  # "cpt" or "hcpcs"
    source: str = "NLM Clinical Tables (HCPCS)"
    source_url: str = ""
    found: bool = True


def _normalize_procedure_code(raw: str) -> str:
    """Strip CPT/HCPCS labels and extract a bare procedure code token."""
    s = raw.strip()
    if not s:
        return s
    s = _PREFIX_RE.sub("", s)
    s = s.strip()
    m = _TOKEN_RE.search(s)
    if m:
        return m.group(1).upper()
    compact = re.sub(r"[^0-9A-Za-z]", "", s)
    return compact.upper() if compact else raw.strip().upper()


def _classify_code(code: str) -> str:
    """Determine if a code is CPT or HCPCS Level II."""
    code = code.strip().upper()
    if not code:
        return "unknown"
    if _CPT_RE.match(code):
        return "cpt"
    if _HCPCS_RE.match(code):
        return "hcpcs"
    return "unknown"


async def _cpt_description_via_web(code: str) -> HCPCSResult | None:
    """Best-effort CPT description when NLM HCPCS (Level II only) has no CPT rows."""
    from tools.web_search import web_search

    ws = await web_search(f"CPT code {code} procedure description medical billing", num_results=3)
    if not ws.found or not ws.results:
        return None
    first = ws.results[0]
    snippet = (first.get("snippet") or first.get("title") or "").strip()
    if len(snippet) < 12:
        return None
    link = first.get("link") or ""
    return HCPCSResult(
        code=code,
        description=snippet[:1200],
        code_type="cpt",
        source=ws.source,
        source_url=link,
        found=True,
    )


async def lookup_cpt_hcpcs(code: str) -> HCPCSResult:
    """
    Look up a CPT or HCPCS code and return its official description.

    Uses the NLM Clinical Tables API. The API returns code + description
    in the details array (index 3) when searching by text.
    """
    code = _normalize_procedure_code(code)
    if not code:
        return HCPCSResult(
            code=code,
            description="No procedure code could be parsed from the input.",
            code_type="unknown",
            found=False,
        )

    code_type = _classify_code(code)
    if code_type == "unknown":
        return HCPCSResult(
            code=code,
            description=f"Unrecognized procedure code format: {code}",
            code_type="unknown",
            found=False,
        )

    # NLM table is HCPCS Level II only — CPT is AMA-licensed and not in this API
    if code_type == "cpt":
        web_hit = await _cpt_description_via_web(code)
        if web_hit:
            return web_hit
        return HCPCSResult(
            code=code,
            description=(
                f"CPT code {code}: no public description found. "
                "Confirm the code on an official fee schedule or payer portal."
            ),
            code_type="cpt",
            found=False,
            source="CPT (AMA) — configure GOOGLE_SEARCH_API_KEY for web fallback",
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # The NLM API returns [total, [codes], null, [[code, description], ...]]
            resp = await client.get(
                _NLM_HCPCS_URL,
                params={"terms": code, "maxList": 10},
            )
            resp.raise_for_status()
            data = resp.json()

            total = data[0] if len(data) > 0 else 0
            details = data[3] if len(data) > 3 else []

            if total > 0 and details:
                for entry in details:
                    entry_code = entry[0] if entry else ""
                    entry_desc = entry[1] if len(entry) > 1 else ""
                    if entry_code.upper() == code:
                        return HCPCSResult(
                            code=entry_code,
                            description=entry_desc or f"HCPCS code {code}",
                            code_type="hcpcs",
                            source_url=f"https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search?terms={code}",
                        )

                first = details[0]
                return HCPCSResult(
                    code=first[0] if first else code,
                    description=first[1] if len(first) > 1 and first[1] else f"HCPCS code {code}",
                    code_type="hcpcs",
                    source_url=f"https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search?terms={code}",
                )

    except (httpx.HTTPError, IndexError, KeyError):
        pass

    return HCPCSResult(
        code=code,
        description=f"HCPCS code {code} — description not found via API",
        code_type="hcpcs",
        found=False,
    )
