"""
Export Routes

POST /api/v1/export/pdf  → Generate PDF from markdown content
POST /api/v1/export/ics  → Generate .ics calendar file for a deadline
"""
from __future__ import annotations

import io
import logging
import re
import textwrap
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PDFExportRequest(BaseModel):
    content: str
    format: Literal["appeal_letter", "provider_brief", "summary"] = "appeal_letter"
    title: str = ""


class ICSExportRequest(BaseModel):
    event_title: str
    event_date: str          # ISO date: YYYY-MM-DD
    description: str = ""
    reminder_days_before: list[int] = [30, 7]


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------

def _markdown_to_plain_lines(markdown: str) -> list[tuple[str, str]]:
    """
    Convert markdown to a list of (style, text) tuples for FPDF rendering.
    Styles: 'h1', 'h2', 'h3', 'bold', 'body', 'hr', 'blank'
    """
    lines = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()

        if line.startswith("### "):
            lines.append(("h3", line[4:].strip()))
        elif line.startswith("## "):
            lines.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            lines.append(("h1", line[2:].strip()))
        elif line.startswith("---") or line.startswith("==="):
            lines.append(("hr", ""))
        elif line.startswith("**") and line.endswith("**") and len(line) > 4:
            lines.append(("bold", line[2:-2]))
        elif line.strip() == "":
            lines.append(("blank", ""))
        else:
            # Strip inline markdown: **bold**, *italic*, `code`
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            clean = re.sub(r"`(.+?)`", r"\1", clean)
            clean = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", clean)
            lines.append(("body", clean))

    return lines


def _generate_pdf(content: str, title: str, doc_format: str) -> bytes:
    """Render markdown content to PDF bytes using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="PDF export requires fpdf2. Install with: pip install fpdf2",
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(left=20, top=20, right=20)

    # Header
    pdf.set_font("Helvetica", style="B", size=14)
    display_title = title or {
        "appeal_letter": "Insurance Appeal Letter",
        "provider_brief": "Provider Brief",
        "summary": "Denial Summary",
    }.get(doc_format, "Insurance Document")
    pdf.cell(0, 10, display_title, ln=True, align="C")
    pdf.ln(4)

    # Content
    parsed_lines = _markdown_to_plain_lines(content)
    page_width = pdf.w - pdf.l_margin - pdf.r_margin

    for style, text in parsed_lines:
        if style == "h1":
            pdf.set_font("Helvetica", style="B", size=13)
            pdf.multi_cell(page_width, 8, text)
            pdf.ln(2)
        elif style == "h2":
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.multi_cell(page_width, 7, text)
            pdf.ln(1)
        elif style == "h3":
            pdf.set_font("Helvetica", style="BI", size=11)
            pdf.multi_cell(page_width, 6, text)
            pdf.ln(1)
        elif style == "bold":
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.multi_cell(page_width, 6, text)
        elif style == "hr":
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(3)
        elif style == "blank":
            pdf.ln(4)
        else:  # body
            pdf.set_font("Helvetica", size=10)
            # Handle bullet points
            stripped = text.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                bullet_text = "  \u2022  " + stripped[2:]
                pdf.multi_cell(page_width, 5, bullet_text)
            elif re.match(r"^\d+\.\s", stripped):
                pdf.multi_cell(page_width, 5, "  " + stripped)
            else:
                pdf.multi_cell(page_width, 5, text)

    return bytes(pdf.output())


@router.post("/pdf")
async def export_pdf(req: PDFExportRequest) -> Response:
    """Generate a PDF from markdown content and return as binary stream."""
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    try:
        pdf_bytes = _generate_pdf(req.content, req.title, req.format)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    filename_map = {
        "appeal_letter": "appeal_letter.pdf",
        "provider_brief": "provider_brief.pdf",
        "summary": "denial_summary.pdf",
    }
    filename = filename_map.get(req.format, "document.pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# ICS export
# ---------------------------------------------------------------------------

def _build_ics(
    event_title: str,
    event_date: str,
    description: str,
    reminder_days_before: list[int],
) -> str:
    """Build a complete .ics (iCalendar) file string."""
    date_compact = event_date.replace("-", "")

    # Build VALARM blocks for each reminder
    alarm_blocks = ""
    for days in sorted(reminder_days_before, reverse=True):
        alarm_minutes = days * 24 * 60
        alarm_blocks += (
            "BEGIN:VALARM\r\n"
            "ACTION:DISPLAY\r\n"
            f"DESCRIPTION:Reminder: {event_title} in {days} days\r\n"
            f"TRIGGER:-PT{alarm_minutes}M\r\n"
            "END:VALARM\r\n"
        )

    desc_escaped = description.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    title_escaped = event_title.replace(",", "\\,").replace(";", "\\;")

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//CBH Insurance Debugger//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
        "BEGIN:VEVENT\r\n"
        f"DTSTART;VALUE=DATE:{date_compact}\r\n"
        f"DTEND;VALUE=DATE:{date_compact}\r\n"
        f"SUMMARY:{title_escaped}\r\n"
        f"DESCRIPTION:{desc_escaped}\r\n"
        f"STATUS:CONFIRMED\r\n"
        f"{alarm_blocks}"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


@router.post("/ics")
async def export_ics(req: ICSExportRequest) -> Response:
    """Generate a .ics calendar file for a deadline event."""
    if not req.event_title:
        raise HTTPException(status_code=400, detail="event_title is required")
    if not req.event_date:
        raise HTTPException(status_code=400, detail="event_date is required")

    # Validate date format
    try:
        date.fromisoformat(req.event_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="event_date must be ISO format YYYY-MM-DD")

    try:
        ics_content = _build_ics(
            event_title=req.event_title,
            event_date=req.event_date,
            description=req.description,
            reminder_days_before=req.reminder_days_before,
        )
    except Exception as e:
        logger.error(f"ICS generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"ICS generation failed: {str(e)}")

    safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", req.event_title)[:40]
    filename = f"{safe_title}.ics"

    return Response(
        content=ics_content.encode("utf-8"),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
