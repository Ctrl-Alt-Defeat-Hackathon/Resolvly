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
from tools.llm_client import is_llm_available

logger = logging.getLogger(__name__)

# Per-agent wall-clock timeout (seconds).  Exceed → agent is treated as failed
# but the rest of the pipeline continues with an empty default result.
_AGENT_TIMEOUTS: dict[str, float] = {
    "code_lookup_agent": 15.0,
    "regulation_agent": 20.0,
    "state_rules_agent": 20.0,
    "analysis_agent": 30.0,
}


async def _with_timeout(coro, timeout_s: float, agent_name: str):
    """
    Await *coro* with a hard timeout.  Raises asyncio.TimeoutError (which
    asyncio.gather catches when return_exceptions=True) on expiry.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning(f"{agent_name} timed out after {timeout_s}s")
        raise


class OrchestratorResult(BaseModel):
    claim_object: dict[str, Any] = {}
    enrichment: dict[str, Any] = {}
    analysis: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    # Per-agent execution status: "ok" | "timeout" | "error"
    agent_status: dict[str, str] = {}
    # False when no LLM key is configured and Ollama is disabled
    llm_available: bool = True


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
            "state_deadlines": state_rules.state_deadlines.model_dump(),
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


def _unpack_agent_outcomes(
    outcomes: tuple,
    errors: list[str],
    agent_status: dict[str, str],
) -> tuple[CodeLookupResult, RegulationEnrichment, StateRulesEnrichment]:
    """
    Unpack asyncio.gather(return_exceptions=True) results for the 3 parallel agents.
    Substitutes an empty default when an agent fails, and records the error.
    Populates agent_status with "ok" | "timeout" | "error" per agent.
    """
    names = ("code_lookup_agent", "regulation_agent", "state_rules_agent")
    defaults = (CodeLookupResult(), RegulationEnrichment(), StateRulesEnrichment())
    results = []
    for name, outcome, default in zip(names, outcomes, defaults):
        if isinstance(outcome, Exception):
            status = "timeout" if isinstance(outcome, asyncio.TimeoutError) else "error"
            logger.error(f"{name} failed ({status}): {outcome}")
            errors.append(f"{name}: {outcome}")
            agent_status[name] = status
            results.append(default)
        else:
            agent_status[name] = "ok"
            results.append(outcome)
    return tuple(results)


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
    # return_exceptions=True: one failing agent doesn't kill the entire run
    logger.info("Orchestrator: dispatching parallel agents (code lookup, regulation, state rules)")
    outcomes = await asyncio.gather(
        _with_timeout(run_code_lookup_agent(claim), _AGENT_TIMEOUTS["code_lookup_agent"], "code_lookup_agent"),
        _with_timeout(run_regulation_agent(claim), _AGENT_TIMEOUTS["regulation_agent"], "regulation_agent"),
        _with_timeout(run_state_rules_agent(claim), _AGENT_TIMEOUTS["state_rules_agent"], "state_rules_agent"),
        return_exceptions=True,
    )

    pipeline_errors: list[str] = []
    agent_status: dict[str, str] = {}
    code_result, regulation_result, state_result = _unpack_agent_outcomes(
        outcomes, pipeline_errors, agent_status
    )

    logger.info("Orchestrator: parallel agents complete — running Analysis Agent")

    # Stage 2: Run Analysis Agent — pass root_cause_pre and code_result to avoid re-work
    try:
        analysis_result: AnalysisResult = await _with_timeout(
            run_analysis_agent(claim, root_cause_result=root_cause_pre, code_lookup_result=code_result),
            _AGENT_TIMEOUTS["analysis_agent"],
            "analysis_agent",
        )
        agent_status["analysis_agent"] = "ok"
    except Exception as e:
        status = "timeout" if isinstance(e, asyncio.TimeoutError) else "error"
        logger.error(f"Analysis Agent failed ({status}): {e}")
        pipeline_errors.append(f"analysis_agent: {e}")
        agent_status["analysis_agent"] = status
        analysis_result = AnalysisResult()

    logger.info("Orchestrator: Analysis Agent complete — assembling response")

    enrichment = _build_enrichment_dict(code_result, regulation_result, state_result)
    sources = _collect_sources(code_result, regulation_result, state_result)

    return OrchestratorResult(
        claim_object=claim.model_dump(mode="json"),
        enrichment=enrichment,
        analysis=analysis_result.model_dump(),
        sources=sources,
        errors=pipeline_errors,
        agent_status=agent_status,
        llm_available=is_llm_available(),
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
    stream_errors: list[str] = []
    stream_agent_status: dict[str, str] = {}
    code_task = asyncio.create_task(
        _with_timeout(run_code_lookup_agent(claim), _AGENT_TIMEOUTS["code_lookup_agent"], "code_lookup_agent")
    )
    regulation_task = asyncio.create_task(
        _with_timeout(run_regulation_agent(claim), _AGENT_TIMEOUTS["regulation_agent"], "regulation_agent")
    )
    state_task = asyncio.create_task(
        _with_timeout(run_state_rules_agent(claim), _AGENT_TIMEOUTS["state_rules_agent"], "state_rules_agent")
    )

    try:
        code_result: CodeLookupResult = await code_task
        stream_agent_status["code_lookup_agent"] = "ok"
    except Exception as e:
        status = "timeout" if isinstance(e, asyncio.TimeoutError) else "error"
        logger.error(f"code_lookup_agent failed (streaming, {status}): {e}")
        stream_errors.append(f"code_lookup_agent: {e}")
        stream_agent_status["code_lookup_agent"] = status
        code_result = CodeLookupResult()

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

    try:
        regulation_result: RegulationEnrichment = await regulation_task
        stream_agent_status["regulation_agent"] = "ok"
    except Exception as e:
        status = "timeout" if isinstance(e, asyncio.TimeoutError) else "error"
        logger.error(f"regulation_agent failed (streaming, {status}): {e}")
        stream_errors.append(f"regulation_agent: {e}")
        stream_agent_status["regulation_agent"] = status
        regulation_result = RegulationEnrichment()

    yield OrchestratorProgress(
        event="regulations_enriched",
        data={
            "regulation_type": regulation_result.regulation_type,
            "applicable_laws_count": len(regulation_result.applicable_laws),
            "internal_appeal_deadline_days": regulation_result.internal_appeal_deadline_days,
            "external_review_available": regulation_result.external_review_available,
        },
    )

    try:
        state_result: StateRulesEnrichment = await state_task
        stream_agent_status["state_rules_agent"] = "ok"
    except Exception as e:
        status = "timeout" if isinstance(e, asyncio.TimeoutError) else "error"
        logger.error(f"state_rules_agent failed (streaming, {status}): {e}")
        stream_errors.append(f"state_rules_agent: {e}")
        stream_agent_status["state_rules_agent"] = status
        state_result = StateRulesEnrichment()

    yield OrchestratorProgress(
        event="state_rules_enriched",
        data={
            "state": state_result.state,
            "regulatory_routing": state_result.regulatory_routing,
            "doi_name": state_result.doi_contact.get("name", ""),
            "doi_phone": state_result.doi_contact.get("phone", ""),
        },
    )

    # Analysis (sequential) — reuse root_cause_pre and code_result to skip re-work
    try:
        analysis_result: AnalysisResult = await _with_timeout(
            run_analysis_agent(claim, root_cause_result=root_cause_pre, code_lookup_result=code_result),
            _AGENT_TIMEOUTS["analysis_agent"],
            "analysis_agent",
        )
        stream_agent_status["analysis_agent"] = "ok"
    except Exception as e:
        status = "timeout" if isinstance(e, asyncio.TimeoutError) else "error"
        logger.error(f"analysis_agent failed (streaming, {status}): {e}")
        stream_errors.append(f"analysis_agent: {e}")
        stream_agent_status["analysis_agent"] = status
        analysis_result = AnalysisResult()

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
            "errors": stream_errors,
            "agent_status": stream_agent_status,
            "llm_available": is_llm_available(),
        },
    )

    logger.info("Orchestrator (streaming): complete")
