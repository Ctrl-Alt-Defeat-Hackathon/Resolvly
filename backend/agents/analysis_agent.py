"""
Analysis Agent

Takes the enriched ClaimObject (after code lookup, regulation, and state rules
enrichment) and produces all analytical outputs:
  - Root cause classification
  - Denial letter completeness check
  - Appeal deadlines
  - Approval probability score
  - Severity triage

No external tools — operates purely on data already gathered by agents 2-4.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from extraction.schema import ClaimObject, SeverityTriage
from analysis.root_cause_classifier import classify_root_cause, RootCauseResult
from analysis.deadline_calculator import calculate_deadlines, AppealDeadlines
from analysis.completeness_checker import check_completeness, CompletenessResult
from analysis.severity_triage import triage_severity
from analysis.probability_estimator import estimate_probability, ProbabilityResult

logger = logging.getLogger(__name__)


class AnalysisResult(BaseModel):
    root_cause: dict[str, Any] = {}
    denial_completeness: dict[str, Any] = {}
    deadlines: dict[str, Any] = {}
    approval_probability: dict[str, Any] = {}
    severity_triage: str = "routine"
    assumptions: list[dict[str, Any]] = []
    ics_events: list[dict] = []


async def run_analysis_agent(claim: ClaimObject) -> AnalysisResult:
    """
    Run all analysis modules and return structured results.
    """
    logger.info("Analysis Agent: starting analysis pipeline")

    # Step 1: Classify root cause (may call LLM)
    root_cause_result: RootCauseResult = await classify_root_cause(claim)
    logger.info(f"Root cause: {root_cause_result.category} ({root_cause_result.confidence:.2f})")

    # Update derived fields on claim so downstream modules have access
    claim.derived.root_cause_category = root_cause_result.category

    # Step 2: Denial letter completeness check (deterministic)
    completeness_result: CompletenessResult = check_completeness(claim)
    logger.info(f"Completeness score: {completeness_result.score:.2f} (deficient={completeness_result.deficient})")

    # Step 3: Severity triage (pre-deadline — we'll refine after computing deadlines)
    preliminary_severity = triage_severity(claim, internal_deadline=None)

    # Step 4: Calculate deadlines (uses denial date + regulation type)
    deadlines: AppealDeadlines = calculate_deadlines(claim, severity=preliminary_severity)
    if deadlines.internal_appeal.deadline_date:
        claim.derived.appeal_deadline_internal = deadlines.internal_appeal.deadline_date
    if deadlines.external_review.deadline_date:
        claim.derived.appeal_deadline_external = deadlines.external_review.deadline_date

    # Step 5: Refine severity triage with deadline info
    final_severity = triage_severity(claim, internal_deadline=deadlines.internal_appeal.deadline_date)
    claim.derived.severity_triage = final_severity
    logger.info(f"Severity: {final_severity}")

    # Step 6: Estimate approval probability
    prob_result: ProbabilityResult = estimate_probability(
        claim=claim,
        root_cause=root_cause_result,
        denial_completeness_score=completeness_result.score,
    )
    claim.derived.approval_probability_score = prob_result.score
    claim.derived.denial_completeness_score = completeness_result.score
    claim.derived.responsible_party = root_cause_result.responsible_party
    logger.info(f"Approval probability: {prob_result.score:.2f}")

    # Step 7: Build assumptions list
    assumptions = _build_assumptions(claim, root_cause_result, completeness_result)

    # Serialize to dicts for API response
    deadlines_dict: dict[str, Any] = {}
    if deadlines.internal_appeal.deadline_date:
        deadlines_dict["internal_appeal"] = {
            "date": deadlines.internal_appeal.deadline_date.isoformat(),
            "days_remaining": deadlines.internal_appeal.days_remaining,
            "source": deadlines.internal_appeal.source,
            "already_passed": deadlines.internal_appeal.already_passed,
        }
    if deadlines.external_review.deadline_date:
        deadlines_dict["external_review"] = {
            "date": deadlines.external_review.deadline_date.isoformat(),
            "days_remaining": deadlines.external_review.days_remaining,
            "source": deadlines.external_review.source,
            "already_passed": deadlines.external_review.already_passed,
        }
    elif deadlines.external_review.source:
        deadlines_dict["external_review"] = {"note": deadlines.external_review.source}

    if deadlines.expedited_available:
        deadlines_dict["expedited"] = {
            "available": True,
            "turnaround": "72 hours",
            "qualifier": deadlines.expedited_qualifier,
            "source": deadlines.expedited.source,
        }

    return AnalysisResult(
        root_cause={
            "category": root_cause_result.category.value,
            "confidence": root_cause_result.confidence,
            "responsible_party": root_cause_result.responsible_party,
            "reasoning": root_cause_result.reasoning,
            "classification_method": root_cause_result.classification_method,
        },
        denial_completeness={
            "score": completeness_result.score,
            "missing_fields": completeness_result.missing_fields,
            "present_fields": completeness_result.present_fields,
            "deficient": completeness_result.deficient,
            "escalation_available": completeness_result.escalation_available,
            "escalation_reason": completeness_result.escalation_reason,
            "regulation_standard": completeness_result.regulation_standard,
        },
        deadlines=deadlines_dict,
        approval_probability={
            "score": prob_result.score,
            "reasoning": prob_result.reasoning,
            "factors": prob_result.factors,
            "source": prob_result.source,
        },
        severity_triage=final_severity.value,
        assumptions=assumptions,
        ics_events=deadlines.ics_events,
    )


def _build_assumptions(
    claim: ClaimObject,
    root_cause: RootCauseResult,
    completeness: CompletenessResult,
) -> list[dict[str, Any]]:
    """Generate a list of key assumptions made during analysis."""
    assumptions = []

    # Assumption about plan type
    plan_type = claim.identification.plan_type
    if plan_type is None:
        assumptions.append({
            "assumption": "Plan type was not extracted from documents — regulation type may be incorrect",
            "confidence": 0.50,
            "impact": "high",
        })

    # Assumption about regulation type
    reg_type = claim.identification.erisa_or_state_regulated
    if reg_type and reg_type.value == "unknown":
        assumptions.append({
            "assumption": "Regulation type is unknown — assume ACA/state-regulated for deadline purposes",
            "confidence": 0.60,
            "impact": "high",
        })

    # Assumption about denial date
    if claim.identification.date_of_denial is None:
        assumptions.append({
            "assumption": "Date of denial not found in documents — deadlines cannot be calculated accurately",
            "confidence": 0.40,
            "impact": "high",
        })

    # Assumption about root cause confidence
    if root_cause.confidence < 0.75:
        assumptions.append({
            "assumption": f"Root cause classification confidence is {root_cause.confidence:.0%} — manual review recommended",
            "confidence": root_cause.confidence,
            "impact": "medium",
        })

    # Assumption for medical necessity
    from extraction.schema import RootCauseCategory
    if root_cause.category == RootCauseCategory.medical_necessity:
        assumptions.append({
            "assumption": "Assuming treating physician can provide a letter of medical necessity",
            "confidence": 0.80,
            "impact": "medium",
        })

    # Assumption for prior auth
    if root_cause.category == RootCauseCategory.prior_authorization:
        assumptions.append({
            "assumption": "Assuming provider is willing to submit retroactive prior authorization",
            "confidence": 0.70,
            "impact": "high",
        })

    # Assumption about ACA compliance
    if claim.identification.plan_type and "employer" not in (claim.identification.plan_type.value or ""):
        assumptions.append({
            "assumption": "Plan is ACA-compliant (not grandfathered or grandmothered)",
            "confidence": 0.85,
            "impact": "medium",
        })

    return assumptions
