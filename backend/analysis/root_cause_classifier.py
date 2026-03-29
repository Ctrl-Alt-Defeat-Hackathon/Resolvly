"""
Root Cause Classifier

Hybrid rule + AI classifier that maps claim denial data to one of 6 root
cause categories. Uses CARC code rules first (fast, deterministic), then
falls back to LLM reasoning for ambiguous cases.

Categories:
  - medical_necessity
  - prior_authorization
  - coding_billing_error
  - network_coverage
  - eligibility_enrollment
  - procedural_administrative
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from config import get_settings
from tools.llm_client import complete_llm
from extraction.schema import ClaimObject, RootCauseCategory

logger = logging.getLogger(__name__)


class RootCauseResult(BaseModel):
    category: RootCauseCategory
    confidence: float          # 0.0 – 1.0
    responsible_party: str     # patient, provider_billing_office, insurer, unknown
    reasoning: str
    classification_method: str = "rules"  # rules | llm | hybrid


# CARC code → root cause mapping (deterministic rules)
_CARC_MEDICAL_NECESSITY = {"50", "56", "58", "146", "167", "193"}
_CARC_PRIOR_AUTH = {"15", "197", "246", "251"}
_CARC_CODING_BILLING = {"4", "6", "9", "11", "16", "18", "22", "26", "29", "31", "97", "125", "131", "170", "176", "177", "178", "179", "180", "181", "182", "183", "184", "185", "186", "187", "188"}
_CARC_NETWORK_COVERAGE = {"27", "109", "119", "151", "204"}
_CARC_ELIGIBILITY = {"27", "96", "116", "133"}
_CARC_PROCEDURAL = {"16", "29", "252", "253", "254"}

# CARC → responsible party mapping
_CARC_RESPONSIBLE_PARTY: dict[str, str] = {
    # Provider billing errors
    "4": "provider_billing_office",
    "6": "provider_billing_office",
    "16": "provider_billing_office",
    "18": "provider_billing_office",
    "22": "provider_billing_office",
    "97": "provider_billing_office",
    "125": "provider_billing_office",
    "131": "provider_billing_office",
    # Prior auth — usually provider
    "15": "provider_billing_office",
    "197": "provider_billing_office",
    "246": "provider_billing_office",
    # Medical necessity — insurer determination
    "50": "insurer",
    "56": "insurer",
    "58": "insurer",
    # Coverage / benefit limits
    "109": "insurer",
    "119": "patient",
    "151": "patient",
    # Network
    "27": "provider_billing_office",
}


def _classify_by_carc(carc_codes: list[str]) -> RootCauseResult | None:
    """
    Attempt deterministic classification from CARC codes.
    Returns None if codes are absent or ambiguous.
    """
    if not carc_codes:
        return None

    # Normalize: strip group prefix (CO-, PR-, OA-)
    normalized: list[str] = []
    for code in carc_codes:
        parts = code.upper().replace("-", " ").split()
        for part in parts:
            if part.isdigit():
                normalized.append(part)
                break
        else:
            normalized.append(code.strip())

    # Score each category
    scores: dict[str, int] = {
        "medical_necessity": 0,
        "prior_authorization": 0,
        "coding_billing_error": 0,
        "network_coverage": 0,
        "eligibility_enrollment": 0,
        "procedural_administrative": 0,
    }

    responsible_parties: list[str] = []

    for code in normalized:
        if code in _CARC_PRIOR_AUTH:
            scores["prior_authorization"] += 3
        if code in _CARC_MEDICAL_NECESSITY:
            scores["medical_necessity"] += 3
        if code in _CARC_CODING_BILLING:
            scores["coding_billing_error"] += 2
        if code in _CARC_NETWORK_COVERAGE:
            scores["network_coverage"] += 2
        if code in _CARC_ELIGIBILITY:
            scores["eligibility_enrollment"] += 2
        if code in _CARC_PROCEDURAL:
            scores["procedural_administrative"] += 1

        party = _CARC_RESPONSIBLE_PARTY.get(code, "unknown")
        if party != "unknown":
            responsible_parties.append(party)

    best_category = max(scores, key=lambda k: scores[k])
    best_score = scores[best_category]

    if best_score == 0:
        return None

    # Determine confidence: high if clear winner, lower if tied
    second_best = sorted(scores.values(), reverse=True)[1]
    if best_score > second_best + 1:
        confidence = 0.90
        method = "rules"
    else:
        confidence = 0.65
        method = "rules"

    # Determine responsible party (mode of collected parties)
    if responsible_parties:
        responsible_party = max(set(responsible_parties), key=responsible_parties.count)
    else:
        responsible_party = "unknown"

    category_map = {
        "medical_necessity": RootCauseCategory.medical_necessity,
        "prior_authorization": RootCauseCategory.prior_authorization,
        "coding_billing_error": RootCauseCategory.coding_billing_error,
        "network_coverage": RootCauseCategory.network_coverage,
        "eligibility_enrollment": RootCauseCategory.eligibility_enrollment,
        "procedural_administrative": RootCauseCategory.procedural_administrative,
    }

    carc_list = ", ".join(carc_codes)
    reasoning_map = {
        "prior_authorization": f"CARC code(s) {carc_list} indicate missing or invalid prior authorization",
        "medical_necessity": f"CARC code(s) {carc_list} indicate insurer did not deem service medically necessary",
        "coding_billing_error": f"CARC code(s) {carc_list} indicate a billing or coding error",
        "network_coverage": f"CARC code(s) {carc_list} indicate a network or coverage limitation",
        "eligibility_enrollment": f"CARC code(s) {carc_list} indicate an eligibility or enrollment issue",
        "procedural_administrative": f"CARC code(s) {carc_list} indicate a procedural or administrative issue",
    }

    return RootCauseResult(
        category=category_map[best_category],
        confidence=confidence,
        responsible_party=responsible_party,
        reasoning=reasoning_map[best_category],
        classification_method=method,
    )


async def _classify_by_llm(claim: ClaimObject) -> RootCauseResult:
    """
    Use LLM (Groq or Gemini) to classify root cause when CARC rules are insufficient.
    """
    settings = get_settings()

    if not settings.groq_api_key and not settings.gemini_api_key:
        logger.warning("GROQ_API_KEY or GEMINI_API_KEY not set — returning unknown root cause")
        return RootCauseResult(
            category=RootCauseCategory.procedural_administrative,
            confidence=0.3,
            responsible_party="unknown",
            reasoning="Could not classify — no LLM API key configured",
            classification_method="fallback",
        )

    prompt = f"""You are an expert in medical billing and insurance claim denials.

