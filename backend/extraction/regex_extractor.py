"""
Pass 1 — Deterministic Regex Extraction.

Extracts all structured entities (codes, dates, amounts, IDs) from raw text
without any LLM calls. Fast, free, and deterministic.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from extraction.schema import (
    AppealRightsEntities,
    ClaimIdentification,
    DenialReasonEntities,
    FinancialEntities,
    PatientProviderEntities,
    ServiceBillingEntities,
)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, str] = {
    # Billing codes
    "icd10": r"\b([A-Z][0-9]{2}\.?[0-9A-Z]{0,4})\b",
    "cpt": r"\b([0-9]{4}[0-9A-Z]|[0-9]{5})\b",                          # 5-char CPT
    "hcpcs": r"\b([A-Z][0-9]{4})\b",
    "modifier": r"\b([A-Z]{2}|[0-9]{2}|[A-Z][0-9]|[0-9][A-Z])\b",      # 2-char modifiers

    # Claim & plan identifiers
    "claim_number": r"(?:claim\s*(?:reference\s*)?(?:#|no\.?|number)[:\s]*)([\w\-]{6,20})",
    "member_id": r"(?:member\s*(?:id|#|no\.?)[:\s]*)([\w\-]{6,20})",
    "group_number": r"(?:group\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,15})",
    "plan_number": r"(?:policy\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,20})",
    "npi": r"\b([0-9]{10})\b",                                            # NPI is exactly 10 digits
    "prior_auth": r"(?:auth(?:orization)?\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,20})",

    # Denial codes
    # CARC codes: explicit prefix ("CARC: 50", "adjustment reason code 50")
    # OR EOB group-prefix format ("CO-50", "PR-27", "OA-18")
    "carc": r"(?:(?:CARC|carc|adjustment\s*reason\s*code)[:\s]*([0-9]{1,3}[A-Z]?)|(?:CO|PR|OA|PI|CR)-([0-9]{1,3}[A-Z]?))\b",
    "rarc": r"\b(?:RARC|rarc|remark\s*code)[:\s]*([A-Z]{1,2}[0-9]{1,3}[A-Z]?)\b",

    # Financial amounts
    "currency": r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)",

    # Dates — many formats
    "date_mdy": r"\b(0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12][0-9]|3[01])[\/\-](20[0-9]{2})\b",
    "date_ymd": r"\b(20[0-9]{2})[\/\-](0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12][0-9]|3[01])\b",
    "date_wordy": r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-9]{1,2}),?\s+(20[0-9]{2})\b",

    # Phone numbers
    "phone": r"(?:\+1[\s\-]?)?(?:\([0-9]{3}\)|[0-9]{3})[\s\-]?[0-9]{3}[\s\-]?[0-9]{4}",

    # Place of service (2-digit)
    "pos": r"(?:place\s*of\s*service|POS)[:\s]*([0-9]{2})\b",

    # Labeled date fields (for denial date / date of service)
    "date_of_denial_label": r"(?:date\s*of\s*(?:denial|notice|adverse|determination)|denial\s*date)[:\s]*(.{0,40})",
    "date_of_service_label": r"(?:date\s*of\s*service|service\s*date)[:\s]*(.{0,40})",
}

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

# ICD-10 codes that are clearly valid (letter + digits pattern)
_ICD10_RE = re.compile(r"^[A-Z][0-9]{2}\.?[0-9A-Z]{0,4}$")
# CPT codes are 5 numeric digits (or 4 digits + 1 alpha for category II/III)
_CPT_RE = re.compile(r"^[0-9]{4}[0-9A-Z]$")
# HCPCS Level II: letter + 4 digits
_HCPCS_RE = re.compile(r"^[A-Z][0-9]{4}$")


def _parse_date(text: str) -> date | None:
    """Try to parse a date string into a date object."""
    text = text.strip()
    # MM/DD/YYYY or MM-DD-YYYY
    m = re.match(r"^(0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12][0-9]|3[01])[\/\-](20[0-9]{2})$", text)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    # YYYY-MM-DD
    m = re.match(r"^(20[0-9]{2})[\/\-](0?[1-9]|1[0-2])[\/\-](0?[1-9]|[12][0-9]|3[01])$", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _extract_dates(text: str) -> list[date]:
    dates: list[date] = []
    # MM/DD/YYYY
    for m in re.finditer(_PATTERNS["date_mdy"], text, re.IGNORECASE):
        d = _parse_date(f"{m.group(1)}/{m.group(2)}/{m.group(3)}")
        if d:
            dates.append(d)
    # YYYY-MM-DD
    for m in re.finditer(_PATTERNS["date_ymd"], text, re.IGNORECASE):
        d = _parse_date(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        if d:
            dates.append(d)
    # Month DD, YYYY
    for m in re.finditer(_PATTERNS["date_wordy"], text, re.IGNORECASE):
        month = _MONTHS.get(m.group(1).capitalize())
        if month:
            try:
                dates.append(date(int(m.group(3)), month, int(m.group(2))))
            except ValueError:
                pass
    return dates


def _extract_currencies(text: str) -> list[float]:
    amounts = []
    for m in re.finditer(_PATTERNS["currency"], text):
        try:
            amounts.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return amounts


def _extract_icd10(text: str) -> list[str]:
    candidates = re.findall(_PATTERNS["icd10"], text)
    return list(dict.fromkeys(c.upper() for c in candidates if _ICD10_RE.match(c.upper())))


def _extract_cpt(text: str) -> list[str]:
    """Extract CPT codes using context-aware matching to reduce false positives.

    Strategy:
    1. Extract codes that appear after an explicit CPT label (e.g. "CPT Code: 47562",
       "CPT: 47562", "procedure code 47562").
    2. Fall back to bare 5-char codes only if they look like category II/III (contain
       a letter, e.g. "47562T") — all-numeric codes are too ambiguous without context.
    """
    found: list[str] = []

    # Pattern 1: explicit CPT label
    for m in re.finditer(
        r"(?:CPT\s*(?:code)?[:\s#]*|procedure\s*code[:\s#]*)([0-9]{4}[0-9A-Z])",
        text,
        re.IGNORECASE,
    ):
        code = m.group(1).upper()
        if _CPT_RE.match(code):
            found.append(code)

    # Pattern 2: category II/III codes that contain a letter (unambiguous)
    for m in re.finditer(r"\b([0-9]{4}[A-Z])\b", text):
        code = m.group(1).upper()
        if _CPT_RE.match(code) and code not in found:
            found.append(code)

    return list(dict.fromkeys(found))


def _extract_hcpcs(text: str) -> list[str]:
    candidates = re.findall(_PATTERNS["hcpcs"], text)
    return list(dict.fromkeys(c.upper() for c in candidates if _HCPCS_RE.match(c.upper())))


def _first_match(pattern: str, text: str, group: int = 1) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(group).strip() if m else None


def _all_matches(pattern: str, text: str, group: int = 1) -> list[str]:
    return [m.group(group).strip() for m in re.finditer(pattern, text, re.IGNORECASE)]


# ---------------------------------------------------------------------------
# Public extraction function
# ---------------------------------------------------------------------------

def _extract_carc(text: str) -> list[str]:
    """Extract CARC codes from both explicit-prefix and EOB group-prefix formats."""
    codes = []
    for m in re.finditer(_PATTERNS["carc"], text, re.IGNORECASE):
        # Group 1: explicit prefix (CARC: 50), Group 2: EOB prefix (CO-50)
        code = m.group(1) or m.group(2)
        if code:
            codes.append(code.strip())
    return list(dict.fromkeys(codes))


def extract_pass1(text: str) -> dict[str, Any]:
    """
    Run all regex patterns against the document text.
    Returns a dict of raw extracted values keyed by field name.
    This dict is used to populate the ClaimObject and also fed into Pass 2 (LLM).
    """
    dates = _extract_dates(text)
    currencies = _extract_currencies(text)

    # Denial keywords
    denial_lower = text.lower()
    prior_auth_status = None
    if "prior authorization" in denial_lower or "prior auth" in denial_lower:
        if "not obtained" in denial_lower or "not received" in denial_lower:
            prior_auth_status = "required_not_obtained"
        elif "denied" in denial_lower:
            prior_auth_status = "denied"
        elif "approved" in denial_lower or "authorized" in denial_lower:
            prior_auth_status = "approved"
        else:
            prior_auth_status = "required_unknown"

    expedited = None
    if "expedited" in denial_lower:
        expedited = True

    state_commissioner = None
    if "insurance commissioner" in denial_lower or "department of insurance" in denial_lower:
        state_commissioner = True

    # Try to identify denial date and service date from labeled patterns
    denial_date_str: str | None = None
    service_date_str: str | None = None
    denial_label_raw = _first_match(_PATTERNS["date_of_denial_label"], text)
    service_label_raw = _first_match(_PATTERNS["date_of_service_label"], text)
    if denial_label_raw:
        d = _parse_date(denial_label_raw.strip())
        if d is None:
            # Try wordy format like "March 5, 2026"
            for m in re.finditer(_PATTERNS["date_wordy"], denial_label_raw, re.IGNORECASE):
                month = _MONTHS.get(m.group(1).capitalize())
                if month:
                    try:
                        d = date(int(m.group(3)), month, int(m.group(2)))
                        break
                    except ValueError:
                        pass
        if d:
            denial_date_str = d.isoformat()
    if service_label_raw:
        d = _parse_date(service_label_raw.strip())
        if d is None:
            for m in re.finditer(_PATTERNS["date_wordy"], service_label_raw, re.IGNORECASE):
                month = _MONTHS.get(m.group(1).capitalize())
                if month:
                    try:
                        d = date(int(m.group(3)), month, int(m.group(2)))
                        break
                    except ValueError:
                        pass
        if d:
            service_date_str = d.isoformat()

    return {
        # Identification
        "claim_reference_number": _first_match(_PATTERNS["claim_number"], text),
        "plan_policy_number": _first_match(_PATTERNS["plan_number"], text),
        "group_number": _first_match(_PATTERNS["group_number"], text),
        "dates_found": [d.isoformat() for d in dates],
        "date_of_denial": denial_date_str,
        "date_of_service": service_date_str,

        # Patient / provider
        "treating_provider_npi": _first_match(_PATTERNS["npi"], text),
        "patient_member_id": _first_match(_PATTERNS["member_id"], text),

        # Billing codes
        "icd10_diagnosis_codes": _extract_icd10(text),
        "cpt_procedure_codes": _extract_cpt(text),
        "hcpcs_codes": _extract_hcpcs(text),
        "modifier_codes": _all_matches(_PATTERNS["modifier"], text),
        "place_of_service_code": _first_match(_PATTERNS["pos"], text),

        # Financial
        "currency_amounts": currencies,

        # Denial codes — CARC pattern has 2 groups: (explicit-prefix, group-prefix)
        "carc_codes": _extract_carc(text),
        "rarc_codes": _all_matches(_PATTERNS["rarc"], text),

        # Prior auth
        "prior_auth_status": prior_auth_status,
        "prior_auth_number": _first_match(_PATTERNS["prior_auth"], text),

        # Appeal rights
        "expedited_review_available": expedited,
        "insurer_appeals_phone": _first_match(_PATTERNS["phone"], text, group=0),
        "state_commissioner_info_present": state_commissioner,
    }
