"""
Pass 2 — LLM-Powered Entity Extraction.

Uses Groq (preferred) or Google Gemini with structured JSON output to extract entities
that require contextual understanding:
  - denial reason narratives
  - provider / patient names (NER)
  - plan provisions cited
  - clinical criteria
  - network status
  - procedure descriptions
  - financial field labelling

Input:  raw document text + Pass 1 regex results
Output: dict of extracted fields to merge into the ClaimObject
"""
from __future__ import annotations

import json
import logging
from typing import Any

from config import get_settings
from tools.llm_client import complete_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a medical billing document parser specializing in insurance denial letters, Explanations of Benefits (EOBs), and hospital bills.

Your job is to extract specific entities from the document text. You will also receive preliminary regex extraction results (Pass 1) — use these to validate and supplement your extraction, but rely on your own reading comprehension for fields that regex cannot capture.

IMPORTANT RULES:
1. Extract ONLY what is explicitly stated in the document. Do NOT infer or fabricate information.
2. If a field is not found in the document, return null for that field.
3. For dates, return in YYYY-MM-DD format.
4. For dollar amounts, return as numbers without the $ sign (e.g., 1500.00).
5. For denial_reason_narrative, extract the FULL explanation the insurer gives for the denial — not just a code or one-liner.
6. For plan_provision_cited, extract the specific plan section/clause the insurer references.
7. For clinical_criteria_cited, extract any clinical guidelines, protocols, or medical criteria mentioned.
8. For prior_auth_status, determine from context whether prior authorization was granted, denied, not requested, expired, not required, or unknown.
9. For network_status, determine from context whether the provider is in-network, out-of-network, or unknown.
10. For document_type, classify what kind of document this is based on its content and format.

Return ONLY a JSON object with the extracted fields. Use null for fields not found."""


def _build_user_prompt(text: str, pass1_results: dict[str, Any]) -> str:
    """Build the user message with document text and Pass 1 results."""
    pass1_summary_parts = []
    for key, value in pass1_results.items():
        if value is not None and value != [] and value != "":
            pass1_summary_parts.append(f"  {key}: {value}")
    pass1_summary = "\n".join(pass1_summary_parts) if pass1_summary_parts else "  (no entities found in Pass 1)"

    return f"""## Document Text

{text[:80000]}

## Pass 1 (Regex) Extraction Results

{pass1_summary}

## Instructions

Extract the following entities from the document above. Use the Pass 1 results as a reference but rely on your own reading of the document for fields that require contextual understanding.

Return a JSON object with these fields (use null for any not found):
- patient_full_name, treating_provider_name, treating_provider_specialty
- facility_name, facility_address, network_status (in_network/out_of_network/unknown)
- date_of_service, date_of_denial, date_of_eob (YYYY-MM-DD format)
- denial_reason_narrative (full text of denial reason)
- plan_provision_cited, clinical_criteria_cited, medical_necessity_statement
- prior_auth_status (granted/denied/not_requested/expired/not_required/required_not_obtained/unknown)
- procedure_description
- billed_amount, allowed_amount, insurer_paid_amount, denied_amount
- patient_responsibility_total, copay_amount, coinsurance_amount, deductible_applied
- internal_appeal_deadline_stated, external_review_deadline_stated
- expedited_review_available (boolean), insurer_appeals_contact_name
- insurer_appeals_address, insurer_appeals_fax
- document_type (denial_letter/eob/hospital_bill/insurance_card/prior_auth_letter/other)"""


async def extract_pass2(
    text: str,
    pass1_results: dict[str, Any],
) -> dict[str, Any]:
    """
    Run LLM-powered entity extraction (Pass 2).

    Returns an empty dict if no LLM API key is configured or the call fails.
    """
    settings = get_settings()
    if not settings.groq_api_key and not settings.gemini_api_key:
        logger.warning("GROQ_API_KEY or GEMINI_API_KEY not set — skipping Pass 2 LLM extraction")
        return {}

    user_prompt = _build_user_prompt(text, pass1_results)

    try:
        response_text = await complete_llm(
            user_prompt,
            expect_json=True,
            system_instruction=_SYSTEM_PROMPT,
        )

        if not response_text:
            logger.warning("LLM returned empty response for Pass 2 extraction")
            return {}

        result = json.loads(response_text)

        cleaned = {}
        for key, value in result.items():
            if value is not None and value != "" and value != []:
                cleaned[key] = value

        logger.info(f"Pass 2 extracted {len(cleaned)} fields via LLM")
        return cleaned

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response for Pass 2: {e}")
        return {}
    except Exception as e:
        logger.error(f"LLM API call failed for Pass 2: {e}")
        return {}
