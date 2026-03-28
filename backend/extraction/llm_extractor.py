"""
Pass 2 — LLM-Powered Entity Extraction.

Uses Google Gemini 2.5 Flash with structured output to extract entities
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

from google import genai
from google.genai import types

from config import get_settings

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

{text[:15000]}

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

    Takes raw document text and Pass 1 regex results, sends to Gemini
    with a structured output prompt, and returns extracted fields.

    Returns an empty dict if the API key is not configured or the call fails.
    """
    settings = get_settings()

    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — skipping Pass 2 LLM extraction")
        return {}

    client = genai.Client(api_key=settings.gemini_api_key)
    user_prompt = _build_user_prompt(text, pass1_results)

    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model_primary,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        if not response.text:
            logger.warning("Gemini returned empty response for Pass 2 extraction")
            return {}

        result = json.loads(response.text)

        # Clean up: remove null values and empty strings
        cleaned = {}
        for key, value in result.items():
            if value is not None and value != "" and value != []:
                cleaned[key] = value

        logger.info(f"Pass 2 extracted {len(cleaned)} fields via LLM")
        return cleaned

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini JSON response: {e}")
        return {}
    except Exception as e:
        logger.error(f"Gemini API call failed for Pass 2: {e}")
        # Try fallback model
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model_fallback,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            if response.text:
                result = json.loads(response.text)
                cleaned = {k: v for k, v in result.items() if v is not None and v != "" and v != []}
                logger.info(f"Pass 2 (fallback model) extracted {len(cleaned)} fields")
                return cleaned
        except Exception as fallback_err:
            logger.error(f"Fallback model also failed: {fallback_err}")

        return {}
