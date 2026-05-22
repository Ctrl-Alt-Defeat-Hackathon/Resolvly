"""
Pass 2 — LLM-Powered Entity Extraction.

Split into 3 focused parallel calls instead of one monolithic call:
  1. entities  — NER: patient/provider/facility names, network status, document type
  2. narrative — denial reason text, plan provision, clinical criteria, prior auth
  3. contact   — appeal deadlines as stated, contact info, expedited flag

Benefits over the previous single-call approach:
  - A JSON parse failure in one call does not lose the other two groups of fields
  - Each call uses a smaller, more focused context window (≤40k chars)
  - Fields already found by Pass 1 regex are skipped to save tokens

Input:  raw document text + Pass 1 regex results
Output: dict of extracted fields to merge into the ClaimObject
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from config import get_settings
from tools.llm_client import complete_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a medical billing document parser specializing in insurance denial letters, Explanations of Benefits (EOBs), and hospital bills.

IMPORTANT RULES:
1. Extract ONLY what is explicitly stated in the document. Do NOT infer or fabricate.
2. If a field is not found, return null for that field.
3. For dates, return in YYYY-MM-DD format.
4. For dollar amounts, return as numbers without the $ sign (e.g., 1500.00).
5. Return ONLY a JSON object with the requested fields. Use null for fields not found."""


def _repair_truncated_json(text: str) -> str:
    """Attempt to close truncated JSON by counting unclosed braces."""
    t = text.strip()
    if not t:
        return t
    open_b = t.count("{") - t.count("}")
    open_br = t.count("[") - t.count("]")
    if open_b > 0 or open_br > 0:
        t = t.rstrip(",").rstrip()
        t += "]" * max(0, open_br)
        t += "}" * max(0, open_b)
    return t


def _safe_json_loads(text: str) -> dict[str, Any]:
    """Parse JSON with fence stripping and repair for truncated responses."""
    if not text:
        return {}
    # Strip markdown fences
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, count=1)
        t = re.sub(r"\s*```\s*$", "", t)
        t = t.strip()
    # Find the outermost JSON object
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start:end + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(t)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return {}


# ---------------------------------------------------------------------------
# Call 1 — NER entities
# ---------------------------------------------------------------------------

async def _extract_entities(text: str) -> dict[str, Any]:
    """Extract patient/provider names, facility, network status, document type."""
    prompt = f"""Extract the following entities from this medical document. Return JSON only.

Fields (use null if not found):
- patient_full_name: patient's full name
- treating_provider_name: treating physician's full name
- treating_provider_specialty: medical specialty
- facility_name: hospital or clinic name
- facility_address: facility mailing address
- network_status: "in-network" or "out-of-network" (null if not stated)
- document_type: one of: denial_letter / eob / hospital_bill / insurance_card / prior_auth_letter / other

Document text:
{text[:40000]}"""

    try:
        response = await complete_llm(
            prompt,
            expect_json=True,
            system_instruction=_SYSTEM_PROMPT,
            priority=1,
        )
        result = _safe_json_loads(response)
        logger.debug(f"Pass 2 entities: extracted {sum(1 for v in result.values() if v is not None)} fields")
        return result
    except Exception as e:
        logger.warning(f"Pass 2 entities extraction failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Call 2 — Denial narrative fields
# ---------------------------------------------------------------------------

async def _extract_narrative(text: str, pass1: dict[str, Any]) -> dict[str, Any]:
    """Extract denial reason prose, plan provision, clinical criteria, prior auth status."""
    # Skip fields already found confidently by Pass 1
    skip_prior_auth = pass1.get("prior_auth_status") not in (None, "required_unknown")

    fields_block = """Fields (use null if not found):
- denial_reason_narrative: full text of the insurer's denial explanation (not just a code)
- plan_provision_cited: specific plan section or exclusion cited (e.g. "Section 5.3 – Experimental Treatments")
- clinical_criteria_cited: clinical guidelines cited (e.g. "InterQual Level of Care criteria")
- medical_necessity_statement: full text of insurer's medical necessity explanation
- procedure_description: human-readable description of the denied service"""

    if not skip_prior_auth:
        fields_block += "\n- prior_auth_status: one of: granted / denied / not_requested / expired / required_not_obtained / unknown"

    prompt = f"""Extract the following fields from this insurance denial document. Return JSON only.

{fields_block}

Document text:
{text[:40000]}"""

    try:
        response = await complete_llm(
            prompt,
            expect_json=True,
            system_instruction=_SYSTEM_PROMPT,
            priority=1,
        )
        result = _safe_json_loads(response)
        logger.debug(f"Pass 2 narrative: extracted {sum(1 for v in result.values() if v is not None)} fields")
        return result
    except Exception as e:
        logger.warning(f"Pass 2 narrative extraction failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Call 3 — Appeal contact and deadline fields
# ---------------------------------------------------------------------------

async def _extract_contact(text: str, pass1: dict[str, Any]) -> dict[str, Any]:
    """Extract appeal deadlines as stated, contact info, expedited flag, financial amounts."""
    # Skip financial fields already extracted by labeled regex
    labeled = pass1.get("financial_labeled", {})
    financial_fields_needed = [
        f for f in (
            "billed_amount", "allowed_amount", "insurer_paid_amount",
            "denied_amount", "patient_responsibility_total",
            "copay_amount", "coinsurance_amount", "deductible_applied",
        )
        if labeled.get(f) is None
    ]

    financial_block = ""
    if financial_fields_needed:
        financial_block = "\n- " + "\n- ".join(financial_fields_needed) + " (numeric, no $ sign)"

    prompt = f"""Extract the following fields from this insurance document. Return JSON only.

Fields (use null if not found):
- internal_appeal_deadline_stated: deadline text as written (e.g. "within 180 days of this notice")
- external_review_deadline_stated: external review deadline text as written
- expedited_review_available: true if expedited review is mentioned, false if explicitly unavailable, null otherwise
- insurer_appeals_contact_name: name of appeals department or contact
- insurer_appeals_address: mailing address for appeal submissions
- insurer_appeals_fax: fax number for appeal submissions
- date_of_eob: date the EOB was issued (YYYY-MM-DD){financial_block}

Document text:
{text[:40000]}"""

    try:
        response = await complete_llm(
            prompt,
            expect_json=True,
            system_instruction=_SYSTEM_PROMPT,
            priority=1,
        )
        result = _safe_json_loads(response)
        logger.debug(f"Pass 2 contact: extracted {sum(1 for v in result.values() if v is not None)} fields")
        return result
    except Exception as e:
        logger.warning(f"Pass 2 contact extraction failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def extract_pass2(
    text: str,
    pass1_results: dict[str, Any],
) -> dict[str, Any]:
    """
    Run LLM-powered entity extraction (Pass 2) as 3 parallel focused calls.

    Each call targets a distinct field group. A failure in one call does not
    affect the other two. Returns merged results; empty dict if all calls fail.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY not set — skipping Pass 2 LLM extraction")
        return {}

    try:
        entities, narrative, contact = await asyncio.gather(
            _extract_entities(text),
            _extract_narrative(text, pass1_results),
            _extract_contact(text, pass1_results),
        )
    except Exception as e:
        logger.error(f"Pass 2 parallel extraction failed: {e}")
        return {}

    # Merge all three results; later calls do not overwrite earlier non-null values
    merged: dict[str, Any] = {}
    for result in (entities, narrative, contact):
        for key, value in result.items():
            if value is not None and value != "" and value != [] and key not in merged:
                merged[key] = value

    logger.info(f"Pass 2 extracted {len(merged)} fields via LLM ({3} parallel calls)")
    return merged
