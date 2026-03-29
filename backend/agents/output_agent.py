"""
Output Generation Agent

Takes the ClaimObject + analysis results and generates all user-facing content
using Gemini 2.5 Flash.

Outputs:
  - plain_english_summary   → one-paragraph denial explanation for patients
  - action_checklist        → numbered steps with why-expanders
  - appeal_letter           → formal letter citing regulations and clinical facts
  - provider_message        → message to provider's billing office
  - insurer_message         → message to insurer's member services
  - provider_brief          → one-page summary for treating physician
"""
from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class ActionStep(BaseModel):
    number: int
    action: str
    detail: str
    why: str
    responsible_party: str
    expected_timeline: str
    contact: dict[str, str] = {}


class ActionChecklist(BaseModel):
    steps: list[ActionStep] = []
    total_steps: int = 0


class AppealLetterOutput(BaseModel):
    appeal_letter: str = ""
    provider_message: str = ""
    insurer_message: str = ""
    legal_citations: list[dict[str, str]] = []


class SummaryOutput(BaseModel):
    summary_text: str = ""
    reading_level: str = "8th grade"
    key_points: list[str] = []


class ProviderBriefOutput(BaseModel):
    brief_text: str = ""
    format: str = "markdown"
    pdf_ready: bool = True


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client | None:
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("Output Agent: GEMINI_API_KEY not set — skipping LLM generation")
        return None
    return genai.Client(api_key=settings.gemini_api_key)


def _claim_context_summary(claim_dict: dict[str, Any], analysis_dict: dict[str, Any]) -> str:
    """Build a compact context string for LLM prompts."""
    ident = claim_dict.get("identification", {})
    denial = claim_dict.get("denial_reason", {})
    service = claim_dict.get("service_billing", {})
    financial = claim_dict.get("financial", {})
    appeal_rights = claim_dict.get("appeal_rights", {})

    root_cause = analysis_dict.get("root_cause", {})
    deadlines = analysis_dict.get("deadlines", {})
    completeness = analysis_dict.get("denial_completeness", {})
    probability = analysis_dict.get("approval_probability", {})
    # enrichment is passed as a separate top-level key alongside analysis
    enrichment = analysis_dict.get("enrichment", {}) or {}
    regulations = enrichment.get("regulations", {}) if enrichment else {}

    lines = [
        f"CLAIM REFERENCE: {ident.get('claim_reference_number', 'Unknown')}",
        f"PLAN TYPE: {ident.get('plan_type', 'Unknown')}",
        f"REGULATION TYPE: {ident.get('erisa_or_state_regulated', 'Unknown')}",
        f"STATE: {ident.get('plan_jurisdiction', 'Unknown')}",
        f"DATE OF DENIAL: {ident.get('date_of_denial', 'Unknown')}",
        f"DATE OF SERVICE: {ident.get('date_of_service', 'Unknown')}",
        f"",
        f"DENIED PROCEDURE(S): {service.get('procedure_description', 'Unknown')}",
        f"CPT CODES: {', '.join(service.get('cpt_procedure_codes', []) or [])}",
        f"ICD-10 CODES: {', '.join(service.get('icd10_diagnosis_codes', []) or [])}",
        f"",
        f"DENIAL REASON TEXT: {denial.get('denial_reason_narrative', 'Not specified')}",
        f"DENIAL CODES (CARC): {', '.join(denial.get('carc_codes', []) or [])}",
        f"",
        f"AMOUNT BILLED: {financial.get('billed_amount', 'Unknown')}",
        f"AMOUNT DENIED: {financial.get('denied_amount', 'Unknown')}",
        f"",
        f"ROOT CAUSE: {root_cause.get('category', 'Unknown')} (confidence: {root_cause.get('confidence', 0):.0%})",
        f"RESPONSIBLE PARTY: {root_cause.get('responsible_party', 'Unknown')}",
        f"ROOT CAUSE REASONING: {root_cause.get('reasoning', '')}",
        f"",
        f"APPROVAL PROBABILITY: {probability.get('score', 0):.0%}",
        f"COMPLETENESS SCORE: {completeness.get('score', 0):.0%}",
        f"MISSING FIELDS: {', '.join(completeness.get('missing_fields', []) or [])}",
        f"",
        f"APPLICABLE LAWS: {', '.join(l.get('law', '') + ' ' + l.get('section', '') for l in regulations.get('applicable_laws', []))}",
        f"INTERNAL APPEAL DEADLINE: {deadlines.get('internal_appeal', {}).get('date', 'Unknown')} ({deadlines.get('internal_appeal', {}).get('days_remaining', '?')} days remaining)",
        f"",
        f"APPEAL CONTACT: {appeal_rights.get('insurer_appeals_address', '')}",
        f"INSURER PHONE: {appeal_rights.get('insurer_appeals_phone', '')}",
    ]
    return "\n".join(lines)


