"""
Pass 1 — Deterministic Regex Extraction.

Extracts all structured entities (codes, dates, amounts, IDs) from raw text
without any LLM calls. Fast, free, and deterministic.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# NPI Luhn validation
# ---------------------------------------------------------------------------

def _is_valid_npi(npi: str) -> bool:
    """
    Validate a 10-digit NPI using the CMS Luhn-variant algorithm.
    Prepend '80840' to the first 9 digits, apply standard Luhn, compare check digit.
    """
    if len(npi) != 10 or not npi.isdigit():
        return False
    payload = "80840" + npi[:9]
    check_digit = int(npi[9])
    total = 0
    for i, ch in enumerate(reversed(payload)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (total + check_digit) % 10 == 0


# ---------------------------------------------------------------------------
# CPT modifier allowlist — any 2-char token NOT in this set is discarded
# ---------------------------------------------------------------------------

_VALID_CPT_MODIFIERS: frozenset[str] = frozenset({
    "21", "22", "23", "24", "25", "26", "27", "32", "33",
    "47", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59",
    "62", "63", "66", "76", "77", "78", "79",
    "80", "81", "82", "90", "91", "92", "95", "96", "97", "99",
    "AA", "AD", "AH", "AI", "AJ", "AM", "AO", "AP", "AQ", "AR", "AS", "AT",
    "AU", "AV", "AW", "AX", "AY", "AZ",
    "BA", "BL", "BO", "BP", "BR", "BS", "BT",
    "CA", "CB", "CC", "CD", "CE", "CF", "CG", "CH", "CI", "CJ", "CK",
    "CM", "CN", "CO", "CP", "CQ", "CR", "CS", "CT",
    "DA", "E1", "E2", "E3", "E4", "EA", "EB", "EC", "ED", "EE",
    "EJ", "EM", "EP", "ER", "ET", "EX", "EY",
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "FA", "FP",
    "G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9",
    "GA", "GB", "GC", "GD", "GE", "GF", "GG", "GH", "GJ", "GK",
    "GL", "GM", "GN", "GP", "GQ", "GR", "GS", "GT", "GU", "GV",
    "GW", "GX", "GY", "GZ",
    "HA", "HB", "HC", "HD", "HE", "HF", "HG", "HH", "HI", "HJ",
    "HK", "HL", "HM", "HN", "HO", "HP", "HQ", "HR", "HS", "HT",
    "HU", "HV", "HW", "HX", "HY", "HZ",
    "J1", "J2", "J3", "J4", "JA", "JB", "JW",
    "K0", "K1", "K2", "K3", "K4", "KA", "KB", "KC", "KD", "KE",
    "KF", "KG", "KH", "KI", "KJ", "KX",
    "L1", "LC", "LD", "LE", "LF", "LT",
    "M2", "MA", "MB", "MC", "MD", "ME", "MF", "MG", "MH", "MS",
    "N1", "NR",
    "P1", "P2", "P3", "P4", "P5", "P6", "P9", "PA", "PB", "PC",
    "Q0", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "QA", "QB",
    "QC", "QD", "QE", "QF", "QG", "QH", "QI", "QJ", "QK", "QM",
    "QN", "QP", "QQ", "QR", "QS", "QT", "QU", "QV", "QW", "QX", "QY", "QZ",
    "RA", "RB", "RC", "RD", "RE", "RR", "RS", "RT",
    "SA", "SB", "SC", "SD", "SE", "SF", "SG", "SH", "SI", "SJ",
    "SK", "SL", "SM", "SN", "SQ", "SS", "ST", "SU", "SV", "SW",
    "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9",
    "TA", "TB", "TC", "TD", "TE", "TF", "TG", "TH", "TJ", "TK",
    "TL", "TM", "TN", "TP", "TQ", "TR", "TS", "TT",
    "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9",
    "UA", "UB", "UC", "UD", "UE", "UF", "UG", "UH",
    "VP", "XE", "XP", "XS", "XU",
})

from extraction.schema import (
    AppealRightsEntities,
    ClaimIdentification,
    DenialReasonEntities,
    FinancialEntities,
    PatientProviderEntities,
    ServiceBillingEntities,
)


# ---------------------------------------------------------------------------
# ICD-10-CM valid first-character ranges
# All 26 letters A-Z are valid ICD-10-CM leading characters in the current
# specification (U codes added for COVID/emergency use). We use an allowlist to
# explicitly guard against future additions and document the intent.
# Additionally we keep a small set of 3-char tokens that appear in EOB/denial
# contexts but are NOT ICD-10 codes (RARC/CARC context strings).
# ---------------------------------------------------------------------------

_ICD10_VALID_FIRST_CHARS: frozenset[str] = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Tokens that match the ICD-10 regex structurally but appear as billing
# administrative codes in EOBs — excluded to reduce false positives.
_ICD10_KNOWN_EXCLUSIONS: frozenset[str] = frozenset({
    # Common RARC codes that happen to be letter+digit+digit
    "N19", "N20", "N30", "N95", "N96",
    # CARC group identifiers sometimes printed as bare codes
    "CO1", "PR1", "OA1",
    # Revenue codes that look like ICD-10
    "REV",
})


def _is_valid_icd10(code: str) -> bool:
    """
    Accept a candidate ICD-10-CM code if it passes structural and exclusion checks.
    The validation loop (§5) will further discard codes not found in the NLM database.
    """
    if not code or len(code) < 3:
        return False
    if code[0] not in _ICD10_VALID_FIRST_CHARS:
        return False
    if not code[1].isdigit() or not code[2].isdigit():
        return False
    if code in _ICD10_KNOWN_EXCLUSIONS:
        return False
    return True


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, str] = {
    # Billing codes
    "icd10": r"\b([A-Z][0-9]{2}\.?[0-9A-Z]{0,4})\b",
    "cpt": r"\b([0-9]{4}[0-9A-Z]|[0-9]{5})\b",                          # 5-char CPT
    "hcpcs": r"\b([A-Z][0-9]{4})\b",
    "modifier": r"\b([A-Z]{2}|[0-9]{2}|[A-Z][0-9]|[0-9][A-Z])\b",      # pre-filtered via _VALID_CPT_MODIFIERS allowlist below

    # Claim & plan identifiers
    "claim_number": r"(?:claim\s*(?:reference\s*)?(?:#|no\.?|number)[:\s]*)([\w\-]{6,20})",
    "member_id": r"(?:member\s*(?:id|#|no\.?)[:\s]*)([\w\-]{6,20})",
    "group_number": r"(?:group\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,15})",
    "plan_number": r"(?:policy\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,20})",
    "npi": r"\b([0-9]{10})\b",                                            # validated via Luhn checksum below
    "prior_auth": r"(?:auth(?:orization)?\s*(?:#|no\.?|number)[:\s]*)([\w\-]{4,20})",

    # Denial codes
    # CARC codes: explicit prefix ("CARC: 50", "adjustment reason code 50")
    # OR EOB group-prefix format ("CO-50", "PR-27", "OA-18")
    # Group 1 = code from explicit form; Group 2 = code from group-prefix form; Group 3 = the prefix (CO/PR/OA/…)
    "carc": r"(?:(?:CARC|carc|adjustment\s*reason\s*code)[:\s]*([0-9]{1,3}[A-Z]?)|(CO|PR|OA|PI|CR)-([0-9]{1,3}[A-Z]?))\b",
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

    # Labeled date fields (100-char window to handle verbose denial letter phrasing).
    # e.g. "Date of Denial Determination Notice (the date of this letter): March 5, 2026"
    "date_of_denial_label": r"(?:date\s*of\s*(?:denial|notice|adverse|determination)|denial\s*date)[:\s]*(.{0,100})",
    "date_of_service_label": r"(?:date\s*of\s*service|service\s*date)[:\s]*(.{0,100})",
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


_MONEY_CAP = r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+\.[0-9]{2})"


def _parse_money_cap(s: str) -> float | None:
    s = s.strip().replace(",", "")
    if not s:
        return None
    try:
        v = float(s)
        return v if v >= 0 else None
    except ValueError:
        return None


def _first_labeled_amount(text: str, patterns: list[str]) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            v = _parse_money_cap(m.group(1))
            if v is not None:
                return v
    return None


def extract_labeled_financials(text: str) -> dict[str, float]:
    """
    Map common EOB / denial / hospital-bill labels to structured financial fields.
    This fixes gaps where Pass 1 only had positional currency_amounts[0]/[1] and
    Pass 2 (LLM) is skipped — insurer_paid, copay, etc. were never set by regex alone.
    """
    # fmt: off
    labeled: dict[str, float] = {}

    billed = _first_labeled_amount(
        text,
        [
            rf"(?i)(?:total\s+)?(?:billed|charge(?:d)?|submitted|amount\s+charged)[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:charge|billed)\s+amount[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)total\s+charges?[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if billed is not None:
        labeled["billed_amount"] = billed

    allowed = _first_labeled_amount(
        text,
        [
            rf"(?i)(?:contracted|allowed)\s+(?:amount|rate)?[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)eligible\s+amount[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if allowed is not None:
        labeled["allowed_amount"] = allowed

    paid = _first_labeled_amount(
        text,
        [
            rf"(?i)plan\s+paid[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:insurance|plan|payer|ins\.?)\s+(?:paid|payment|pay)\s*(?:amount)?[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:amount\s+)?paid\s+by\s+(?:insurance|plan|payer)[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)payer\s+responsibility\s+paid[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)payment\s+from\s+(?:insurance|plan)[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)net\s+paid[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if paid is not None:
        labeled["insurer_paid_amount"] = paid

    denied = _first_labeled_amount(
        text,
        [
            rf"(?i)(?:amount\s+)?denied[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)disallowed[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:not\s+covered|uncovered)(?:\s+amount)?[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)denial\s+amount[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if denied is not None:
        labeled["denied_amount"] = denied

    copay = _first_labeled_amount(
        text,
        [
            rf"(?i)co[-\s]?pay(?:ment)?[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)copay[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if copay is not None:
        labeled["copay_amount"] = copay

    coins = _first_labeled_amount(
        text,
        [
            rf"(?i)co[-\s]?insurance[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)coinsurance[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if coins is not None:
        labeled["coinsurance_amount"] = coins

    ded = _first_labeled_amount(
        text,
        [
            rf"(?i)deductible(?:\s+applied)?[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if ded is not None:
        labeled["deductible_applied"] = ded

    pr = _first_labeled_amount(
        text,
        [
            rf"(?i)patient\s+responsibility[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:your|member)\s+responsibility[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)(?:you\s+owe|balance\s+due|amount\s+you\s+owe)[:\s]+\$?\s*{_MONEY_CAP}",
            rf"(?i)member\s+liability[:\s]+\$?\s*{_MONEY_CAP}",
        ],
    )
    if pr is not None:
        labeled["patient_responsibility_total"] = pr

    # fmt: on
    return labeled


def _extract_icd10(text: str) -> list[str]:
    candidates = re.findall(_PATTERNS["icd10"], text)
    return list(dict.fromkeys(
        c.upper() for c in candidates
        if _ICD10_RE.match(c.upper()) and _is_valid_icd10(c.upper())
    ))


_PROC_LINE_RE = re.compile(
    r"(?:procedure|proc|service|svc)\b[^\n]*?\b([0-9]{5})\b[^\n]*?\$",
    re.IGNORECASE,
)


def _extract_cpt(text: str) -> list[str]:
    """Extract CPT codes using context-aware matching to reduce false positives.

    Strategy:
    1. Explicit CPT label (highest confidence).
    2. Category II/III alpha-suffix codes (unambiguous).
    3. Bare 5-digit codes that appear in a procedure/service context line containing
       a dollar amount (positional heuristic for table rows in EOBs).
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

    # Pattern 3: bare 5-digit codes in procedure/service table rows with a dollar amount
    # Requires "procedure|proc|service|svc" AND "$" on the same line to reduce false positives
    for m in _PROC_LINE_RE.finditer(text):
        code = m.group(1)
        n = int(code)
        if 100 <= n <= 99999 and code not in found:
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

