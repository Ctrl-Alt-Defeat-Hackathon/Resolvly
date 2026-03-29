"""
Output Generation Agent

Takes the ClaimObject + analysis results and generates all user-facing content
using Groq (preferred) or Google Gemini.

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

from pydantic import BaseModel, ConfigDict

from tools.llm_client import complete_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class ActionStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int = 1
    action: str = ""
    detail: str = ""
    why: str = ""
    responsible_party: str = "patient"
    expected_timeline: str = ""
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
    model_config = ConfigDict(extra="ignore")

    summary_text: str = ""
    reading_level: str = "8th grade"
    key_points: list[str] = []


def _normalize_summary_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Map common LLM JSON variants (camelCase, alternate key names) so summary_text is never
    dropped when the model deviates from the requested schema.
    """
    summary_keys = (
        "summary_text",
        "summary",
        "plain_english_summary",
        "denial_summary",
        "explanation",
        "patient_summary",
        "text",
        "content",
        "summaryText",
        "plainEnglishSummary",
    )
    text = ""
    for k in summary_keys:
        v = data.get(k)
        if v is None:
            continue
        if isinstance(v, str) and v.strip():
            text = v.strip()
            break
        if isinstance(v, dict):
            for nk in ("summary_text", "text", "body", "content"):
                if v.get(nk) and str(v[nk]).strip():
                    text = str(v[nk]).strip()
                    break
            if text:
                break

    kp_raw = data.get("key_points") or data.get("keyPoints") or data.get("bullets") or []
    if isinstance(kp_raw, str) and kp_raw.strip():
        key_points = [kp_raw.strip()]
    elif isinstance(kp_raw, list):
        key_points = [str(x).strip() for x in kp_raw if x is not None and str(x).strip()]
    else:
        key_points = []

    rl = data.get("reading_level") or data.get("readingLevel") or "8th grade"
    if not isinstance(rl, str):
        rl = "8th grade"

    return {"summary_text": text, "reading_level": rl, "key_points": key_points[:12]}


class ProviderBriefOutput(BaseModel):
    brief_text: str = ""
    format: str = "markdown"
    pdf_ready: bool = True


# ---------------------------------------------------------------------------
# Context + LLM (via tools.llm_client)
# ---------------------------------------------------------------------------

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

Return a single JSON object with exactly these keys (use snake_case):
- "summary_text": string, 2-3 short paragraphs plain English
- "reading_level": string, e.g. "8th grade"
- "key_points": array of exactly 3 short strings