async def _call_gemini(prompt: str, expect_json: bool = False) -> str:
    """Call Gemini with a prompt. Returns text response or empty string on failure."""
    settings = get_settings()
    client = _get_client()
    if client is None:
        return ""

    for model in (settings.gemini_model_primary, settings.gemini_model_fallback):
        try:
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            )
            if expect_json:
                config = types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                )
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.warning(f"Output Agent: Gemini model {model} failed: {e}")
            continue

    logger.error("Output Agent: all Gemini models failed")
    return ""


# ---------------------------------------------------------------------------
# Public generation functions
# ---------------------------------------------------------------------------

async def generate_summary(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> SummaryOutput:
    """Generate plain-English denial summary for a patient."""
    context = _claim_context_summary(claim_dict, analysis_dict)
    root_cause = analysis_dict.get("root_cause", {})
    root_cause_category = root_cause.get("category", "unknown")

    prompt = f"""You are an insurance advocate helping a patient understand their insurance denial.

CLAIM INFORMATION:
{context}

Write a plain-English explanation of this insurance denial for the patient. The explanation must:
1. Be written at an 8th grade reading level — no jargon
2. Start with what was denied and why, in simple terms
3. Explain what the root cause is ({root_cause_category}) and what it means for them
4. Briefly mention what they can do about it (appeal, contact provider, etc.)
5. Be 2-3 short paragraphs maximum
6. Be empathetic and actionable, not scary

Return a JSON object with exactly these fields:
{{
  "summary_text": "<2-3 paragraph plain-English explanation>",
  "reading_level": "8th grade",
  "key_points": ["<bullet 1>", "<bullet 2>", "<bullet 3>"]
}}

Key points should be 3 short sentence fragments capturing the most important takeaways.
"""
    raw = await _call_gemini(prompt, expect_json=True)
    if not raw:
        return SummaryOutput(
            summary_text="Unable to generate summary — LLM service unavailable.",
            key_points=["Check denial reason codes", "Contact your insurer", "Consider filing an appeal"],
        )
    try:
        data = json.loads(raw)
        return SummaryOutput(**data)
    except Exception as e:
        logger.error(f"Output Agent: failed to parse summary JSON: {e}")
        return SummaryOutput(summary_text=raw)


async def generate_action_checklist(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> ActionChecklist:
    """Generate numbered action steps with why-expanders."""
    context = _claim_context_summary(claim_dict, analysis_dict)
    root_cause = analysis_dict.get("root_cause", {})
    deadlines = analysis_dict.get("deadlines", {})
    state_rules = analysis_dict.get("enrichment", {}).get("state_rules", {}) if analysis_dict.get("enrichment") else {}
    doi_contact = state_rules.get("doi_contact", {}) if state_rules else {}

    prompt = f"""You are an insurance advocate. Generate a step-by-step action plan for a patient to resolve their insurance denial.

CLAIM INFORMATION:
{context}

Generate an action checklist with 4-7 steps. Each step must be specific, actionable, and tailored to this exact denial.

Rules:
- Order steps logically (most urgent first if deadline is soon)
- Assign each step to the correct responsible_party: "patient", "provider", or "insurer"
- Include contact info where known (from claim data above)
- Expected timeline should be realistic business-day estimates

Return a JSON object with this exact structure:
{{
  "steps": [
    {{
      "number": 1,
      "action": "<short action title, imperative, max 10 words>",
      "detail": "<specific instructions for this step, 1-2 sentences>",
      "why": "<explanation of why this step matters, 1-2 sentences>",
      "responsible_party": "patient" | "provider" | "insurer",
      "expected_timeline": "<e.g., '1-3 business days'>",
      "contact": {{
        "name": "<contact name if known, else empty>",
        "phone": "<phone if known, else empty>",
        "address": "<address if known, else empty>"
      }}
    }}
  ]
}}

DOI Contact info: {json.dumps(doi_contact)}
Internal appeal deadline: {deadlines.get('internal_appeal', {}).get('date', 'Unknown')} ({deadlines.get('internal_appeal', {}).get('days_remaining', '?')} days remaining)
"""
    raw = await _call_gemini(prompt, expect_json=True)
    if not raw:
        return ActionChecklist(steps=[], total_steps=0)
    try:
        data = json.loads(raw)
        steps = [ActionStep(**s) for s in data.get("steps", [])]
        return ActionChecklist(steps=steps, total_steps=len(steps))
    except Exception as e:
        logger.error(f"Output Agent: failed to parse checklist JSON: {e}")
        return ActionChecklist(steps=[], total_steps=0)


async def generate_appeal_letter(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
    patient_info: dict[str, str] | None = None,
) -> AppealLetterOutput:
    """Generate appeal letter, provider message, and insurer message."""
    context = _claim_context_summary(claim_dict, analysis_dict)
    patient = patient_info or {}
    patient_name = patient.get("name", "[PATIENT NAME]")
    patient_address = patient.get("address", "[PATIENT ADDRESS]")
    patient_phone = patient.get("phone", "[PATIENT PHONE]")
    patient_email = patient.get("email", "")

    enrichment = analysis_dict.get("enrichment", {}) or {}
    regulations = enrichment.get("regulations", {})
    appeal_process = regulations.get("appeal_process", [])
    applicable_laws = regulations.get("applicable_laws", [])
    root_cause = analysis_dict.get("root_cause", {})
    deadlines = analysis_dict.get("deadlines", {})
    ident = claim_dict.get("identification", {})

    appeal_address = claim_dict.get("appeal_rights", {}).get("insurer_appeals_address", "[INSURER APPEALS ADDRESS]")
    internal_deadline = deadlines.get("internal_appeal", {}).get("date", "Unknown")
    laws_text = "; ".join(
        f"{l.get('law', '')} {l.get('section', '')}" for l in applicable_laws
    ) or "applicable federal and state regulations"

    prompt = f"""You are an expert insurance appeal attorney. Generate three formal documents for an insurance denial appeal.

CLAIM INFORMATION:
{context}

PATIENT INFORMATION:
Name: {patient_name}
Address: {patient_address}
Phone: {patient_phone}
Email: {patient_email}

APPEAL DEADLINE: {internal_deadline}
APPEALS ADDRESS: {appeal_address}
APPLICABLE LAWS: {laws_text}
APPEAL PROCESS: {json.dumps(appeal_process)}

Generate three documents in Markdown format:

1. APPEAL LETTER — A formal letter to the insurance company appealing the denial. Must:
   - Use formal letter format with date, addresses, subject line
   - Cite specific regulations ({laws_text}) that support the appeal
   - Reference the specific denial reason and why it is incorrect or reversible
   - Reference the root cause: {root_cause.get('category', 'unknown')} — {root_cause.get('reasoning', '')}
   - Request specific remedies (reconsideration, coverage, payment)
   - Include a signature block for {patient_name}
   - Tone: firm, professional, factual

2. PROVIDER MESSAGE — A message from the patient to their provider's billing office. Must:
   - Explain the denial and what action is needed from the provider
   - Be conversational but professional
   - Request specific documentation or action (e.g., retroactive prior auth, corrected billing code, letter of medical necessity)
   - Be concise — 2-3 paragraphs

3. INSURER MESSAGE — A shorter message to the insurer's member services line. Must:
   - Request a status update or escalation
   - Reference the claim and denial
   - Be polite but persistent
   - 1-2 paragraphs

Return a JSON object with exactly:
{{
  "appeal_letter": "<full appeal letter in Markdown>",
  "provider_message": "<provider message in Markdown>",
  "insurer_message": "<insurer message in Markdown>",
  "legal_citations": [
    {{"law": "<law name>", "section": "<section>", "relevance": "<why cited>"}}
  ]
}}
"""
    raw = await _call_gemini(prompt, expect_json=True)
    if not raw:
        fallback_letter = _fallback_appeal_letter(patient_name, patient_address, ident, laws_text, appeal_address, internal_deadline, root_cause)
        return AppealLetterOutput(
            appeal_letter=fallback_letter,
            provider_message=f"Dear Billing Department,\n\nI am writing regarding claim {ident.get('claim_reference_number', 'Unknown')} which was denied. Please provide any documentation needed to support an appeal.\n\nThank you,\n{patient_name}",
            insurer_message=f"Dear Member Services,\n\nI am writing to appeal the denial of claim {ident.get('claim_reference_number', 'Unknown')}. Please confirm receipt of this appeal.\n\nThank you,\n{patient_name}",
            legal_citations=[],
        )
    try:
        data = json.loads(raw)
        return AppealLetterOutput(**data)
    except Exception as e:
        logger.error(f"Output Agent: failed to parse appeal letter JSON: {e}")
        return AppealLetterOutput(appeal_letter=raw)


async def generate_provider_brief(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> ProviderBriefOutput:
    """Generate a one-page provider-formatted summary for the treating physician."""
    context = _claim_context_summary(claim_dict, analysis_dict)
    root_cause = analysis_dict.get("root_cause", {})
    enrichment = analysis_dict.get("enrichment", {}) or {}
    codes = enrichment.get("codes", {})
    regulations = enrichment.get("regulations", {})

    code_descriptions = "\n".join(
        f"- {k}: {v.get('description', '')} — {v.get('plain_english', '')}"
        for k, v in codes.items()
    ) if codes else "No code descriptions available."

    prompt = f"""You are a medical billing specialist. Generate a one-page provider brief — a summary document for the treating physician to review and act on for their patient's insurance denial.

CLAIM INFORMATION:
{context}

CODE DESCRIPTIONS:
{code_descriptions}

The provider brief must be formatted in clean Markdown and include these sections:

## Patient Insurance Denial — Provider Action Required

**Date:** [today's date]
**RE:** [Claim reference, procedure, denial reason]

### Denial Summary
[2-3 sentences: what was denied, denial codes, root cause: {root_cause.get('category', 'unknown')}]

### Codes at Issue
[Table or bullet list of ICD-10 and CPT codes with their descriptions]

### Regulatory Context
[What regulations apply and what they require — {regulations.get('regulation_type', 'unknown')} plan]

### Requested Provider Actions
[Numbered list of specific actions the physician/billing staff should take — e.g., letter of medical necessity, retroactive prior auth, corrected coding, clinical documentation]

### Appeal Deadline
[Date and days remaining]

### Contact for Questions
[Patient contact info placeholder]

---
*This brief was generated to assist with insurance appeal. Clinical decisions remain with the treating provider.*

Make the brief concise, professional, and immediately actionable. Return a JSON object:
{{
  "brief_text": "<full provider brief in Markdown>",
  "format": "markdown",
  "pdf_ready": true
}}
"""
    raw = await _call_gemini(prompt, expect_json=True)
    if not raw:
        return ProviderBriefOutput(
            brief_text="## Provider Brief\n\nUnable to generate provider brief — LLM service unavailable.\n\nPlease review the claim details and contact the patient.",
        )
    try:
        data = json.loads(raw)
        return ProviderBriefOutput(**data)
    except Exception as e:
        logger.error(f"Output Agent: failed to parse provider brief JSON: {e}")
        return ProviderBriefOutput(brief_text=raw)


# ---------------------------------------------------------------------------
# Fallback content (used when Gemini is unavailable)
# ---------------------------------------------------------------------------

def _fallback_appeal_letter(
    patient_name: str,
    patient_address: str,
    ident: dict,
    laws_text: str,
    appeal_address: str,
    deadline: str,
    root_cause: dict,
) -> str:
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    claim_ref = ident.get("claim_reference_number", "Unknown")
    insurer = ident.get("insurance_company_name", "Insurance Company")
    return f"""# Appeal of Insurance Claim Denial

{today}

{patient_name}
{patient_address}

---

**To:** Appeals Department, {insurer}
**Re:** Appeal of Claim Denial — Claim #{claim_ref}
**Deadline:** {deadline}

---

Dear Appeals Department,

I am writing to formally appeal the denial of the above-referenced claim. I believe this denial was issued in error and request a full and fair review pursuant to {laws_text}.

The root cause of this denial appears to be: **{root_cause.get('category', 'Unknown')}**. {root_cause.get('reasoning', '')}

I request that you reconsider this claim and provide coverage for the denied services. Please confirm receipt of this appeal and provide a timeline for your decision.

Sincerely,

{patient_name}
"""
