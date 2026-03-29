"""
Orchestrator Agent

Central coordinator that:
1. Receives ClaimObject from the extraction pipeline
2. Dispatches Code Lookup, Regulation, and State Rules agents in parallel
3. Merges enrichment data into the ClaimObject
4. Dispatches Analysis Agent with enriched data
5. Returns full enriched analysis result

All agents run concurrently via asyncio for speed (~8–16s total).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from pydantic import BaseModel

from extraction.schema import ClaimObject, PlanContext, RegulationType
from agents.code_lookup_agent import run_code_lookup_agent, CodeLookupResult
from agents.regulation_agent import run_regulation_agent, RegulationEnrichment
from agents.state_rules_agent import run_state_rules_agent, StateRulesEnrichment
from agents.analysis_agent import run_analysis_agent, AnalysisResult
from analysis.root_cause_classifier import classify_root_cause

logger = logging.getLogger(__name__)


class OrchestratorResult(BaseModel):
    claim_object: dict[str, Any] = {}
    enrichment: dict[str, Any] = {}
    analysis: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []


class OrchestratorProgress(BaseModel):
    """Used for SSE streaming — describes a completed stage."""
    event: str
    data: dict[str, Any]


def _apply_plan_context(claim: ClaimObject, plan_context: PlanContext | None) -> ClaimObject:
    """Merge user-provided plan context into the ClaimObject."""
    if plan_context is None:
        return claim

    if plan_context.plan_type:
        claim.identification.plan_type = plan_context.plan_type

    if plan_context.regulation_type:
        claim.identification.erisa_or_state_regulated = plan_context.regulation_type

    if plan_context.state:
        claim.identification.plan_jurisdiction = plan_context.state.upper()

    return claim


def _build_enrichment_dict(
    codes: CodeLookupResult,
    regulation: RegulationEnrichment,
    state_rules: StateRulesEnrichment,
) -> dict[str, Any]:
    return {
        "codes": {
            code_key: {
                "code": desc.code,
                "code_type": desc.code_type,
                "description": desc.description,
                "plain_english": desc.plain_english,
                "common_fix": desc.common_fix,
                "source": desc.source,
                "source_url": desc.source_url,
                "found": desc.found,
            }
            for code_key, desc in codes.codes.items()
        },
        "npi_details": codes.npi_details,
        "regulations": {
            "regulation_type": regulation.regulation_type,
            "applicable_laws": [law.model_dump() for law in regulation.applicable_laws],
            "appeal_process": regulation.appeal_process,
            "internal_appeal_deadline_days": regulation.internal_appeal_deadline_days,
            "plan_review_deadline_days": regulation.plan_review_deadline_days,
            "expedited_turnaround_hours": regulation.expedited_turnaround_hours,
            "external_review_available": regulation.external_review_available,
            "required_notice_elements": regulation.required_notice_elements,
            "coverage_determination": regulation.coverage_determination,
            "coverage_url": regulation.coverage_url,
        },
        "state_rules": {
            "state": state_rules.state,
            "doi_contact": state_rules.doi_contact,
            "appeal_rules": state_rules.appeal_rules,
            "state_deadlines": state_rules.state_deadlines,
            "consumer_resources": state_rules.consumer_resources,
            "external_review_available": state_rules.external_review_available,
            "external_review_url": state_rules.external_review_url,
            "regulatory_routing": state_rules.regulatory_routing,
            "routing_reason": state_rules.routing_reason,
        },
    }


def _collect_sources(
    codes: CodeLookupResult,
    regulation: RegulationEnrichment,
    state_rules: StateRulesEnrichment,
) -> list[dict[str, Any]]:
    sources = []

    for citation in codes.sources:
        sources.append({
            "entity": citation.entity,
            "source_name": citation.source_name,
            "url": citation.url,
        })

    for law in regulation.applicable_laws:
        sources.append({
            "entity": law.section,
            "source_name": law.law,
            "url": law.url,
        })

    if state_rules.doi_contact.get("website"):
        sources.append({
            "entity": f"{state_rules.state} DOI",
            "source_name": state_rules.doi_contact.get("name", "State DOI"),
            "url": state_rules.doi_contact.get("website", ""),
        })

    return sources


async def run_orchestrator(
    claim: ClaimObject,
    plan_context: PlanContext | None = None,
) -> OrchestratorResult:
    """
    Full synchronous orchestration — returns complete result when done.
    Used by POST /api/v1/claims/analyze.
    """
    # Apply plan context from wizard
    claim = _apply_plan_context(claim, plan_context)

    logger.info(f"Orchestrator: starting analysis for claim {claim.upload_id}")

    # Stage 0: Classify root cause first so regulation agent can use it for CMS coverage lookup
    logger.info("Orchestrator: pre-classifying root cause")
    root_cause_pre = await classify_root_cause(claim)
    claim.derived.root_cause_category = root_cause_pre.category
    logger.info(f"Orchestrator: root cause pre-classified as {root_cause_pre.category}")

    # Stage 1: Run Code Lookup, Regulation, and State Rules agents in parallel
    logger.info("Orchestrator: dispatching parallel agents (code lookup, regulation, state rules)")
    code_result, regulation_result, state_result = await asyncio.gather(
        run_code_lookup_agent(claim),
        run_regulation_agent(claim),
        run_state_rules_agent(claim),
        return_exceptions=False,
    )

    logger.info("Orchestrator: parallel agents complete — running Analysis Agent")

    # Stage 2: Run Analysis Agent (sequential — needs enrichment data)
    analysis_result: AnalysisResult = await run_analysis_agent(claim)

    logger.info("Orchestrator: Analysis Agent complete — assembling response")

    enrichment = _build_enrichment_dict(code_result, regulation_result, state_result)
    sources = _collect_sources(code_result, regulation_result, state_result)

    return OrchestratorResult(
        claim_object=claim.model_dump(mode="json"),
        enrichment=enrichment,
        analysis=analysis_result.model_dump(),
        sources=sources,
    )


async def stream_orchestrator(
    claim: ClaimObject,
    plan_context: PlanContext | None = None,
) -> AsyncGenerator[OrchestratorProgress, None]:
    """
    Streaming orchestration via async generator — yields progress events.
    Used by POST /api/v1/claims/analyze/stream (SSE).

    Events emitted:
      started             → pipeline has begun
      codes_enriched      → code lookup complete
      regulations_enriched → regulation agent complete
      state_rules_enriched → state rules agent complete
      analysis_complete   → analysis agent complete
      done                → full response ready
    """
    claim = _apply_plan_context(claim, plan_context)
    logger.info(f"Orchestrator (streaming): starting for claim {claim.upload_id}")

    yield OrchestratorProgress(
        event="started",
        data={"message": "Analysis pipeline started", "upload_id": claim.upload_id},
    )

    # Stage 0: Pre-classify root cause so regulation agent has it available
    root_cause_pre = await classify_root_cause(claim)
    claim.derived.root_cause_category = root_cause_pre.category

    # Run all 3 parallel agents and yield as each completes
    code_task = asyncio.create_task(run_code_lookup_agent(claim))
    regulation_task = asyncio.create_task(run_regulation_agent(claim))
    state_task = asyncio.create_task(run_state_rules_agent(claim))

    code_result: CodeLookupResult = await code_task
    yield OrchestratorProgress(
        event="codes_enriched",
        data={
            "codes": {
                k: {
                    "description": v.description,
                    "plain_english": v.plain_english,
                    "found": v.found,
                }
                for k, v in code_result.codes.items()
            },
            "code_count": len(code_result.codes),
        },
    )

    regulation_result: RegulationEnrichment = await regulation_task
    yield OrchestratorProgress(
        event="regulations_enriched",
        data={
            "regulation_type": regulation_result.regulation_type,
            "applicable_laws_count": len(regulation_result.applicable_laws),
            "internal_appeal_deadline_days": regulation_result.internal_appeal_deadline_days,
            "external_review_available": regulation_result.external_review_available,
        },
    )

    state_result: StateRulesEnrichment = await state_task
    yield OrchestratorProgress(
        event="state_rules_enriched",
        data={
            "state": state_result.state,
            "regulatory_routing": state_result.regulatory_routing,
            "doi_name": state_result.doi_contact.get("name", ""),
            "doi_phone": state_result.doi_contact.get("phone", ""),
        },
    )

    # Analysis (sequential)
    analysis_result: AnalysisResult = await run_analysis_agent(claim)
    yield OrchestratorProgress(
        event="analysis_complete",
        data={
            "root_cause": analysis_result.root_cause,
            "severity_triage": analysis_result.severity_triage,
            "approval_probability": analysis_result.approval_probability.get("score"),
            "deadlines": analysis_result.deadlines,
        },
    )

    # Final combined response
    enrichment = _build_enrichment_dict(code_result, regulation_result, state_result)
    sources = _collect_sources(code_result, regulation_result, state_result)

    yield OrchestratorProgress(
        event="done",
        data={
            "claim_object": claim.model_dump(mode="json"),
            "enrichment": enrichment,
            "analysis": analysis_result.model_dump(),
            "sources": sources,
        },
    )

    logger.info("Orchestrator (streaming): complete")