Example shape:
{{
  "summary_text": "...",
  "reading_level": "8th grade",
  "key_points": ["...", "...", "..."]
}}
"""
    raw = await complete_llm(prompt, expect_json=True)
    if not raw:
        return SummaryOutput(
            summary_text="Unable to generate summary — LLM service unavailable.",
            key_points=["Check denial reason codes", "Contact your insurer", "Consider filing an appeal"],
        )
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM summary JSON must be an object")
        norm = _normalize_summary_payload(data)
        if not norm["summary_text"]:
            logger.warning("Output Agent: summary JSON parsed but summary_text empty after normalization; using raw fallback")
            return SummaryOutput(summary_text=raw.strip()[:12000])
        return SummaryOutput(**norm)
    except json.JSONDecodeError as e:
        logger.error(f"Output Agent: invalid summary JSON: {e}")
        # Show best-effort text so the UI is not blank
        cleaned = raw.strip()
        if cleaned:
            return SummaryOutput(summary_text=cleaned[:12000])
        return SummaryOutput(
            summary_text="Could not parse summary from the model. Try again or check server logs.",
            key_points=[],
        )
    except Exception as e:
        logger.error(f"Output Agent: failed to build summary: {e}")
        return SummaryOutput(summary_text=raw.strip()[:12000] if raw.strip() else "")


_VALID_RESPONSIBLE = frozenset({"patient", "provider", "insurer"})


def _normalize_action_step_dict(raw: dict[str, Any], index: int) -> dict[str, Any]:
    """Map camelCase / alternate keys so Groq and other models can deviate from the schema."""
    n = raw.get("number")
    if n is None:
        n = raw.get("step") or raw.get("stepNumber")
    try:
        num = int(float(n)) if n is not None else index + 1
    except (TypeError, ValueError):
        num = index + 1

    action = (
        raw.get("action")
        or raw.get("title")
        or raw.get("name")
        or raw.get("step_title")
        or raw.get("summary")
    )
    action_s = str(action).strip() if action is not None else ""

    det = raw.get("detail") or raw.get("description") or raw.get("instructions") or raw.get("body")
    detail_s = str(det).strip() if det is not None else ""

    why = raw.get("why") or raw.get("rationale") or raw.get("reason") or raw.get("because")
    why_s = str(why).strip() if why is not None else ""

    rp = str(raw.get("responsible_party") or raw.get("responsibleParty") or raw.get("owner") or "patient").strip().lower()
    if rp not in _VALID_RESPONSIBLE:
        rp = "patient"

    et = raw.get("expected_timeline") or raw.get("expectedTimeline") or raw.get("timeline")
    et_s = str(et).strip() if et is not None else ""

    contact_raw = raw.get("contact")
    contact: dict[str, str] = {}
    if isinstance(contact_raw, dict):
        for k, v in contact_raw.items():
            if v is None:
                continue
            contact[str(k)] = str(v).strip()

    if not action_s:
        action_s = f"Step {num}"
    if not detail_s:
        detail_s = why_s or "Use your denial letter and insurer contact information to complete this step."
    if not why_s:
        why_s = "This step keeps your appeal organized and protects your rights."

    return {
        "number": num,
        "action": action_s[:500],
        "detail": detail_s[:2000],
        "why": why_s[:2000],
        "responsible_party": rp,
        "expected_timeline": et_s or "1–5 business days",
        "contact": contact,
    }


def _action_step_from_loose_item(item: Any, index: int) -> ActionStep | None:
    if isinstance(item, str):
        t = item.strip()
        if not t:
            return None
        return ActionStep(
            number=index + 1,
            action=t[:500],
            detail="Follow your plan documents and insurer instructions for this step.",
            why="Consistent follow-through improves your chance of a successful appeal.",
            responsible_party="patient",
            expected_timeline="1–5 business days",
            contact={},
        )
    if isinstance(item, dict):
        return ActionStep(**_normalize_action_step_dict(item, index))
    return None


def _action_steps_from_parsed_json(data: Any) -> list[ActionStep]:
    if isinstance(data, list):
        items: list[Any] = data
    elif isinstance(data, dict):
        items = []
        for key in ("steps", "action_steps", "checklist", "actions", "actionItems"):
            v = data.get(key)
            if isinstance(v, list) and v:
                items = v
                break
    else:
        return []

    out: list[ActionStep] = []
    for i, item in enumerate(items):
        step = _action_step_from_loose_item(item, i)
        if step:
            out.append(step)
    return out


def _fallback_action_checklist(claim_dict: dict[str, Any], analysis_dict: dict[str, Any]) -> ActionChecklist:
    """Deterministic steps when the LLM is unavailable or returns unusable JSON."""
    ident = claim_dict.get("identification", {}) or {}
    denial = claim_dict.get("denial_reason", {}) or {}
    appeal = claim_dict.get("appeal_rights", {}) or {}
    deadlines = analysis_dict.get("deadlines", {}) or {}
    root = analysis_dict.get("root_cause", {}) or {}
    internal = deadlines.get("internal_appeal", {}) or {}
    ref = str(ident.get("claim_reference_number") or "").strip() or "your claim"
    narrative = str(denial.get("denial_reason_narrative") or "")[:280]
    rc_cat = str(root.get("category") or "this denial")
    phone = str(appeal.get("insurer_appeals_phone") or "").strip()
    addr = str(appeal.get("insurer_appeals_address") or "").strip()
    deadline_str = str(internal.get("date") or "the date listed on your denial letter")
    days = internal.get("days_remaining")

    contact_insurer: dict[str, str] = {}
    if phone:
        contact_insurer["phone"] = phone
    if addr:
        contact_insurer["address"] = addr

    d_tail = ""
    if isinstance(days, (int, float)):
        d_tail = f" (about {int(days)} days remaining)."
    else:
        d_tail = "."

    steps = [
        ActionStep(
            number=1,
            action="Confirm denial details and internal appeal deadline",
            detail=f"For claim {ref}, verify the denial reason and any codes listed. Your internal appeal deadline is {deadline_str}{d_tail}",
            why="Missing a deadline can end your right to appeal this decision.",
            responsible_party="patient",
            expected_timeline="Same day",
            contact={},
        ),
        ActionStep(
            number=2,
            action="Gather supporting records",
            detail="Collect visit notes, labs, imaging reports, or prior authorization letters that relate to the denied service."
            + (f" Denial summary: {narrative}" if narrative else ""),
            why="Insurers often reverse denials when documentation shows medical necessity or billing support.",
            responsible_party="patient",
            expected_timeline="2–7 business days",
            contact={},
        ),
        ActionStep(
            number=3,
            action="Address the main issue",
            detail=f"Focus on what the analysis flagged: {rc_cat}. Work with your provider if clinical or billing corrections are needed.",
            why="Appeals that directly address the insurer's stated reason are more likely to succeed.",
            responsible_party="patient",
            expected_timeline="3–10 business days",
            contact={},
        ),
        ActionStep(
            number=4,
            action="Submit a formal internal appeal",
            detail="Send a written appeal to the insurer's appeals address with your reference number, a clear request for reconsideration, and copies of supporting documents."
            + (f" Insurer phone on file: {phone}." if phone else ""),
            why="An internal appeal is usually required before external review or other remedies.",
            responsible_party="patient",
            expected_timeline="1–3 business days to prepare",
            contact=contact_insurer,
        ),
        ActionStep(
            number=5,
            action="Track the decision and next steps",
            detail="Keep a copy of what you sent and follow up if you do not receive a decision within the timeframe your plan describes.",
            why="A documented paper trail helps if you need to escalate.",
            responsible_party="patient",
            expected_timeline="Ongoing",
            contact={},
        ),
    ]
    return ActionChecklist(steps=steps, total_steps=len(steps))


async def generate_action_checklist(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> ActionChecklist:
    """Generate numbered action steps with why-expanders."""
    context = _claim_context_summary(claim_dict, analysis_dict)
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

Return a JSON object with this exact structure (use snake_case keys):
{{
  "steps": [
    {{
      "number": 1,
      "action": "<short action title, imperative, max 10 words>",
      "detail": "<specific instructions for this step, 1-2 sentences>",
      "why": "<explanation of why this step matters, 1-2 sentences>",
      "responsible_party": "patient",
      "expected_timeline": "<e.g., '1-3 business days'>",
      "contact": {{
        "name": "<contact name if known, else empty>",
        "phone": "<phone if known, else empty>",
        "address": "<address if known, else empty>"
      }}
    }}
  ]
}}

Each responsible_party must be exactly one of: "patient", "provider", "insurer".

DOI Contact info: {json.dumps(doi_contact)}
Internal appeal deadline: {deadlines.get('internal_appeal', {}).get('date', 'Unknown')} ({deadlines.get('internal_appeal', {}).get('days_remaining', '?')} days remaining)
"""
    raw = await complete_llm(prompt, expect_json=True)
    parsed_steps: list[ActionStep] = []
    if raw:
        try:
            data = json.loads(raw)
            parsed_steps = _action_steps_from_parsed_json(data)
        except json.JSONDecodeError as e:
            logger.warning(f"Output Agent: checklist JSON invalid: {e}")
        except Exception as e:
            logger.warning(f"Output Agent: checklist parse failed: {e}")

    fixed: list[ActionStep] = []
    for i, s in enumerate(parsed_steps):
        fixed.append(s.model_copy(update={"number": i + 1}))

    if not fixed:
        logger.info("Output Agent: using context-based fallback action checklist")
        return _fallback_action_checklist(claim_dict, analysis_dict)

    return ActionChecklist(steps=fixed, total_steps=len(fixed))


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
    raw = await complete_llm(prompt, expect_json=True)
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
    raw = await complete_llm(prompt, expect_json=True)
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
# Week 6: Denial letter completeness report
# ---------------------------------------------------------------------------

