"""
Document Stitcher v2

When multiple documents are uploaded (e.g., denial letter + EOB + hospital bill),
this module:
  1. Classifies each document by type using weighted feature-scoring (not fragile keyword count)
  2. Assigns a classification confidence; docs below threshold → requires_review
  3. Runs Pass 1 (regex) on each document individually
  4. Quality-ranks duplicate doc types (prefer content-rich, parsable documents)
  5. Checks claim-ID consistency across documents and warns on mismatches
  6. Merges entity fields intelligently into a single ClaimObject result

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
# Feature-scoring document classifier (v2)
# ---------------------------------------------------------------------------

# Each rule: (doc_type, compiled_regex, weight)
# Higher weight = stronger signal for that doc type.
# Multiple rules for the same doc_type accumulate; the highest total wins.
_FEATURE_RULES: list[tuple[str, re.Pattern, int]] = [
    # Denial letter signals
    (
        "denial_letter",
        re.compile(r"right to appeal|appeal rights|adverse benefit determination", re.I),
        4,
    ),
    (
        "denial_letter",
        re.compile(r"we have determined|coverage has been denied|not medically necessary|claim is denied", re.I),
        3,
    ),
    (
        "denial_letter",
        re.compile(r"your request for (coverage|benefits|services) (has been|is) denied", re.I),
        3,
    ),
    (
        "denial_letter",
        re.compile(r"internal (appeal|review)|external review|independent review", re.I),
        2,
    ),
    (
        "denial_letter",
        re.compile(r"days (of|from) (this notice|receipt|denial)", re.I),
        2,
    ),

    # EOB signals
    (
        "eob",
        re.compile(r"explanation of benefits|this is not a bill", re.I),
        5,
    ),
    (
        "eob",
        re.compile(r"adjustment reason code|remark code|CARC|RARC", re.I),
        4,
    ),
    (
        "eob",
        re.compile(r"\$[\d,]+\.\d{2}[^\n]{0,60}(?:allowed|paid|responsibility|billed)", re.I),
        3,
    ),
    (
        "eob",
        re.compile(r"amount (billed|paid|allowed)|patient responsibility|provider paid", re.I),
        3,
    ),
    (
        "eob",
        re.compile(r"claim number[:\s]+\S+.{0,80}(?:allowed|billed|paid)", re.I | re.DOTALL),
        2,
    ),

    # Hospital bill signals
    (
        "hospital_bill",
        re.compile(r"statement of (?:account|charges)|billing statement|patient account", re.I),
        4,
    ),
    (
        "hospital_bill",
        re.compile(r"(?:bed type|drg|diagnosis.related.group)", re.I),
        4,
    ),
    (
        "hospital_bill",
        re.compile(r"total charges?[:\s]+\$[\d,]+", re.I),
        3,
    ),
    (
        "hospital_bill",
        re.compile(r"(?:amount due|balance due|payment due)[:\s]+\$", re.I),
        2,
    ),

    # Insurance card signals
    (
        "insurance_card",
        re.compile(r"rx\s*bin|rx\s*pcn|payer\s*id", re.I),
        5,
    ),
    (
        "insurance_card",
        re.compile(r"member\s*id[:\s]+\S+.{0,40}group\s*(#|number|no\.?)", re.I | re.DOTALL),
        4,
    ),
    (
        "insurance_card",
        re.compile(r"(?:subscriber|member)[:\s]+.{0,30}plan\s*name", re.I | re.DOTALL),
        3,
    ),

    # Prior auth letter signals
    (
        "prior_auth_letter",
        re.compile(r"prior auth(?:orization)?\s*(number|#|no\.?|letter)", re.I),
        4,
    ),
    (
        "prior_auth_letter",
        re.compile(r"authorization\s*(number|#)[:\s]+\S+", re.I),
        4,
    ),
    (
        "prior_auth_letter",
        re.compile(r"(?:approved for|authorization request|authorized service)", re.I),
        3,
    ),
]

# Minimum confidence to trust the top classification; below → requires_review
_CONFIDENCE_THRESHOLD = 0.30


def classify_document_scored(text: str) -> tuple[str, float]:
    """
    Classify a document type using weighted feature-scoring.

    Returns:
        (doc_type, confidence) where confidence = (winner - runner_up) / winner.
        If confidence < _CONFIDENCE_THRESHOLD the caller should treat as requires_review.
    """
    scores: dict[str, int] = {}

    for doc_type, pattern, weight in _FEATURE_RULES:
        if pattern.search(text):
            scores[doc_type] = scores.get(doc_type, 0) + weight

    if not scores:
        return "requires_review", 0.0

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    winner_type, winner_score = sorted_scores[0]
    runner_up_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    confidence = (winner_score - runner_up_score) / winner_score if winner_score > 0 else 0.0

    if confidence < _CONFIDENCE_THRESHOLD:
        return "requires_review", confidence

    return winner_type, round(confidence, 2)


def classify_document(text: str) -> str:
    """
    Classify a document by type. Returns a string doc_type.

    Backward-compatible wrapper around classify_document_scored.
    Possible values: denial_letter, eob, hospital_bill, insurance_card,
                     prior_auth_letter, requires_review
    """
    doc_type, _ = classify_document_scored(text)
    return doc_type


# ---------------------------------------------------------------------------
# Quality-ranking within a document type
# ---------------------------------------------------------------------------

def _score_document_quality(doc_type: str, text: str, raw: dict[str, Any]) -> int:
    """
    Score the quality of a document of a known type.
    Higher score → prefer this document as the authoritative source.
    """
    score = 0

    # Longer content is usually more complete
    score += min(len(text) // 500, 10)

    # For denial letters: prefer ones with a parseable denial date and CARC codes
    if doc_type == "denial_letter":
        if raw.get("date_of_denial"):
            score += 5
        if raw.get("carc_codes"):
            score += 3
        if raw.get("denial_reason_narrative") or "denial" in text.lower():
            score += 2

    # For EOBs: prefer ones with financial amounts and CARC codes
    elif doc_type == "eob":
        fl = raw.get("financial_labeled") or {}
        score += min(len(fl), 5)
        if raw.get("carc_codes"):
            score += 3

    return score


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
        "carc_codes", "rarc_codes", "carc_code_groups",
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
    if new is None or new == "" or new == [] or new == {}:
        return existing
    if existing is None or existing == "" or existing == [] or existing == {}:
        return new
    if isinstance(existing, list) and isinstance(new, list):
        seen = set()
        merged = []
        for item in existing + new:
            if item not in seen:
                seen.add(item)
                merged.append(item)
        return merged
    if isinstance(existing, dict) and isinstance(new, dict):
        return {**existing, **new}
    return new


# ---------------------------------------------------------------------------
# Claim-ID consistency check
# ---------------------------------------------------------------------------

def _check_claim_id_consistency(
    doc_extractions: list[tuple[str, str, dict[str, Any]]]
) -> list[str]:
    """
    Warn when documents have conflicting claim_reference_numbers.
    Docs without a claim number are ignored (they can't contradict).
    """
    warnings: list[str] = []
    id_map: dict[str, str] = {}  # claim_ref → first doc_id that set it

    for doc_id, doc_type, raw in doc_extractions:
        ref = raw.get("claim_reference_number")
        if not ref:
            continue
        existing = id_map.get(ref)
        if existing is None:
            id_map[ref] = doc_id
        elif existing != doc_id and existing != ref:
            # Only warn if we see a genuinely different reference number
            first_ref = next(iter(id_map))
            if ref != first_ref:
                warnings.append(
                    f"Claim reference mismatch: document '{doc_id}' ({doc_type}) shows "
                    f"'{ref}', but an earlier document shows '{first_ref}'. "
                    "Verify these are the same claim before submitting an appeal."
                )
                break

    return warnings


# ---------------------------------------------------------------------------
# Public stitcher
# ---------------------------------------------------------------------------

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
        doc_type, confidence = classify_document_scored(text)
        raw = extract_pass1(text)
        warnings: list[str] = []
        if doc_type == "requires_review":
            warnings.append(
                f"Document '{documents[0]['doc_id']}' could not be confidently classified "
                "(feature score confidence too low). Verify the document type manually."
            )
        return raw, warnings, {documents[0]["doc_id"]: doc_type}

    # Classify each document with confidence scoring
    doc_type_map: dict[str, str] = {}
    doc_confidences: dict[str, float] = {}
    doc_extractions: list[tuple[str, str, dict[str, Any]]] = []  # (doc_id, doc_type, raw)
    warnings: list[str] = []

    for doc in documents:
        doc_type, confidence = classify_document_scored(doc["text"])
        doc_type_map[doc["doc_id"]] = doc_type
        doc_confidences[doc["doc_id"]] = confidence
        raw = extract_pass1(doc["text"])
        doc_extractions.append((doc["doc_id"], doc_type, raw))

        if doc_type == "requires_review":
            warnings.append(
                f"Document '{doc['doc_id']}' could not be confidently classified "
                f"(confidence={confidence:.0%}). It may still contribute fields in the merge step, "
                "but it is not treated as an authoritative source for any field group."
            )

    # Quality-rank documents within each type and warn on duplicates
    type_to_docs: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for doc_id, doc_type, raw in doc_extractions:
        if doc_type == "requires_review":
            continue
        type_to_docs.setdefault(doc_type, []).append((doc_id, raw))

    for doc_type, docs in type_to_docs.items():
        if len(docs) > 1:
            warnings.append(
                f"Multiple documents classified as '{doc_type}' ({len(docs)} found). "
                "Using the highest-quality document as the authoritative source."
            )

    # Build a "best doc per type" map (highest quality score wins)
    best_doc_per_type: dict[str, dict[str, Any]] = {}
    for doc_type, docs in type_to_docs.items():
        ranked = sorted(
            docs,
            key=lambda t: _score_document_quality(doc_type, "", t[1]),
            reverse=True,
        )
        best_doc_per_type[doc_type] = ranked[0][1]  # raw extraction of best doc

    # Claim-ID consistency check
    warnings.extend(_check_claim_id_consistency(doc_extractions))

    # Build priority ordering: authoritative doc types first for their fields
    merged: dict[str, Any] = {}
    authority_applied: set[str] = set()

    for doc_type_priority in ["denial_letter", "eob", "hospital_bill"]:
        best_raw = best_doc_per_type.get(doc_type_priority)
        if best_raw is None:
            continue
        for field in _FIELD_AUTHORITY.get(doc_type_priority, []):
            if field in best_raw and field not in authority_applied:
                merged[field] = _merge_value(merged.get(field), best_raw.get(field))
                authority_applied.add(field)

    # Second pass: fill remaining fields from any source (including requires_review docs)
    for _, _, raw in doc_extractions:
        for key, value in raw.items():
            if key == "financial_labeled":
                continue
            if key not in merged or merged[key] is None or merged[key] == "" or merged[key] == []:
                merged[key] = value
            elif isinstance(merged[key], list) and isinstance(value, list):
                merged[key] = _merge_value(merged[key], value)
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = _merge_value(merged[key], value)

    # Labeled financials: union keys from all docs
    fl_merged: dict[str, float] = {}
    for _, _, raw in doc_extractions:
        for k, v in (raw.get("financial_labeled") or {}).items():
            if k not in fl_merged:
                fl_merged[k] = v
    merged["financial_labeled"] = fl_merged

    return merged, warnings, doc_type_map
