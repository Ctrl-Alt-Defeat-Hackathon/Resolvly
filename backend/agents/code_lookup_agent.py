"""
Code Lookup Agent

Resolves every billing and denial code in a ClaimObject to its authoritative
definition using live API lookups. No local code database except for CARC/RARC
(which have no public API).

Tools:
  - lookup_icd10     → CMS/NLM ICD-10-CM API
  - lookup_cpt_hcpcs → CMS/NLM HCPCS API
  - lookup_carc      → Local CARC table (WPC source)
  - lookup_rarc      → Local RARC table (WPC source)
  - lookup_npi       → NPPES NPI Registry API
  - web_search       → Google Custom Search (fallback)

Input:  ClaimObject with extracted codes
Output: Enrichment dict with code descriptions, plain-English explanations, and sources
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from extraction.schema import ClaimObject
from tools.cms_icd_lookup import lookup_icd10
from tools.cms_hcpcs_lookup import lookup_cpt_hcpcs
from tools.carc_rarc_lookup import lookup_carc, lookup_rarc
from tools.npi_registry import lookup_npi
from tools.web_search import web_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------

class CodeDescription(BaseModel):
    code: str
    code_type: str  # icd10, cpt, hcpcs, carc, rarc, npi
    description: str
    plain_english: str = ""
    common_fix: str = ""
    source: str = ""
    source_url: str = ""
    found: bool = True


class SourceCitation(BaseModel):
    entity: str
    source_name: str
    url: str = ""


class CodeLookupResult(BaseModel):
    codes: dict[str, CodeDescription] = Field(default_factory=dict)
    npi_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sources: list[SourceCitation] = Field(default_factory=list)
    lookup_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CARC group code parsing
# ---------------------------------------------------------------------------

_CARC_GROUP_RE = re.compile(r"^(CO|PR|OA|PI|CR)[- ]?(\d+)$", re.IGNORECASE)


def _parse_carc_code(raw: str) -> tuple[str, str]:
    """Parse a CARC code like 'CO-50' or 'CO50' into (group, number)."""
    raw = raw.strip()
    m = _CARC_GROUP_RE.match(raw)
    if m:
        return m.group(1).upper(), m.group(2)
    # Just a number
    if raw.isdigit():
        return "", raw
    return "", raw


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

async def run_code_lookup_agent(claim: ClaimObject) -> CodeLookupResult:
    """
    Look up all codes in the ClaimObject using the appropriate tools.

    Runs all lookups in parallel for speed, then assembles the results.
    """
    result = CodeLookupResult()
    tasks: list[tuple[str, str, Any]] = []  # (key, code_type, coroutine)

    # ICD-10 codes
    for code in claim.service_billing.icd10_diagnosis_codes:
        tasks.append((code, "icd10", lookup_icd10(code)))

    # CPT codes
    for code in claim.service_billing.cpt_procedure_codes:
        tasks.append((code, "cpt", lookup_cpt_hcpcs(code)))

    # HCPCS codes
    for code in claim.service_billing.hcpcs_codes:
        tasks.append((code, "hcpcs", lookup_cpt_hcpcs(code)))

    # CARC codes
    for raw_code in claim.denial_reason.carc_codes:
        group, number = _parse_carc_code(raw_code)
        tasks.append((raw_code, "carc", lookup_carc(number, group)))

    # RARC codes
    for code in claim.denial_reason.rarc_codes:
        tasks.append((code, "rarc", lookup_rarc(code)))

    # NPI
    if claim.patient_provider.treating_provider_npi:
        npi = claim.patient_provider.treating_provider_npi
        tasks.append((npi, "npi", lookup_npi(npi)))

    if not tasks:
        logger.info("No codes to look up in ClaimObject")
        return result

    # Run all lookups in parallel
    logger.info(f"Code Lookup Agent: resolving {len(tasks)} codes in parallel")
    coroutines = [t[2] for t in tasks]
    outcomes = await asyncio.gather(*coroutines, return_exceptions=True)

    for (key, code_type, _), outcome in zip(tasks, outcomes):
        if isinstance(outcome, Exception):
            result.lookup_errors.append(f"Lookup failed for {code_type} {key}: {outcome}")
            logger.error(f"Lookup error for {code_type} {key}: {outcome}")
            continue

        if code_type == "icd10":
            result.codes[key] = CodeDescription(
                code=outcome.code,
                code_type="icd10",
                description=outcome.description,
                source=outcome.source,
                source_url=outcome.source_url,
                found=outcome.found,
            )
            if outcome.found:
                result.sources.append(SourceCitation(
                    entity=key, source_name=outcome.source, url=outcome.source_url,
                ))

        elif code_type in ("cpt", "hcpcs"):
            result.codes[key] = CodeDescription(
                code=outcome.code,
                code_type=outcome.code_type,
                description=outcome.description,
                source=outcome.source,
                source_url=outcome.source_url,
                found=outcome.found,
            )
            if outcome.found:
                result.sources.append(SourceCitation(
                    entity=key, source_name=outcome.source, url=outcome.source_url,
                ))

        elif code_type == "carc":
            result.codes[key] = CodeDescription(
                code=outcome.code,
                code_type="carc",
                description=outcome.description,
                plain_english=outcome.plain_english,
                common_fix=outcome.common_fix,
                source=outcome.source,
                found=outcome.found,
            )
            if outcome.found:
                result.sources.append(SourceCitation(
                    entity=key, source_name=outcome.source,
                ))

        elif code_type == "rarc":
            result.codes[key] = CodeDescription(
                code=outcome.code,
                code_type="rarc",
                description=outcome.description,
                plain_english=outcome.plain_english,
                source=outcome.source,
                found=outcome.found,
            )
            if outcome.found:
                result.sources.append(SourceCitation(
                    entity=key, source_name=outcome.source,
                ))

        elif code_type == "npi":
            result.npi_details[key] = {
                "npi": outcome.npi,
                "provider_name": outcome.provider_name,
                "provider_type": outcome.provider_type,
                "specialty": outcome.specialty,
                "address": outcome.address,
                "city": outcome.city,
                "state": outcome.state,
                "zip_code": outcome.zip_code,
                "phone": outcome.phone,
                "found": outcome.found,
            }
            result.codes[key] = CodeDescription(
                code=outcome.npi,
                code_type="npi",
                description=f"{outcome.provider_name} — {outcome.specialty}" if outcome.specialty else outcome.provider_name,
                source=outcome.source,
                source_url=outcome.source_url,
                found=outcome.found,
            )
            if outcome.found:
                result.sources.append(SourceCitation(
                    entity=key, source_name=outcome.source, url=outcome.source_url,
                ))

    # Attempt web search fallback for codes not found
    unfound = [
        (key, desc.code_type)
        for key, desc in result.codes.items()
        if not desc.found
    ]
    if unfound:
        logger.info(f"Web search fallback for {len(unfound)} unfound codes")
        fallback_tasks = []
        for key, code_type in unfound:
            query = f"{code_type.upper()} code {key} medical billing description"
            fallback_tasks.append((key, web_search(query, num_results=1)))

        fallback_outcomes = await asyncio.gather(
            *[t[1] for t in fallback_tasks], return_exceptions=True,
        )

        for (key, _), outcome in zip(fallback_tasks, fallback_outcomes):
            if isinstance(outcome, Exception) or not outcome.found:
                continue
            if outcome.results:
                snippet = outcome.results[0].get("snippet", "")
                if snippet and key in result.codes:
                    result.codes[key].description += f" (Web: {snippet})"
                    result.codes[key].source += " + Web Search"

    found_count = sum(1 for c in result.codes.values() if c.found)
    total = len(result.codes)
    logger.info(f"Code Lookup Agent complete: {found_count}/{total} codes resolved")

    return result
