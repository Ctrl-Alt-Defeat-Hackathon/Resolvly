"""
Output Generation Routes

POST /api/v1/outputs/summary          → plain-English denial summary
POST /api/v1/outputs/action-checklist → numbered action steps
POST /api/v1/outputs/appeal-letter    → appeal letter + provider/insurer messages
POST /api/v1/outputs/provider-brief   → one-page physician-facing summary
POST /api/v1/outputs/deadlines        → deadlines with ICS data
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.output_agent import (
    generate_summary,
    generate_action_checklist,
    generate_appeal_letter,
    generate_provider_brief,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class OutputRequest(BaseModel):
    claim_object: dict[str, Any]
    analysis: dict[str, Any]
    # enrichment is the top-level enrichment dict from /claims/analyze response.
    # Passed separately here so output agent can include applicable laws and
    # appeal process in generated letters/summaries.
    enrichment: dict[str, Any] = {}


class AppealLetterRequest(BaseModel):
    claim_object: dict[str, Any]
    analysis: dict[str, Any]
    enrichment: dict[str, Any] = {}
    patient_info: dict[str, str] = {}


class DeadlinesRequest(BaseModel):
    claim_object: dict[str, Any]
    analysis: dict[str, Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/summary")
async def get_summary(req: OutputRequest) -> dict[str, Any]:
    """Generate plain-English denial summary."""
    try:
        analysis = {**req.analysis, "enrichment": req.enrichment}
        result = await generate_summary(req.claim_object, analysis)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


@router.post("/action-checklist")
async def get_action_checklist(req: OutputRequest) -> dict[str, Any]:
    """Generate numbered action steps with why-expanders."""
    try:
        analysis = {**req.analysis, "enrichment": req.enrichment}
        result = await generate_action_checklist(req.claim_object, analysis)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Action checklist generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Action checklist generation failed: {str(e)}")


@router.post("/appeal-letter")
async def get_appeal_letter(req: AppealLetterRequest) -> dict[str, Any]:
    """Generate appeal letter, provider message, and insurer message (3 tabs)."""
    try:
        analysis = {**req.analysis, "enrichment": req.enrichment}
        result = await generate_appeal_letter(
            claim_dict=req.claim_object,
            analysis_dict=analysis,
            patient_info=req.patient_info or None,
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"Appeal letter generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Appeal letter generation failed: {str(e)}")


@router.post("/provider-brief")
async def get_provider_brief(req: OutputRequest) -> dict[str, Any]:
    """Generate one-page provider brief for treating physician."""
    try:
        analysis = {**req.analysis, "enrichment": req.enrichment}
        result = await generate_provider_brief(req.claim_object, analysis)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Provider brief generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Provider brief generation failed: {str(e)}")


@router.post("/deadlines")
async def get_deadlines(req: DeadlinesRequest) -> dict[str, Any]:
    """Return structured deadlines with ICS calendar event data."""
    try:
        analysis = req.analysis
        deadlines_raw = analysis.get("deadlines", {})
        ics_events = analysis.get("ics_events", [])

        deadlines_list = []
        for deadline_type, info in deadlines_raw.items():
            if not isinstance(info, dict):
                continue
            entry: dict[str, Any] = {
                "type": deadline_type,
                "date": info.get("date"),
                "days_remaining": info.get("days_remaining"),
                "source_law": info.get("source", ""),
                "already_passed": info.get("already_passed", False),
            }
            # Attach matching ICS event if available
            for ics in ics_events:
                if ics.get("date") == info.get("date"):
                    entry["ics_data"] = _build_ics_string(
                        title=ics.get("title", f"Appeal deadline: {deadline_type}"),
                        event_date=ics.get("date", ""),
                        description=ics.get("description", ""),
                        alarm_days_before=ics.get("alarm_days_before", 14),
                    )
                    break
            deadlines_list.append(entry)

        return {
            "deadlines": deadlines_list,
            "reminders": {"email_opt_in_url": ""},  # Phase 3 feature
        }
    except Exception as e:
        logger.error(f"Deadlines endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Deadlines failed: {str(e)}")


# ---------------------------------------------------------------------------
# ICS helper (minimal, used by deadlines endpoint)
# ---------------------------------------------------------------------------

def _build_ics_string(
    title: str,
    event_date: str,
    description: str,
    alarm_days_before: int = 14,
) -> str:
    """Build an inline ICS string for a single event (no library dependency)."""
    if not event_date:
        return ""
    date_compact = event_date.replace("-", "")
    alarm_minutes = alarm_days_before * 24 * 60
    desc_escaped = description.replace("\n", "\\n").replace(",", "\\,")
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CBH Insurance Debugger//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{date_compact}\r\n"
        f"DTEND;VALUE=DATE:{date_compact}\r\n"
        f"SUMMARY:{title}\r\n"
        f"DESCRIPTION:{desc_escaped}\r\n"
        "BEGIN:VALARM\r\n"
        "ACTION:DISPLAY\r\n"
        f"DESCRIPTION:Reminder: {title}\r\n"
        f"TRIGGER:-PT{alarm_minutes}M\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
