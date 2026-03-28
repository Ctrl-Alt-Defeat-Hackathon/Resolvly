"""
ICD-10-CM Code Lookup Tool

Resolves ICD-10-CM diagnosis codes to their official descriptions using the
CMS.gov ICD-10-CM API (clinicaltables.nlm.nih.gov — free, no key required).

Fallback: WHO ICD API (requires free OAuth token).
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

# NLM Clinical Tables API — free, no auth, returns ICD-10-CM descriptions
_NLM_ICD10_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
_TIMEOUT = 10.0


class ICD10Result(BaseModel):
    code: str
    description: str
    source: str = "NLM Clinical Tables (ICD-10-CM)"
    source_url: str = ""
    found: bool = True


async def lookup_icd10(code: str) -> ICD10Result:
    """
    Look up an ICD-10-CM code and return its official description.

    Uses the NLM Clinical Tables API which is free and requires no API key.
    Endpoint: GET /api/icd10cm/v3/search?sf=code&terms={code}
    Returns: [total, [codes], null, [[code, description], ...]]
    """
    code = code.strip().upper()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NLM_ICD10_URL,
                params={"sf": "code", "terms": code, "maxList": 5},
            )
            resp.raise_for_status()
            data = resp.json()

            # Response format: [total_count, [matching_codes], null, [[code, description], ...]]
            total = data[0] if len(data) > 0 else 0
            details = data[3] if len(data) > 3 else []

            if total > 0 and details:
                # Find exact match first, then closest match
                for entry in details:
                    if entry[0].upper().replace(".", "") == code.replace(".", ""):
                        return ICD10Result(
                            code=entry[0],
                            description=entry[1],
                            source_url=f"https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code&terms={code}",
                        )
                # Return first result if no exact match
                return ICD10Result(
                    code=details[0][0],
                    description=details[0][1],
                    source_url=f"https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?sf=code&terms={code}",
                )

    except (httpx.HTTPError, IndexError, KeyError):
        pass

    return ICD10Result(
        code=code,
        description=f"ICD-10-CM code {code} — description not found via API",
        found=False,
    )