Analyze this insurance claim denial and classify the ROOT CAUSE into exactly one of these categories:
- medical_necessity: Insurer says treatment wasn't medically necessary
- prior_authorization: Missing, expired, or denied prior authorization
- coding_billing_error: Incorrect codes, duplicate billing, unbundling, wrong modifier
- network_coverage: Out-of-network provider, benefit not covered, benefit limit reached
- eligibility_enrollment: Patient not eligible, coverage lapsed, not enrolled
- procedural_administrative: Missing info, wrong payer, timely filing, coordination of benefits

Claim data:
- Denial narrative: {claim.denial_reason.denial_reason_narrative or "Not provided"}
- Plan provision cited: {claim.denial_reason.plan_provision_cited or "Not provided"}
- Clinical criteria cited: {claim.denial_reason.clinical_criteria_cited or "Not provided"}
- CARC codes: {claim.denial_reason.carc_codes or "None"}
- RARC codes: {claim.denial_reason.rarc_codes or "None"}
- Prior auth status: {claim.denial_reason.prior_auth_status or "Unknown"}
- Network status: {claim.patient_provider.network_status or "Unknown"}
- ICD-10 codes: {claim.service_billing.icd10_diagnosis_codes or "None"}
- CPT codes: {claim.service_billing.cpt_procedure_codes or "None"}

Return JSON with these fields:
{{
  "category": "<one of the 6 categories>",
  "confidence": <0.0-1.0>,
  "responsible_party": "<patient|provider_billing_office|insurer|unknown>",
  "reasoning": "<1-2 sentence explanation>"
}}"""

    try:
        text = await complete_llm(prompt, expect_json=True, priority=2)  # High priority - needed for analysis
        if not text:
            raise ValueError("empty LLM response")
        data = json.loads(text)
        category_str = data.get("category", "procedural_administrative")

        try:
            category = RootCauseCategory(category_str)
        except ValueError:
            category = RootCauseCategory.procedural_administrative

        return RootCauseResult(
            category=category,
            confidence=float(data.get("confidence", 0.7)),
            responsible_party=data.get("responsible_party", "unknown"),
            reasoning=data.get("reasoning", ""),
            classification_method="llm",
        )

    except Exception as e:
        logger.error(f"LLM root cause classification failed: {e}")
        return RootCauseResult(
            category=RootCauseCategory.procedural_administrative,
            confidence=0.3,
            responsible_party="unknown",
            reasoning="Classification failed — insufficient data",
            classification_method="fallback",
        )


async def classify_root_cause(claim: ClaimObject) -> RootCauseResult:
    """
    Classify the root cause of the claim denial.

    Strategy:
    1. Try deterministic CARC rule classification first (fast, high confidence)
    2. If confidence < 0.80 or no CARC codes, supplement with LLM analysis
    """
    rules_result = _classify_by_carc(claim.denial_reason.carc_codes)

    if rules_result and rules_result.confidence >= 0.85:
        logger.info(f"Root cause classified by rules: {rules_result.category} ({rules_result.confidence:.2f})")
        return rules_result

    # Use LLM for ambiguous or code-free cases
    llm_result = await _classify_by_llm(claim)

    # If we had a rules result too, merge (take higher confidence)
    if rules_result and rules_result.confidence > llm_result.confidence:
        logger.info(f"Root cause: rules ({rules_result.confidence:.2f}) > LLM ({llm_result.confidence:.2f}), using rules")
        return rules_result

    logger.info(f"Root cause classified by LLM: {llm_result.category} ({llm_result.confidence:.2f})")
    return llm_result
