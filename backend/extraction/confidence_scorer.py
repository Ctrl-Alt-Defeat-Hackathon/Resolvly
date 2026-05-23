"""
Feature-based confidence scoring (§6).

Replaces the 3-bucket step function (0.7 regex / 0.9 LLM / 1.0 both)
with per-field confidence derived from HOW the value was extracted:
  - Labeled patterns score higher than positional fallbacks
  - Cross-validated values (Pass 1 ≈ Pass 2) score highest
  - Disputed values (Pass 1 ≠ Pass 2) score 0.5 and store both candidates

Design constraint: compute confidence purely from the raw dicts returned by
extract_pass1 and extract_pass2, with no additional document scanning.
"""
from __future__ import annotations

from datetime import date as date_cls
from typing import Any


# ---------------------------------------------------------------------------
# Feature-based Pass 1 confidence
# ---------------------------------------------------------------------------

_FINANCIAL_LABELED_FIELDS = frozenset({
    "billed_amount", "allowed_amount", "insurer_paid_amount",
    "denied_amount", "patient_responsibility_total",
    "copay_amount", "coinsurance_amount", "deductible_applied",
})


def compute_pass1_field_confidence(field_name: str, value: Any, raw: dict) -> float:
    """
    Return a feature-based confidence score for a Pass 1 (regex) extracted field.

    Scores reflect extraction quality:
      0.92–0.93 — extracted from a verbatim labeled pattern ("Date of Denial: ...")
      0.88–0.90 — extracted from a well-structured labeled pattern (e.g. "CARC: 50")
      0.87      — extracted from a labeled identifier regex
      0.75      — extracted from a less-specific but reliable pattern
      0.50      — extracted positionally (no field label, just currency position)
      0.0       — not found
    """
    if value is None or value == [] or value == {} or value == "":
        return 0.0

    # Date of denial: only set when the "Date of Denial: …" labeled pattern fires
    if field_name == "date_of_denial":
        return 0.92

    # Date of service: from the "date of service" labeled pattern
    if field_name == "date_of_service":
        return 0.88

    # Claim reference number: from a labeled "claim #/no./number:" pattern
    if field_name == "claim_reference_number":
        return 0.87

    # CARC codes: differentiate explicit label form vs EOB group-prefix form
    if field_name == "carc_codes":
        groups = raw.get("carc_code_groups") or {}
        has_explicit = any(g == "" for g in groups.values())
        has_group_prefix = any(g != "" for g in groups.values())
        if has_explicit and has_group_prefix:
            return 0.92   # both forms present — highest
        if has_explicit:
            return 0.93   # "CARC: 50" form is very precise
        if has_group_prefix:
            return 0.90   # "CO-50" form from EOB table
        return 0.80

    # Financial amounts: distinguish labeled extraction from positional fallback
    if field_name in _FINANCIAL_LABELED_FIELDS:
        fl = raw.get("financial_labeled") or {}
        if fl.get(field_name) is not None:
            return 0.88   # labeled regex hit ("Patient Responsibility: $…")
        return 0.50       # positional currency fallback — much lower confidence

    # NPI: always Luhn-validated before reaching provenance
    if field_name == "treating_provider_npi":
        return 0.85

    # Member/policy/group IDs: from labeled regex
    if field_name in ("patient_member_id", "plan_policy_number", "group_number"):
        return 0.82

    # ICD-10 / CPT / HCPCS codes: structural validation applied but no label
    if field_name in ("icd10_diagnosis_codes", "cpt_procedure_codes", "hcpcs_codes"):
        return 0.78

    # Default for any other labeled-pattern fields
    return 0.75


# ---------------------------------------------------------------------------
# Cross-validation helpers
# ---------------------------------------------------------------------------

def _normalize_for_compare(field_name: str, value: Any) -> Any:
    """
    Normalize a field value for equality comparison between passes.
    Dates are parsed to date objects; amounts are floated; strings are lowercased.
    """
    if value is None:
        return None

    date_fields = {"date_of_denial", "date_of_service", "date_of_eob"}
    if field_name in date_fields:
        if isinstance(value, date_cls):
            return value
        if isinstance(value, str):
            parts = value.strip().split("-")
            if len(parts) == 3:
                try:
                    return date_cls(int(parts[0]), int(parts[1]), int(parts[2]))
                except (ValueError, TypeError):
                    pass
        return str(value).strip()

    amount_fields = _FINANCIAL_LABELED_FIELDS
    if field_name in amount_fields:
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return value

    if isinstance(value, str):
        return value.strip().lower()

    return value


def _values_agree(field_name: str, v1: Any, v2: Any) -> bool:
    """Return True when two normalized values can be considered the same."""
    n1 = _normalize_for_compare(field_name, v1)
    n2 = _normalize_for_compare(field_name, v2)

    if n1 is None or n2 is None:
        return False

    if field_name in _FINANCIAL_LABELED_FIELDS:
        try:
            return abs(float(n1) - float(n2)) <= 1.00   # $1 tolerance
        except (ValueError, TypeError):
            return False

    return n1 == n2


def cross_validate_field(
    field_name: str,
    p1_value: Any,
    p2_value: Any,
) -> tuple[float, bool, list[Any]]:
    """
    Compare Pass 1 and Pass 2 values for a single field.

    Returns:
        confidence     — 0.97 (agreed), 0.50 (disagreed), or unchanged when only one pass found it
        agreed         — True when both passes found identical/compatible values
        disputed       — [p1_value, p2_value] when they disagree; empty list otherwise

    Caller is responsible for using the existing provenance confidence when only
    one of the two passes has a value (no cross-validation benefit in that case).
    """
    has_p1 = p1_value is not None and p1_value != [] and p1_value != "" and p1_value != {}
    has_p2 = p2_value is not None and p2_value != [] and p2_value != "" and p2_value != {}

    if not has_p1 or not has_p2:
        return 0.0, False, []   # 0.0 signals "no cross-validation applicable"

    if _values_agree(field_name, p1_value, p2_value):
        return 0.97, True, []

    # Disagreement
    return 0.50, False, [p1_value, p2_value]
