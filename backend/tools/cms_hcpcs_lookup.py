"""
HCPCS / CPT Code Lookup Tool

Resolves HCPCS Level II and CPT procedure codes to their official descriptions
using the NLM Clinical Tables API.

- HCPCS Level II (alphanumeric, e.g. A0425): NLM Clinical Tables API
- CPT codes (5-digit numeric, e.g. 99213): The NLM HCPCS table does not include
  CPT codes (AMA licensing), so we fall back to web search for CPT descriptions.
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

_NLM_HCPCS_URL = "https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search"
_TIMEOUT = 10.0


class HCPCSResult(BaseModel):
    code: str
    description: str
    code_type: str = "unknown"  # "cpt" or "hcpcs_level2"
    source: str = "NLM Clinical Tables (HCPCS)"
    source_url: str = ""
    found: bool = True


def _classify_code(code: str) -> str:
    """Determine if a code is CPT or HCPCS Level II."""
    code = code.strip().upper()
    if code.isdigit() and len(code) == 5:
        return "cpt"
    if len(code) == 5 and code[0].isalpha() and code[1:].isdigit():
        return "hcpcs_level2"
    return "unknown"


async def lookup_cpt_hcpcs(code: str) -> HCPCSResult:
    """
    Look up a CPT or HCPCS code and return its official description.

    Uses the NLM Clinical Tables API. The API returns code + description
    in the details array (index 3) when searching by text.
    """
    code = code.strip().upper()
    code_type = _classify_code(code)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # The NLM API works best when we search the code as a term
            # It returns [total, [codes], null, [[code, description], ...]]
            resp = await client.get(
                _NLM_HCPCS_URL,
                params={"terms": code, "maxList": 10},
            )
            resp.raise_for_status()
            data = resp.json()

            total = data[0] if len(data) > 0 else 0
            codes_list = data[1] if len(data) > 1 else []
            details = data[3] if len(data) > 3 else []

            if total > 0 and details:
                # Find exact match by code
                for entry in details:
                    entry_code = entry[0] if entry else ""
                    entry_desc = entry[1] if len(entry) > 1 else ""
                    if entry_code.upper() == code:
                        return HCPCSResult(
                            code=entry_code,
                            description=entry_desc or f"HCPCS code {code}",
                            code_type=code_type,
                            source_url=f"https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search?terms={code}",
                        )

                # If no exact match, return first result
                first = details[0]
                return HCPCSResult(
                    code=first[0] if first else code,
                    description=first[1] if len(first) > 1 and first[1] else f"HCPCS code {code}",
                    code_type=code_type,
                    source_url=f"https://clinicaltables.nlm.nih.gov/api/hcpcs/v3/search?terms={code}",
                )

            # Code not in HCPCS table (common for CPT codes which are AMA-licensed)
            if code_type == "cpt":
                return HCPCSResult(
                    code=code,
                    description=f"CPT code {code} (description requires AMA license — use web search fallback)",
                    code_type="cpt",
                    found=False,
                    source="NLM Clinical Tables (CPT codes not included — AMA licensed)",
                )

    except (httpx.HTTPError, IndexError, KeyError):
        pass

    return HCPCSResult(
        code=code,
        description=f"{'CPT' if code_type == 'cpt' else 'HCPCS'} code {code} — description not found via API",
        code_type=code_type,
        found=False,
    )
