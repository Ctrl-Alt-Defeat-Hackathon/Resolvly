"""
Document Stitcher

When multiple documents are uploaded (e.g., denial letter + EOB + hospital bill),
this module:
  1. Classifies each document by type using keyword heuristics
  2. Runs Pass 1 (regex) on each document individually
  3. Merges entity fields intelligently into a single ClaimObject,
     preferring values from the most authoritative source for each field

Priority rules:
  - Claim IDs, denial reasons, appeal rights → denial letter
  - Billing codes, financial amounts, CARC/RARC → EOB
  - Provider details, facility info → hospital bill or EOB
  - Patient info → any document (first found)
"""
from __future__ import annotations

import re
from typing import Any

from extraction.regex_extractor import extract_pass1


# ---------------------------------------------------------------------------
# Document type classification (heuristic)
# ---------------------------------------------------------------------------

_DOC_TYPE_KEYWORDS: dict[str, list[str]] = {
    "denial_letter": [
        "denied", "denial", "not covered", "not medically necessary",
        "adverse benefit determination", "appeal rights", "right to appeal",
        "we have determined", "coverage has been denied",
        "precertification", "your request for coverage",
    ],
    "eob": [
        "explanation of benefits", "eob", "this is not a bill",
        "claim number", "allowed amount", "patient responsibility",
        "amount billed", "amount paid", "adjustment reason",
        "remark code", "carc", "rarc", "provider paid",
    ],
    "hospital_bill": [
        "statement of charges", "patient account", "amount due",
        "balance due", "billing statement", "hospital charges",
        "total charges", "payment due", "account number",
    ],
    "insurance_card": [
        "member id", "group number", "rx bin", "rx pcn",
        "copay", "subscriber", "payer id", "plan name",
    ],
    "prior_auth_letter": [
        "prior authorization", "precertification",
        "authorization number", "approved for", "authorization request",
    ],
}


def classify_document(text: str) -> str:
    """Classify a document by type based on keyword frequency."""
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        scores[doc_type] = score

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        return "other"
    return best


# ---------------------------------------------------------------------------
# Merge strategy
# ---------------------------------------------------------------------------

# Which document type is authoritative for which field groups
_FIELD_AUTHORITY: dict[str, list[str]] = {
    "denial_letter": [
        "claim_reference_number", "date_of_denial",
        "denial_reason_narrative", "plan_provision_cited",
        "clinical_criteria_cited", "medical_necessity_statement",
        "prior_auth_status", "prior_auth_number",
        "internal_appeal_deadline_stated", "external_review_deadline_stated",
        "expedited_review_available", "insurer_appeals_contact_name",
        "insurer_appeals_phone", "insurer_appeals_address",
        "insurer_appeals_fax", "state_commissioner_info_present",
    ],
    "eob": [
        "carc_codes", "rarc_codes",
        "icd10_diagnosis_codes", "cpt_procedure_codes", "hcpcs_codes",
        "modifier_codes", "place_of_service_code",
        "billed_amount", "allowed_amount", "insurer_paid_amount",
        "denied_amount", "patient_responsibility_total",
        "copay_amount", "coinsurance_amount", "deductible_applied",
        "out_of_pocket_remaining",
        "date_of_eob", "date_of_service",
        "treating_provider_npi", "network_status",
    ],
    "hospital_bill": [
        "facility_name", "facility_address",
        "units_of_service", "service_date_range",
    ],
}


def _merge_value(existing: Any, new: Any) -> Any:
    """Merge two values — lists are unioned, scalars prefer non-None new value."""
    if new is None or new == "" or new == []:
        return existing
    if existing is None or existing == "" or existing == []:
        return new
    # Both have values — for lists, union them preserving order
    if isinstance(existing, list) and isinstance(new, list):
        seen = set()
        merged = []
        for item in existing + new:
            if item not in seen:
                seen.add(item)
                merged.append(item)
        return merged
    # For scalars, prefer the new value (from the more authoritative source)
    return new


def stitch_documents(
    documents: list[dict],
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """
    Stitch multiple documents into a unified extraction result.

    Args:
        documents: list of {"doc_id": str, "text": str} dicts

    Returns:
        (merged_pass1_results, warnings, doc_type_map)
        - merged_pass1_results: combined Pass 1 extraction dict
        - warnings: list of warning messages
        - doc_type_map: {doc_id: classified_type}
    """
    if not documents:
        return {}, ["No documents provided"], {}

    if len(documents) == 1:
        text = documents[0]["text"]
        doc_type = classify_document(text)
        raw = extract_pass1(text)
        return raw, [], {documents[0]["doc_id"]: doc_type}

    # Classify each document
    doc_type_map: dict[str, str] = {}
    doc_extractions: list[tuple[str, str, dict[str, Any]]] = []  # (doc_id, doc_type, raw)
    warnings: list[str] = []

    for doc in documents:
        doc_type = classify_document(doc["text"])
        doc_type_map[doc["doc_id"]] = doc_type
        raw = extract_pass1(doc["text"])
        doc_extractions.append((doc["doc_id"], doc_type, raw))

    # Check for duplicate document types
    type_counts: dict[str, int] = {}
    for _, doc_type, _ in doc_extractions:
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
    for doc_type, count in type_counts.items():
        if count > 1 and doc_type != "other":
            warnings.append(f"Multiple documents classified as '{doc_type}' — using first occurrence for authoritative fields")

    # Build priority ordering: authoritative doc types first for their fields
    # Start with empty merged result
    merged: dict[str, Any] = {}

    # First pass: apply authoritative sources
    authority_applied: set[str] = set()
    for doc_type_priority in ["denial_letter", "eob", "hospital_bill"]:
        fields = _FIELD_AUTHORITY.get(doc_type_priority, [])
        for doc_id, doc_type, raw in doc_extractions:
            if doc_type == doc_type_priority:
                for field in fields:
                    if field in raw and field not in authority_applied:
                        merged[field] = _merge_value(merged.get(field), raw.get(field))
                        authority_applied.add(field)
                break  # Only use first doc of each type for authority

    # Second pass: fill in remaining fields from any source
    for _, _, raw in doc_extractions:
        for key, value in raw.items():
            if key not in merged or merged[key] is None or merged[key] == "" or merged[key] == []:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = _merge_value(merged[key], value)

    return merged, warnings, doc_type_map