# Legal citation for each required completeness field
_FIELD_CITATIONS: dict[str, dict[str, str]] = {
    "Specific denial reason or narrative": {
        "required_by": "ACA § 2719(b)(2)(A) / ERISA § 503(1)",
        "why_it_matters": (
            "You cannot effectively appeal a denial without knowing the specific reason. "
            "The insurer is legally required to state the exact basis for denial."
        ),
        "action_if_missing": (
            "Request a written explanation of the specific denial reason in writing. "
            "Under ERISA § 503 and ACA § 2719, the insurer must provide this upon request."
        ),
    },
    "Reference to specific plan provision cited": {
        "required_by": "ERISA § 503(1) / ACA § 2719 / 29 CFR § 2560.503-1(g)(1)(i)",
        "why_it_matters": (
            "The insurer must cite the exact plan provision, policy section, or exclusion "
            "that supports the denial. Vague references are legally insufficient."
        ),
        "action_if_missing": (
            "Request the specific plan provision or policy section in writing. "
            "A denial without a cited provision is procedurally deficient and strengthens your appeal."
        ),
    },
    "Clinical criteria or scientific evidence cited": {
        "required_by": "ACA § 2719 / URAC / 29 CFR § 2560.503-1(g)(1)(v)",
        "why_it_matters": (
            "For medical necessity denials, the insurer must disclose what clinical criteria "
            "(e.g., InterQual, MCG) were used to evaluate the claim."
        ),
        "action_if_missing": (
            "Request the specific clinical criteria used to deny the claim. "
            "You have the right to see this information to prepare a clinical rebuttal."
        ),
    },
    "Claim adjustment reason code(s) provided": {
        "required_by": "CMS Claims Processing Manual / ACA § 2719 / HIPAA X12 ERA standards",
        "why_it_matters": (
            "CARC codes identify the exact reason the claim was adjusted or denied. "
            "Without them, it is impossible to target the appeal correctly."
        ),
        "action_if_missing": (
            "Request the Explanation of Benefits (EOB) or remittance advice, which must include "
            "CARC codes under HIPAA electronic transaction standards."
        ),
    },
    "Internal appeal process described": {
        "required_by": "ACA § 2719(b)(1) / ERISA § 503(2) / 29 CFR § 2560.503-1(g)(1)(iv)",
        "why_it_matters": (
            "The insurer must inform you of your right to an internal appeal and the timeline "
            "to file one. Missing this information violates mandatory notice requirements."
        ),
        "action_if_missing": (
            "Call your insurer's member services line and request the internal appeal process "
            "and deadline in writing. Federal law requires them to provide this."
        ),
    },
    "External review rights mentioned": {
        "required_by": "ACA § 2719A / 45 CFR § 147.138 / ERISA § 503",
        "why_it_matters": (
            "For most plans, you have the right to an independent external review after "
            "exhausting internal appeals. The denial letter must inform you of this right."
        ),
        "action_if_missing": (
            "Research external review rights for your plan type and state. "
            "For ACA plans, external review is available in all states. For ERISA plans, "
            "ask your plan administrator or contact DOL EBSA."
        ),
    },
    "Expedited review availability noted": {
        "required_by": "ACA § 2719 / 29 CFR § 2560.503-1(f)(2)(i) (for urgent care)",
        "why_it_matters": (
            "If you are currently receiving treatment or the standard timeline would seriously "
            "jeopardize your health, you may qualify for a 72-hour expedited appeal."
        ),
        "action_if_missing": (
            "If your situation is urgent (ongoing treatment, serious health risk), "
            "explicitly request expedited review from your insurer in writing."
        ),
    },
    "Insurer appeals contact information provided": {
        "required_by": "ACA § 2719 / ERISA § 503(2) / 29 CFR § 2560.503-1(g)(1)(iv)",
        "why_it_matters": (
            "You must know who to contact to file your appeal. Missing contact information "
            "makes it practically impossible to exercise your appeal rights."
        ),
        "action_if_missing": (
            "Call the member services number on your insurance card and request the "
            "appeals department mailing address, phone, and fax in writing."
        ),
    },
    "State insurance commissioner reference included": {
        "required_by": "ACA § 2719 / state insurance regulations",
        "why_it_matters": (
            "For state-regulated plans, the denial letter should mention your right to "
            "contact the state Department of Insurance. This is a required consumer notice."
        ),
        "action_if_missing": (
            "Contact your state Department of Insurance directly to file a complaint about "
            "the missing notice and to request external review assistance."
        ),
    },
    "ERISA § 502(a) civil action rights mentioned": {
        "required_by": "ERISA § 503 / 29 CFR § 2560.503-1(g)(1)(iv)",
        "why_it_matters": (
            "For ERISA plans, after exhausting internal appeals you have the right to file "
            "a civil action under ERISA § 502(a). The plan must inform you of this right."
        ),
        "action_if_missing": (
            "Contact the U.S. Department of Labor EBSA (1-866-444-3272) to report the "
            "missing notice and understand your civil action rights."
        ),
    },
}


