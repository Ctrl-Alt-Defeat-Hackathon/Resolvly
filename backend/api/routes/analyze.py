"""
Claim Analysis API Routes

POST /api/v1/claims/analyze        — Full synchronous analysis
POST /api/v1/claims/analyze/stream — Server-Sent Events (SSE) streaming analysis

The streaming endpoint emits partial results as each agent completes,
allowing the frontend to progressively render the dashboard.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from extraction.schema import ClaimObject, PlanContext
from agents.orchestrator import run_orchestrator, stream_orchestrator

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    claim_object: dict[str, Any]
    plan_context: dict[str, Any] | None = None


class AnalyzeResponse(BaseModel):
    enrichment: dict[str, Any]
    analysis: dict[str, Any]
    sources: list[dict[str, Any]]
    claim_object: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_claim(raw: dict[str, Any]) -> ClaimObject:
    try:
        return ClaimObject.model_validate(raw)
    except (ValidationError, Exception) as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid claim_object: {e}",
        )


def _parse_plan_context(raw: dict[str, Any] | None) -> PlanContext | None:
    if raw is None:
        return None
    try:
        return PlanContext.model_validate(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /analyze — Synchronous full analysis
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_claim(request: Request, body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run the full analysis pipeline synchronously.

    Dispatches Code Lookup, Regulation, and State Rules agents in parallel,
    then runs the Analysis Agent, and returns the complete result.

    Typical response time: 8–16 seconds.
    """
    claim = _parse_claim(body.claim_object)
    plan_context = _parse_plan_context(body.plan_context)

    try:
        result = await run_orchestrator(claim, plan_context)
    except Exception as e:
        logger.error(f"Orchestrator failed for upload_id={claim.upload_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    return AnalyzeResponse(
        enrichment=result.enrichment,
        analysis=result.analysis,
        sources=result.sources,
        claim_object=result.claim_object,
    )


# ---------------------------------------------------------------------------
# POST /analyze/stream — SSE streaming analysis
# ---------------------------------------------------------------------------

@router.post("/analyze/stream")
@limiter.limit("5/minute")
async def analyze_claim_stream(request: Request, body: AnalyzeRequest) -> StreamingResponse:
    """
    Run the analysis pipeline with Server-Sent Events (SSE) streaming.

    Emits partial results as each agent completes, allowing the frontend
    to render the dashboard progressively.

    SSE event types:
      started             → pipeline has begun
      codes_enriched      → code lookup complete
      regulations_enriched → regulation agent complete
      state_rules_enriched → state rules agent complete
      analysis_complete   → analysis agent complete
      done                → full response (same as /analyze)
      error               → pipeline failed
    """
    claim = _parse_claim(body.claim_object)
    plan_context = _parse_plan_context(body.plan_context)

    async def event_generator():
        try:
            async for progress in stream_orchestrator(claim, plan_context):
                # Format as SSE
                event_line = f"event: {progress.event}\n"
                data_line = f"data: {json.dumps(progress.data)}\n\n"
                yield event_line + data_line
        except Exception as e:
            logger.error(f"SSE stream error for upload_id={claim.upload_id}: {e}", exc_info=True)
            error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            yield error_event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering
            "Connection": "keep-alive",
        },
    )