def _extract_carc(text: str) -> tuple[list[str], dict[str, str]]:
    """
    Extract CARC codes from both explicit-prefix and EOB group-prefix formats.

    Returns:
        codes: list of code numbers (e.g. ["50", "27"]) — backward-compatible
        code_groups: dict mapping code → group prefix (e.g. {"50": "CO", "27": "PR"})
                     CO = provider-side, PR = patient-side, OA = other adjustment
                     "" = extracted from explicit form (CARC: 50) with no group context
    """
    codes: list[str] = []
    code_groups: dict[str, str] = {}

    for m in re.finditer(_PATTERNS["carc"], text, re.IGNORECASE):
        if m.group(1):
            # Explicit form: "CARC: 50" or "adjustment reason code 50"
            code = m.group(1).strip()
            if code not in code_groups:
                codes.append(code)
                code_groups[code] = ""  # no group prefix in explicit form
        elif m.group(3):
            # EOB group-prefix form: "CO-50", "PR-27"
            prefix = m.group(2).upper()
            code = m.group(3).strip()
            if code not in code_groups:
                codes.append(code)
                code_groups[code] = prefix
            elif code_groups[code] == "":
                # Upgrade to group-prefix if we previously saw explicit form
                code_groups[code] = prefix

    return list(dict.fromkeys(codes)), code_groups


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

    carc_codes, carc_code_groups = _extract_carc(text)

    return {
        # Identification
        "claim_reference_number": _first_match(_PATTERNS["claim_number"], text),
        "plan_policy_number": _first_match(_PATTERNS["plan_number"], text),
        "group_number": _first_match(_PATTERNS["group_number"], text),
        "dates_found": [d.isoformat() for d in dates],
        "date_of_denial": denial_date_str,
        "date_of_service": service_date_str,

        # Patient / provider — NPI validated via Luhn checksum to reject phone numbers
        "treating_provider_npi": next(
            (m.group(1) for m in re.finditer(_PATTERNS["npi"], text) if _is_valid_npi(m.group(1))),
            None,
        ),
        "patient_member_id": _first_match(_PATTERNS["member_id"], text),

        # Billing codes
        "icd10_diagnosis_codes": _extract_icd10(text),
        "cpt_procedure_codes": _extract_cpt(text),
        "hcpcs_codes": _extract_hcpcs(text),
        # Modifier codes filtered through allowlist of ~150 valid CPT modifier values
        "modifier_codes": [
            m.upper()
            for m in _all_matches(_PATTERNS["modifier"], text)
            if m.upper() in _VALID_CPT_MODIFIERS
        ],
        "place_of_service_code": _first_match(_PATTERNS["pos"], text),

        # Financial
        "currency_amounts": currencies,
        "financial_labeled": extract_labeled_financials(text),

        # Denial codes — code list (backward-compatible) + group prefix map (new)
        "carc_codes": carc_codes,
        "carc_code_groups": carc_code_groups,  # {code: "CO"|"PR"|"OA"|""}
        "rarc_codes": _all_matches(_PATTERNS["rarc"], text),

        # Prior auth
        "prior_auth_status": prior_auth_status,
        "prior_auth_number": _first_match(_PATTERNS["prior_auth"], text),

        # Appeal rights
        "expedited_review_available": expedited,
        "insurer_appeals_phone": _first_match(_PATTERNS["phone"], text, group=0),
        "state_commissioner_info_present": state_commissioner,
    }