class CompletenessReportItem(BaseModel):
    field: str
    present: bool
    required_by: str
    why_it_matters: str
    action_if_missing: str


class CompletenessReport(BaseModel):
    score: float
    score_percentage: str
    regulation_standard: str
    deficient: bool
    escalation_available: bool
    escalation_reason: str
    checklist: list[CompletenessReportItem]
    present_count: int
    missing_count: int
    summary: str


def generate_completeness_report(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> CompletenessReport:
    """
    Format the denial_completeness analysis data into a field-by-field
    actionable checklist with legal citations.
    Deterministic — no LLM call required.
    """
    completeness = analysis_dict.get("denial_completeness", {})
    present_fields: list[str] = completeness.get("present_fields", [])
    missing_fields: list[str] = completeness.get("missing_fields", [])
    score: float = completeness.get("score", 0.0)
    deficient: bool = completeness.get("deficient", False)
    escalation_available: bool = completeness.get("escalation_available", False)
    escalation_reason: str = completeness.get("escalation_reason", "")
    regulation_standard: str = completeness.get("regulation_standard", "ACA § 2719")

    all_fields = present_fields + missing_fields
    checklist = []
    for field in all_fields:
        citation = _FIELD_CITATIONS.get(field, {})
        checklist.append(CompletenessReportItem(
            field=field,
            present=field in present_fields,
            required_by=citation.get("required_by", regulation_standard),
            why_it_matters=citation.get("why_it_matters", "Required by federal or state law."),
            action_if_missing=citation.get(
                "action_if_missing",
                "Request this information from your insurer in writing.",
            ),
        ))

    # Sort: missing first, then present
    checklist.sort(key=lambda x: (x.present, x.field))

    pct = int(round(score * 100))
    if deficient:
        summary = (
            f"Your denial letter meets only {pct}% of legally required notice elements "
            f"({len(present_fields)} of {len(all_fields)} present, {len(missing_fields)} missing). "
            f"A denial letter this incomplete may be challenged on procedural grounds."
        )
    else:
        summary = (
            f"Your denial letter meets {pct}% of legally required notice elements "
            f"({len(present_fields)} of {len(all_fields)} present). "
            f"While substantively complete, review any missing items before filing your appeal."
        )

    return CompletenessReport(
        score=score,
        score_percentage=f"{pct}%",
        regulation_standard=regulation_standard,
        deficient=deficient,
        escalation_available=escalation_available,
        escalation_reason=escalation_reason,
        checklist=checklist,
        present_count=len(present_fields),
        missing_count=len(missing_fields),
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Week 6: ERISA vs. IDOI routing card
# ---------------------------------------------------------------------------

class ContactBlock(BaseModel):
    name: str = ""
    phone: str = ""
    address: str = ""
    website: str = ""
    complaint_url: str = ""
    external_review_url: str = ""


class RoutingRoute(BaseModel):
    route_name: str
    legal_basis: str
    contact: ContactBlock = ContactBlock()
    process_steps: list[str] = []
    notes: str = ""


class RoutingCardOutput(BaseModel):
    routing: str                    # "erisa_federal" | "state_doi" | "medicaid_state"
    routing_reason: str
    primary_route: RoutingRoute
    secondary_route: RoutingRoute | None = None
    complaint_links: list[dict[str, str]] = []
    formatted_card: str = ""        # LLM-generated markdown card


async def generate_routing_card(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> RoutingCardOutput:
    """
    Generate ERISA vs. IDOI regulatory routing card with full contact blocks.
    Uses LLM to format a clean, patient-readable card.
    """
    enrichment = analysis_dict.get("enrichment", {}) or {}
    state_rules = enrichment.get("state_rules", {}) or {}
    regulations = enrichment.get("regulations", {}) or {}

    routing: str = state_rules.get("regulatory_routing", "state_doi")
    routing_reason: str = state_rules.get("routing_reason", "")
    doi_contact: dict = state_rules.get("doi_contact", {}) or {}
    appeal_rules: list = state_rules.get("appeal_rules", [])
    external_review_url: str = state_rules.get("external_review_url", "")
    state: str = state_rules.get("state", claim_dict.get("identification", {}).get("plan_jurisdiction", "Unknown"))

    regulation_type: str = regulations.get("regulation_type", "unknown")
    applicable_laws: list = regulations.get("applicable_laws", [])
    appeal_process: list = regulations.get("appeal_process", [])
    internal_deadline_days: int = regulations.get("internal_appeal_deadline_days", 180)

    # Build structured route objects
    if routing == "erisa_federal":
        primary = RoutingRoute(
            route_name="U.S. Department of Labor (DOL) — EBSA",
            legal_basis="ERISA § 503 / 29 CFR § 2560.503-1 — Self-funded employer plans are governed by federal law, not state insurance regulations.",
            contact=ContactBlock(
                name="Employee Benefits Security Administration (EBSA)",
                phone="1-866-444-3272",
                website="https://www.dol.gov/agencies/ebsa",
                complaint_url="https://www.askebsa.dol.gov/",
            ),
            process_steps=appeal_process or [
                "File internal appeal with plan administrator within 180 days of denial notice",
                "Plan must respond within 60 days (post-service) or 15 days (pre-service)",
                "If internal appeal denied, consider ERISA § 502(a) civil action in federal court",
                "Contact DOL EBSA for guidance on plan violations",
            ],
            notes=(
                "ERISA pre-empts state insurance laws for self-funded plans. "
                "The state Department of Insurance cannot order the plan to pay claims. "
                "However, if the plan is fully insured (an insurance company underwrites it), "
                "state DOI rules apply — verify with your HR department."
            ),
        )
        secondary = RoutingRoute(
            route_name=f"{state} Department of Insurance (limited jurisdiction)",
            legal_basis="State DOI does not regulate ERISA self-funded plans but can provide guidance and investigate insurance company practices.",
            contact=ContactBlock(
                name=doi_contact.get("name", f"{state} Department of Insurance"),
                phone=doi_contact.get("phone", ""),
                address=doi_contact.get("address", ""),
                website=doi_contact.get("website", ""),
                complaint_url=doi_contact.get("complaint_url", ""),
            ),
            process_steps=[
                "Contact state DOI only if plan is fully insured (not self-funded)",
                "State DOI can investigate insurance company practices even if plan is ERISA",
                "File a complaint if insurer fails to follow proper claims procedures",
            ],
            notes="Consult HR or your plan documents to confirm whether your plan is self-funded (ERISA) or fully insured (state-regulated).",
        )
    elif routing == "medicaid_state":
        primary = RoutingRoute(
            route_name=f"{state} Medicaid Agency — Fair Hearing",
            legal_basis="42 CFR § 431.220 — Medicaid beneficiaries have the right to a fair hearing for any adverse action.",
            contact=ContactBlock(
                name=doi_contact.get("name", f"{state} Medicaid Agency"),
                phone=doi_contact.get("phone", ""),
                website=doi_contact.get("website", ""),
                complaint_url=doi_contact.get("complaint_url", ""),
            ),
            process_steps=appeal_process or [
                "Request a fair hearing within 90 days of the denial notice",
                "Submit your hearing request to your state Medicaid agency in writing",
                "If you request a hearing within 10 days, benefits may continue pending the hearing",
                "The hearing must be held within 90 days of your request",
                "You may bring a representative or attorney",
            ],
            notes="Medicaid fair hearings are free. You can request a hearing in writing or by phone. Legal aid organizations may be able to assist you at no cost.",
        )
        secondary = None
    else:
        # state_doi — ACA/marketplace/fully insured
        primary = RoutingRoute(
            route_name=f"{state} Department of Insurance",
            legal_basis=f"ACA § 2719 / 45 CFR § 147.136 — State-regulated plans must follow ACA internal and external review requirements.",
            contact=ContactBlock(
                name=doi_contact.get("name", f"{state} Department of Insurance"),
                phone=doi_contact.get("phone", ""),
                address=doi_contact.get("address", ""),
                website=doi_contact.get("website", ""),
                complaint_url=doi_contact.get("complaint_url", ""),
                external_review_url=external_review_url or doi_contact.get("external_review_url", ""),
            ),
            process_steps=appeal_rules or appeal_process or [
                f"File internal appeal with insurer within {internal_deadline_days} days of denial",
                "Insurer must decide within 60 days (post-service) or 30 days (pre-service)",
                "If internal appeal is denied, request independent external review",
                f"File complaint with {state} Department of Insurance if insurer violates procedures",
            ],
            notes="External review by an Independent Review Organization (IRO) is binding on the insurer. There is typically no cost to you for external review.",
        )
        secondary = RoutingRoute(
            route_name="U.S. Department of Health and Human Services (HHS) / CMS",
            legal_basis="ACA § 2719 — Federal oversight of ACA marketplace and qualified health plans.",
            contact=ContactBlock(
                name="CMS / HealthCare.gov",
                phone="1-800-318-2596",
                website="https://www.healthcare.gov",
                complaint_url="https://www.healthcare.gov/marketplace-appeals/",
            ),
            process_steps=[
                "File a marketplace appeal if coverage was denied through Healthcare.gov",
                "Contact CMS if state DOI is unresponsive or the insurer violates federal law",
            ],
            notes="For employer-sponsored plans that are fully insured, the state DOI is the primary regulator. CMS handles marketplace (exchange) plan disputes.",
        )

    complaint_links = [
        {"name": "DOL EBSA Online Assistance", "url": "https://www.askebsa.dol.gov/"},
        {"name": "CMS Appeals", "url": "https://www.healthcare.gov/marketplace-appeals/"},
    ]
    if doi_contact.get("complaint_url"):
        complaint_links.insert(0, {
            "name": f"{state} DOI Complaint Portal",
            "url": doi_contact["complaint_url"],
        })
    if external_review_url:
        complaint_links.append({"name": "External Review Request", "url": external_review_url})

    # Generate LLM-formatted markdown card
    formatted_card = await _generate_routing_card_markdown(
        routing=routing,
        routing_reason=routing_reason,
        primary=primary,
        secondary=secondary,
        state=state,
        regulation_type=regulation_type,
    )

    return RoutingCardOutput(
        routing=routing,
        routing_reason=routing_reason,
        primary_route=primary,
        secondary_route=secondary,
        complaint_links=complaint_links,
        formatted_card=formatted_card,
    )


async def _generate_routing_card_markdown(
    routing: str,
    routing_reason: str,
    primary: RoutingRoute,
    secondary: RoutingRoute | None,
    state: str,
    regulation_type: str,
) -> str:
    """Generate a clean patient-readable markdown routing card using the configured LLM."""
    route_label = {
        "erisa_federal": "Federal ERISA (DOL)",
        "state_doi": f"{state} Department of Insurance",
        "medicaid_state": f"{state} Medicaid",
    }.get(routing, routing)

    secondary_block = ""
    if secondary:
        secondary_block = f"""
### Secondary Route: {secondary.route_name}
**Legal Basis:** {secondary.legal_basis}

**Contact:**
- Name: {secondary.contact.name or 'N/A'}
- Phone: {secondary.contact.phone or 'N/A'}
- Website: {secondary.contact.website or 'N/A'}

**Notes:** {secondary.notes}
"""

    prompt = f"""You are an insurance patient advocate. Generate a clean, easy-to-read regulatory routing card for a patient in Markdown format.

ROUTING DECISION: {route_label}
ROUTING REASON: {routing_reason}
REGULATION TYPE: {regulation_type}
STATE: {state}

PRIMARY CONTACT:
- Organization: {primary.route_name}
- Legal Basis: {primary.legal_basis}
- Phone: {primary.contact.phone or 'Call insurer on your insurance card'}
- Website: {primary.contact.website or 'N/A'}
- Complaint URL: {primary.contact.complaint_url or 'N/A'}
- External Review URL: {primary.contact.external_review_url or 'N/A'}

PROCESS STEPS:
{chr(10).join(f'- {s}' for s in primary.process_steps)}

PRIMARY NOTES: {primary.notes}
{secondary_block}

Generate a routing card in this exact Markdown structure (fill in the details):

## 📋 Your Regulatory Routing Card

**Regulation Type:** [plain-English description of plan type]
**Who Oversees Your Plan:** [primary regulator name]
**Why:** [1-2 sentence plain-English explanation of why this routing applies]

---

### 🏛️ Primary Appeal Route: [route name]

**Legal Authority:** [cite the law]

**Contact:**
| | |
|---|---|
| **Phone** | [phone] |
| **Website** | [website] |
| **File a Complaint** | [complaint URL] |

**Your Appeal Process:**
1. [step 1]
2. [step 2]
...

**Important Note:** [plain-English explanation of any gotchas or key facts]

[if secondary route exists, include a secondary section]

---

### ℹ️ Key Rights Summary
- [bullet: right 1]
- [bullet: right 2]
- [bullet: right 3]

*This routing card is based on your extracted plan information. Verify your plan type with your employer HR department or insurer if uncertain.*

Keep it concise, clear, and actionable. Use plain English — no jargon.
"""
    raw = await complete_llm(prompt, expect_json=False)
    if not raw:
        # Return a deterministic fallback card
        lines = [
            f"## Your Regulatory Routing Card",
            f"",
            f"**Your Plan Is Regulated By:** {primary.route_name}",
            f"",
            f"**Why:** {routing_reason}",
            f"",
            f"### Contact",
            f"- **Phone:** {primary.contact.phone or 'See your insurance card'}",
            f"- **Website:** {primary.contact.website or 'N/A'}",
            f"- **Complaint Portal:** {primary.contact.complaint_url or 'N/A'}",
            f"",
            f"### Your Appeal Steps",
        ]
        for i, step in enumerate(primary.process_steps, 1):
            lines.append(f"{i}. {step}")
        if primary.notes:
            lines += ["", f"**Note:** {primary.notes}"]
        return "\n".join(lines)
    return raw


# ---------------------------------------------------------------------------
# Week 6: Assumptions panel
# ---------------------------------------------------------------------------

_ASSUMPTION_GUIDANCE: dict[str, dict[str, str]] = {
    "Plan type was not extracted": {
        "how_to_verify": "Check your insurance card, Summary Plan Description (SPD), or call your HR department.",
        "if_incorrect": "The regulation type (ERISA vs. state) and deadlines may be incorrect. Re-run the analysis after providing plan type via the wizard.",
    },
    "Regulation type is unknown": {
        "how_to_verify": "Ask your HR department whether the plan is self-funded (ERISA) or fully insured. Check your SPD for 'self-insured' or 'self-funded' language.",
        "if_incorrect": "Deadlines and appeal routes will change significantly between ERISA (federal) and state-regulated plans.",
    },
    "Date of denial not found": {
        "how_to_verify": "Check the denial letter, EOB, or remittance advice for the date the denial was issued.",
        "if_incorrect": "All appeal deadlines are calculated from the denial date. Incorrect date = incorrect deadlines.",
    },
    "Root cause classification confidence": {
        "how_to_verify": "Review the CARC codes and denial reason text yourself to confirm the root cause.",
        "if_incorrect": "The action steps and appeal strategy will be targeted at the wrong problem.",
    },
    "treating physician can provide a letter of medical necessity": {
        "how_to_verify": "Contact your treating physician's office and confirm they are willing to write a letter of medical necessity.",
        "if_incorrect": "The medical necessity appeal strategy will not be viable without physician support.",
    },
    "provider is willing to submit retroactive prior authorization": {
        "how_to_verify": "Contact your provider's billing department and ask if they can submit a retroactive prior authorization request.",
        "if_incorrect": "The prior authorization appeal strategy requires provider action. If provider is unwilling, you may need to appeal on a different basis.",
    },
    "ACA-compliant (not grandfathered": {
        "how_to_verify": "Check your plan documents for 'grandfathered' or 'grandmothered' status, or contact your insurer.",
        "if_incorrect": "Grandfathered plans are exempt from some ACA requirements, including external review.",
    },
}


def _get_assumption_guidance(assumption_text: str) -> tuple[str, str]:
    """Find the best matching guidance for an assumption."""
    for key, guidance in _ASSUMPTION_GUIDANCE.items():
        if key.lower() in assumption_text.lower():
            return guidance["how_to_verify"], guidance["if_incorrect"]
    return (
        "Verify this assumption by reviewing your plan documents or contacting your insurer.",
        "If this assumption is wrong, some recommendations may not apply to your situation.",
    )


class AssumptionItem(BaseModel):
    assumption: str
    confidence: float
    confidence_percentage: str
    impact: str
    how_to_verify: str
    if_incorrect: str


class AssumptionsPanelOutput(BaseModel):
    assumptions: list[AssumptionItem]
    high_impact_count: int
    medium_impact_count: int
    overall_confidence: float
    overall_confidence_percentage: str
    reliability_note: str


def generate_assumptions_panel(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> AssumptionsPanelOutput:
    """
    Format the analysis assumptions into a structured panel with
    verification guidance for each. Deterministic — no LLM required.
    """
    raw_assumptions: list[dict] = analysis_dict.get("assumptions", [])
    items: list[AssumptionItem] = []

    for a in raw_assumptions:
        assumption_text: str = a.get("assumption", "")
        confidence: float = float(a.get("confidence", 0.5))
        impact: str = a.get("impact", "medium")
        how_to_verify, if_incorrect = _get_assumption_guidance(assumption_text)

        items.append(AssumptionItem(
            assumption=assumption_text,
            confidence=confidence,
            confidence_percentage=f"{int(round(confidence * 100))}%",
            impact=impact,
            how_to_verify=how_to_verify,
            if_incorrect=if_incorrect,
        ))

    # Sort: high impact first, then by confidence ascending (least certain first)
    items.sort(key=lambda x: (x.impact != "high", x.confidence))

    high_count = sum(1 for i in items if i.impact == "high")
    medium_count = sum(1 for i in items if i.impact == "medium")

    overall_confidence = (
        sum(i.confidence for i in items) / len(items) if items else 1.0
    )

    if overall_confidence >= 0.80:
        reliability_note = "The analysis is based on high-confidence assumptions. Results are reliable."
    elif overall_confidence >= 0.65:
        reliability_note = (
            "Some assumptions have moderate confidence. Review the items below and verify "
            "any that are marked as high-impact before taking action."
        )
    else:
        reliability_note = (
            "Several key assumptions could not be verified from the documents provided. "
            "Manual review is recommended before relying on the recommendations."
        )

    return AssumptionsPanelOutput(
        assumptions=items,
        high_impact_count=high_count,
        medium_impact_count=medium_count,
        overall_confidence=round(overall_confidence, 2),
        overall_confidence_percentage=f"{int(round(overall_confidence * 100))}%",
        reliability_note=reliability_note,
    )


# ---------------------------------------------------------------------------
# Week 6: Probability details
# ---------------------------------------------------------------------------

_BASE_RATES_INFO: dict[str, dict[str, Any]] = {
    "prior_authorization": {
        "base_rate": 0.78,
        "source": "CMS appeals data",
        "headline": "78% of prior authorization denials are overturned on appeal",
        "key_action": "Ask your provider to submit a retroactive prior authorization with full clinical documentation.",
    },
    "coding_billing_error": {
        "base_rate": 0.90,
        "source": "MGMA claims data",
        "headline": "90%+ of coding/billing errors are corrected when a corrected claim is submitted",
        "key_action": "Ask your provider's billing department to review and resubmit a corrected claim.",
    },
    "medical_necessity": {
        "base_rate": 0.55,
        "source": "KFF Health Insurance Marketplace Survey",
        "headline": "55% of medical necessity denials are overturned with physician documentation",
        "key_action": "Ask your treating physician to write a detailed letter of medical necessity.",
    },
    "procedural_administrative": {
        "base_rate": 0.70,
        "source": "Industry claims processing averages",
        "headline": "70% of procedural denials are resolved by providing the missing information",
        "key_action": "Identify and provide the specific missing information or documentation.",
    },
    "eligibility_enrollment": {
        "base_rate": 0.40,
        "source": "Published claims appeal statistics",
        "headline": "40% overturn rate — eligibility denials require proving coverage was active",
        "key_action": "Obtain proof of coverage on the date of service from your employer or insurer.",
    },
    "network_coverage": {
        "base_rate": 0.45,
        "source": "No Surprises Act implementation data",
        "headline": "45% overturn rate — varies significantly by circumstances",
        "key_action": "Check for No Surprises Act protections (emergency care, air ambulance, surprise billing).",
    },
}

_FACTOR_EXPLANATIONS: dict[str, str] = {
    "+Provider error": "When the provider made an error, they can usually correct it — this significantly raises your odds.",
    "+Insurer determination": "Insurer-side denials can be challenged with clinical evidence and regulations.",
    "-Patient responsibility": "Denials for patient cost-sharing (deductible, OOP max) are generally not overturnable.",
    "+Denial letter is procedurally deficient": "A legally deficient denial letter is itself grounds for appeal and weakens the insurer's position.",
    "-Denial letter is well-documented": "A thorough denial letter suggests the insurer carefully reviewed the claim.",
    "-No prior appeal filed yet": "First appeals succeed less often than second or third appeals — but you must start here.",
    "+External review by independent IRO": "IRO decisions are binding on the insurer and often favor patients.",
    "~ERISA plan: no external review": "ERISA self-funded plans lack state external review, but DOL EBSA and federal court remain options.",
    "+Expedited review available": "Faster resolution reduces risk of losing access to care.",
    "+Provider can request retroactive": "Retroactive authorization with clinical docs resolves most prior auth denials.",
    "+High denied amount": "High-dollar denials give providers and patients strong motivation to pursue all appeal options.",
    "-Small denied amount": "Weigh the time cost of a full appeal against the amount at stake.",
}


class ProbabilityFactor(BaseModel):
    factor: str
    direction: str          # "positive", "negative", "neutral"
    explanation: str


class ProbabilityDetailsOutput(BaseModel):
    score: float
    percentage: str
    interpretation: str
    base_rate: dict[str, Any]
    reasoning: str
    factors: list[ProbabilityFactor]
    top_recommendation: str
    source: str


def generate_probability_details(
    claim_dict: dict[str, Any],
    analysis_dict: dict[str, Any],
) -> ProbabilityDetailsOutput:
    """
    Format the approval_probability result into a structured breakdown
    with factor explanations and improvement recommendations.
    Deterministic — no LLM required.
    """
    prob = analysis_dict.get("approval_probability", {})
    score: float = float(prob.get("score", 0.5))
    reasoning: str = prob.get("reasoning", "")
    raw_factors: list[str] = prob.get("factors", [])
    source: str = prob.get("source", "Rules engine based on CMS appeals data")

    root_cause_category: str = (
        analysis_dict.get("root_cause", {}).get("category", "procedural_administrative")
    )
    base_info = _BASE_RATES_INFO.get(root_cause_category, {
        "base_rate": 0.50,
        "source": source,
        "headline": "~50% estimated overturn rate",
        "key_action": "File an internal appeal with supporting documentation.",
    })

    # Parse factors and add explanations
    parsed_factors: list[ProbabilityFactor] = []
    for f in raw_factors:
        if f.startswith("+"):
            direction = "positive"
        elif f.startswith("-"):
            direction = "negative"
        else:
            direction = "neutral"

        explanation = f
        for key, expl in _FACTOR_EXPLANATIONS.items():
            if key.lower() in f.lower():
                explanation = expl
                break

        parsed_factors.append(ProbabilityFactor(
            factor=f,
            direction=direction,
            explanation=explanation,
        ))

    # Interpretation label
    if score >= 0.80:
        interpretation = "Excellent — Strong chance of success"
    elif score >= 0.65:
        interpretation = "Good — Worth pursuing with documentation"
    elif score >= 0.50:
        interpretation = "Moderate — Success depends on documentation quality"
    elif score >= 0.35:
        interpretation = "Challenging — Consider consulting an advocate"
    else:
        interpretation = "Difficult — Seek legal or professional assistance"

    return ProbabilityDetailsOutput(
        score=score,
        percentage=f"{int(round(score * 100))}%",
        interpretation=interpretation,
        base_rate={
            "category": root_cause_category,
            "rate": base_info["base_rate"],
            "headline": base_info["headline"],
            "source": base_info["source"],
        },
        reasoning=reasoning,
        factors=parsed_factors,
        top_recommendation=base_info["key_action"],
        source=source,
    )


# ---------------------------------------------------------------------------
# Fallback content (used when LLM is unavailable)
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
    insurer = "Insurance Company"
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
