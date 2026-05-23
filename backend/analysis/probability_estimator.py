"""
Approval Probability Estimator

Rules-based engine that estimates the probability of a successful appeal
based on root cause category, CARC codes, denial completeness, and other factors.

Uses logistic combination: final_p = sigmoid(logit(base_rate) + Σ logit_weights)
so adjustments compose correctly rather than being clamped at arbitrary linear bounds.
"""
from __future__ import annotations

import logging
import math

from pydantic import BaseModel

from extraction.schema import ClaimObject, RootCauseCategory, RegulationType
from analysis.root_cause_classifier import RootCauseResult

logger = logging.getLogger(__name__)


class ProbabilityResult(BaseModel):
    score: float          # 0.0 – 1.0
    reasoning: str
    factors: list[str]    # display factors — items with +/- prefix affect score; others are informational
    source: str = "Rules engine based on published appeals overturn statistics; individual results vary."


def _logit(p: float) -> float:
    p = max(0.01, min(0.99, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# Base overturn rates by root cause (from CMS/KFF appeals data)
_BASE_RATES: dict[RootCauseCategory, float] = {
    RootCauseCategory.prior_authorization: 0.78,      # High: CMS data shows 78% overturn when proper docs submitted
    RootCauseCategory.coding_billing_error: 0.90,     # Very high: correcting a code usually fixes the denial
    RootCauseCategory.medical_necessity: 0.55,        # Moderate: depends on documentation quality
    RootCauseCategory.procedural_administrative: 0.70, # Good: often fixable with correct information
    RootCauseCategory.eligibility_enrollment: 0.40,   # Lower: enrollment issues are harder to retroactively fix
    RootCauseCategory.network_coverage: 0.45,         # Moderate: surprise billing / emergency rules help
}

_BASE_REASONING: dict[RootCauseCategory, str] = {
    RootCauseCategory.prior_authorization: (
        "Prior authorization denials have a 78% overturn rate when the provider submits "
        "retroactive authorization with supporting clinical documentation. Source: CMS appeals data."
    ),
    RootCauseCategory.coding_billing_error: (
        "Coding/billing errors have a 90%+ correction rate — submitting a corrected claim "
        "with the right CPT/ICD-10 codes typically resolves the denial. Source: MGMA claims data."
    ),
    RootCauseCategory.medical_necessity: (
        "Medical necessity denials have a 55% overturn rate when the treating physician "
        "submits a detailed letter of medical necessity with supporting clinical records. "
        "Source: KFF Health Insurance Marketplace Survey."
    ),
    RootCauseCategory.procedural_administrative: (
        "Procedural/administrative denials are often fixable by providing the missing information "
        "or correcting the submission. Success rate is approximately 70%."
    ),
    RootCauseCategory.eligibility_enrollment: (
        "Eligibility denials are harder to overturn but possible if you can demonstrate "
        "coverage was active on the date of service or an enrollment error occurred. "
        "Success rate is approximately 40%."
    ),
    RootCauseCategory.network_coverage: (
        "Network denials may be overturned under the No Surprises Act (emergency services), "
        "continuity-of-care provisions, or network inadequacy claims. "
        "Success rate is approximately 45% and varies by plan type."
    ),
}


def estimate_probability(
    claim: ClaimObject,
    root_cause: RootCauseResult,
    denial_completeness_score: float = 1.0,
) -> ProbabilityResult:
    """
    Estimate appeal approval probability using logistic combination.

    Score adjustments are applied in logit space so they compose correctly;
    display-only factors (no numeric weight) are informational only.
    """
    base_rate = _BASE_RATES.get(root_cause.category, 0.50)
    base_reasoning = _BASE_REASONING.get(root_cause.category, "Estimated based on category averages.")

    factors: list[str] = []          # shown to user
    logit_weights: list[float] = []  # score adjustments (logit scale)

    # Factor: Responsible party
    if root_cause.responsible_party == "provider_billing_office":
        factors.append("+Provider billing error — high overturn rate when provider corrects and resubmits")
        logit_weights.append(0.30)
    elif root_cause.responsible_party == "insurer":
        factors.append("+Insurer determination can be challenged with clinical evidence")
        # No logit adjustment — neutral signal, already baked into base rate
    elif root_cause.responsible_party == "patient":
        factors.append("-Patient responsibility denials (deductible, OOP max) are rarely overturned")
        logit_weights.append(-0.70)

    # Factor: Denial completeness
    if denial_completeness_score < 0.75:
        factors.append("+Denial letter is procedurally deficient — strengthens appeal grounds")
        logit_weights.append(0.40)
    elif denial_completeness_score > 0.90:
        factors.append("-Denial letter is well-documented — insurer appears confident in decision")
        logit_weights.append(-0.15)

    # Display-only: no prior appeal (informational — no score effect, since we can't know)
    factors.append("No prior appeal filed yet — filing an appeal is required before external review")

    # Factor: Regulation type
    regulation_type = claim.identification.erisa_or_state_regulated
    if regulation_type == RegulationType.state:
        factors.append("+External review by independent IRO available (binding on insurer)")
        logit_weights.append(0.25)
    elif regulation_type == RegulationType.erisa:
        factors.append("~ERISA plan: no state external review; civil action under § 502(a) is last resort")

    # Factor: Expedited review available
    if claim.appeal_rights.expedited_review_available is True:
        factors.append("+Expedited review available — faster resolution pathway exists")

    # Factor: Prior auth — retroactive authorization possible
    if root_cause.category == RootCauseCategory.prior_authorization:
        if claim.denial_reason.prior_auth_status == "required_not_obtained":
            factors.append("+Provider can request retroactive authorization with supporting clinical documentation")
            logit_weights.append(0.20)

    # Factor: Financial stakes
    denied = claim.financial.denied_amount or 0
    if denied > 5_000:
        factors.append("+High denied amount — strong financial incentive for provider to support appeal")
    elif denied < 500:
        factors.append("-Small denied amount — weigh appeal effort against potential recovery")

    # Logistic combination: sigmoid(logit(base_rate) + Σ weights)
    final_logit = _logit(base_rate) + sum(logit_weights)
    final_score = max(0.05, min(0.97, _sigmoid(final_logit)))

    return ProbabilityResult(
        score=round(final_score, 2),
        reasoning=base_reasoning,
        factors=factors,
    )
