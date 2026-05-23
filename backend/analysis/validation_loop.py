"""
Validation Loop (§5.1)

Checks the code resolution quality after the Code Lookup Agent completes.
Emits high-impact assumptions for unresolved codes and tags the run as
requires_review when the unresolved rate exceeds 50%.

Does NOT re-run Document Stitcher (would be an infinite loop on the same inputs).
Instead it surfaces actionable warnings so the user knows which codes need
manual verification before the appeal letter is filed.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from extraction.schema import ClaimObject
from agents.code_lookup_agent import CodeLookupResult

logger = logging.getLogger(__name__)

_HIGH_UNRESOLVED_THRESHOLD = 0.50   # 50% unresolved → requires_review


class ValidationLoopResult(BaseModel):
    total_codes: int = 0
    unresolved_count: int = 0
    unresolved_rate: float = 0.0
    requires_review: bool = False
    assumptions: list[dict[str, Any]] = []


# Maps code type to a brief plain-English tip for the user
_CODE_TYPE_HINT: dict[str, str] = {
    "icd10": "Verify the ICD-10-CM code with the treating provider's medical records.",
    "cpt": "Confirm the CPT procedure code with the billing department.",
    "hcpcs": "Check the HCPCS Level II code against the supplier's invoice.",
    "carc": "Look up the CARC code on the WEDI/X12 Claim Adjustment Reason Code list.",
    "rarc": "Look up the RARC remark code on the CMS Remittance Advice Remark Code list.",
    "npi": "Verify the NPI in the NPPES registry at nppes.cms.hhs.gov.",
}


def run_validation_loop(
    claim: ClaimObject,
    code_result: CodeLookupResult,
) -> ValidationLoopResult:
    """
    Inspect code lookup results and emit assumptions for anything that couldn't
    be resolved against a live authority (CMS, NLM, NPPES).
    """
    result = ValidationLoopResult()

    if not code_result.codes:
        return result

    total = len(code_result.codes)
    unresolved = [key for key, desc in code_result.codes.items() if not desc.found]
    unresolved_count = len(unresolved)

    result.total_codes = total
    result.unresolved_count = unresolved_count
    result.unresolved_rate = unresolved_count / total if total else 0.0

    # Per-code assumptions for every unresolved code
    for key in unresolved:
        desc = code_result.codes[key]
        hint = _CODE_TYPE_HINT.get(desc.code_type, "Verify this code against the relevant authority.")
        result.assumptions.append({
            "assumption": (
                f"Code {key} ({desc.code_type.upper()}) could not be resolved against the "
                f"authoritative source — excluded from appeal letter citations. {hint}"
            ),
            "confidence": 0.95,
            "impact": "medium",
            "category": "unresolved_code",
            "code": key,
            "code_type": desc.code_type,
        })

    # High-rate flag
    if result.unresolved_rate > _HIGH_UNRESOLVED_THRESHOLD:
        result.requires_review = True
        result.assumptions.insert(0, {
            "assumption": (
                f"{unresolved_count} of {total} codes ({result.unresolved_rate:.0%}) could not be verified. "
                f"Manual review is strongly recommended before filing an appeal. "
                f"Unresolved codes: {', '.join(unresolved)}."
            ),
            "confidence": 0.99,
            "impact": "high",
            "category": "high_unresolved_rate",
        })
        logger.warning(
            "Validation loop: high unresolved rate %.0f%% (%d/%d) — requires_review=True",
            result.unresolved_rate * 100,
            unresolved_count,
            total,
        )
    else:
        logger.info(
            "Validation loop: %d/%d codes resolved (%.0f%% unresolved)",
            total - unresolved_count,
            total,
            result.unresolved_rate * 100,
        )

    return result
