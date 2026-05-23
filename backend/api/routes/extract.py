"""
POST /api/v1/documents/extract

Runs the full two-pass entity extraction pipeline:
  Pass 1: Deterministic regex extraction (free, instant)
  Pass 2: LLM-powered extraction via OpenAI (contextual entities)

Supports multi-document stitching when multiple documents are provided.
"""

import logging
from datetime import date

from fastapi import APIRouter, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from extraction.regex_extractor import extract_pass1
from extraction.llm_extractor import extract_pass2
from extraction.document_stitcher import stitch_documents, classify_document
from extraction.schema import ClaimObject, ExtractionConfidence, FieldProvenance, PlanContext
from extraction.confidence_scorer import compute_pass1_field_confidence, cross_validate_field

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class DocumentInput(BaseModel):
    doc_id: str
    text_extracted: str


class ExtractRequest(BaseModel):
    upload_id: str
    documents: list[DocumentInput]
    plan_context: PlanContext | None = None


class ExtractResponse(BaseModel):
    claim_object: ClaimObject
    extraction_confidence: ExtractionConfidence
    warnings: list[str]
    document_types: dict[str, str] = {}  # {doc_id: classified_type}


def _safe_parse_date(value: str | None) -> date | None:
    """Try to parse a date string in YYYY-MM-DD format."""
    if not value:
        return None
    try:
        parts = value.strip().split("-")
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        pass
    return None


def _confidence_from_results(pass1: dict, pass2: dict) -> ExtractionConfidence:
    """
    Compute per-field confidence scores from both extraction passes.

    Uses LLM-reported per-field confidence (from Pass 2 _confidence keys) when
    available; falls back to the 0.7/0.9/1.0 step function when not.

    Weights for overall score: critical fields count 2×, others 1×.
    """
    per_field: dict[str, float] = {}

    # (field_name, pass1_key, pass2_key, weight)
    key_fields: list[tuple[str, str | None, str | None, int]] = [
        ("date_of_denial",          "date_of_denial",           None,                      2),
        ("carc_codes",              "carc_codes",               None,                      2),
        ("denial_reason_narrative", None,                       "denial_reason_narrative",  2),
        ("claim_reference_number",  "claim_reference_number",   None,                      1),
        ("plan_policy_number",      "plan_policy_number",       None,                      1),
        ("patient_member_id",       "patient_member_id",        None,                      1),
        ("patient_full_name",       None,                       "patient_full_name",        1),
        ("treating_provider_name",  None,                       "treating_provider_name",   1),
        ("icd10_diagnosis_codes",   "icd10_diagnosis_codes",    None,                      1),
        ("cpt_procedure_codes",     "cpt_procedure_codes",      None,                      1),
        ("prior_auth_status",       "prior_auth_status",        "prior_auth_status",        1),
        ("treating_provider_npi",   "treating_provider_npi",    None,                      1),
        ("billed_amount",           None,                       "billed_amount",            1),
    ]

    weighted_total = 0.0
    weight_sum = 0

    for field_name, p1_key, p2_key, weight in key_fields:
        p1_val = pass1.get(p1_key) if p1_key else None
        p2_val = pass2.get(p2_key) if p2_key else None
        llm_confidence = pass2.get(f"{p2_key}_confidence") if p2_key else None

        score = 0.0
        has_p1 = p1_val is not None and p1_val != "" and p1_val != []
        has_p2 = p2_val is not None and p2_val != "" and p2_val != []

        if has_p2 and isinstance(llm_confidence, (int, float)):
            # Use LLM-reported confidence directly
            score = float(llm_confidence)
            if has_p1:
                # Both passes found something — bonus when they can agree
                score = min(1.0, score + 0.05)
        elif has_p1 and has_p2:
            score = 1.0   # both passes found something
        elif has_p2:
            score = 0.9   # LLM only
        elif has_p1:
            score = 0.7   # regex only

        per_field[field_name] = round(score, 3)
        weighted_total += score * weight
        weight_sum += weight

    return ExtractionConfidence(
        overall=round(weighted_total / weight_sum, 2) if weight_sum else 0.0,
        per_field=per_field,
    )


def _apply_pass2_to_claim(claim: ClaimObject, pass2: dict) -> None:
    """Merge Pass 2 LLM extraction results into the ClaimObject."""
    # Patient & Provider
    if pass2.get("patient_full_name"):
        claim.patient_provider.patient_full_name = pass2["patient_full_name"]
    if pass2.get("treating_provider_name"):
        claim.patient_provider.treating_provider_name = pass2["treating_provider_name"]
    if pass2.get("treating_provider_specialty"):
        claim.patient_provider.treating_provider_specialty = pass2["treating_provider_specialty"]
    if pass2.get("facility_name"):
        claim.patient_provider.facility_name = pass2["facility_name"]
    if pass2.get("facility_address"):
        claim.patient_provider.facility_address = pass2["facility_address"]
    if pass2.get("network_status"):
        claim.patient_provider.network_status = pass2["network_status"]

    # Dates
    dos = _safe_parse_date(pass2.get("date_of_service"))
    if dos:
        claim.identification.date_of_service = dos
    dod = _safe_parse_date(pass2.get("date_of_denial"))
    if dod:
        claim.identification.date_of_denial = dod
    doe = _safe_parse_date(pass2.get("date_of_eob"))
    if doe:
        claim.identification.date_of_eob = doe

    # Denial reason
    if pass2.get("denial_reason_narrative"):
        claim.denial_reason.denial_reason_narrative = pass2["denial_reason_narrative"]
    if pass2.get("plan_provision_cited"):
        claim.denial_reason.plan_provision_cited = pass2["plan_provision_cited"]
    if pass2.get("clinical_criteria_cited"):
        claim.denial_reason.clinical_criteria_cited = pass2["clinical_criteria_cited"]
    if pass2.get("medical_necessity_statement"):
        claim.denial_reason.medical_necessity_statement = pass2["medical_necessity_statement"]
    if pass2.get("prior_auth_status") and not claim.denial_reason.prior_auth_status:
        claim.denial_reason.prior_auth_status = pass2["prior_auth_status"]

    # Service description
    if pass2.get("procedure_description"):
        claim.service_billing.procedure_description = pass2["procedure_description"]

    # Financial — LLM can label amounts correctly (vs Pass 1 positional guessing)
    if pass2.get("billed_amount") is not None:
        claim.financial.billed_amount = float(pass2["billed_amount"])
    if pass2.get("allowed_amount") is not None:
        claim.financial.allowed_amount = float(pass2["allowed_amount"])
    if pass2.get("insurer_paid_amount") is not None:
        claim.financial.insurer_paid_amount = float(pass2["insurer_paid_amount"])
    if pass2.get("denied_amount") is not None:
        claim.financial.denied_amount = float(pass2["denied_amount"])
    if pass2.get("patient_responsibility_total") is not None:
        claim.financial.patient_responsibility_total = float(pass2["patient_responsibility_total"])
    if pass2.get("copay_amount") is not None:
        claim.financial.copay_amount = float(pass2["copay_amount"])
    if pass2.get("coinsurance_amount") is not None:
        claim.financial.coinsurance_amount = float(pass2["coinsurance_amount"])
    if pass2.get("deductible_applied") is not None:
        claim.financial.deductible_applied = float(pass2["deductible_applied"])

    # Appeal rights
    if pass2.get("internal_appeal_deadline_stated"):
        claim.appeal_rights.internal_appeal_deadline_stated = pass2["internal_appeal_deadline_stated"]
    if pass2.get("external_review_deadline_stated"):
        claim.appeal_rights.external_review_deadline_stated = pass2["external_review_deadline_stated"]
    if pass2.get("expedited_review_available") is not None:
        claim.appeal_rights.expedited_review_available = pass2["expedited_review_available"]
    if pass2.get("insurer_appeals_contact_name"):
        claim.appeal_rights.insurer_appeals_contact_name = pass2["insurer_appeals_contact_name"]
    if pass2.get("insurer_appeals_address"):
        claim.appeal_rights.insurer_appeals_address = pass2["insurer_appeals_address"]
    if pass2.get("insurer_appeals_fax"):
        claim.appeal_rights.insurer_appeals_fax = pass2["insurer_appeals_fax"]


def _populate_provenance_pass1(claim: ClaimObject, raw: dict, primary_doc_id: str | None) -> None:
    """
    Populate claim.provenance for key fields after Pass 1 regex extraction (§5.4).
    Only sets provenance for fields that were actually extracted.
    """
    _REGEX_TRACKED: list[tuple[str, str | None]] = [
        # (provenance_key, raw_key_or_None)
        ("date_of_denial",           "date_of_denial"),
        ("date_of_service",          "date_of_service"),
        ("claim_reference_number",   "claim_reference_number"),
        ("carc_codes",               "carc_codes"),
        ("billed_amount",            None),   # from financial_labeled
        ("allowed_amount",           None),
        ("insurer_paid_amount",      None),
        ("denied_amount",            None),
        ("patient_responsibility_total", None),
    ]
    fl = raw.get("financial_labeled") or {}

    for prov_key, raw_key in _REGEX_TRACKED:
        if raw_key:
            value = raw.get(raw_key)
        else:
            value = fl.get(prov_key)

        if value is not None and value != [] and value != "":
            conf = compute_pass1_field_confidence(prov_key, value, raw)
            claim.provenance[prov_key] = FieldProvenance(
                value=value,
                source_doc_id=primary_doc_id,
                extractor="regex",
                confidence=conf,
            )
        else:
            claim.provenance[prov_key] = FieldProvenance(
                value=None,
                source_doc_id=primary_doc_id,
                extractor="missing",
                confidence=0.0,
            )


def _update_provenance_llm(claim: ClaimObject, pass2: dict) -> None:
    """
    Upgrade provenance for fields that Pass 2 LLM extracted with higher confidence (§5.4).
    Overwrites regex provenance when LLM confidence > existing confidence.
    """
    _LLM_TRACKED: list[str] = [
        "date_of_denial",
        "denial_reason_narrative",
        "claim_reference_number",
        "billed_amount",
        "allowed_amount",
        "insurer_paid_amount",
        "denied_amount",
        "patient_responsibility_total",
    ]

    for field in _LLM_TRACKED:
        value = pass2.get(field)
        llm_conf = pass2.get(f"{field}_confidence")
        if value is None:
            continue
        confidence = float(llm_conf) if isinstance(llm_conf, (int, float)) else 0.85
        existing = claim.provenance.get(field)
        if existing is None or confidence > existing.confidence:
            claim.provenance[field] = FieldProvenance(
                value=value,
                extractor="llm",
                confidence=confidence,
            )


def _cross_validate_and_finalize_provenance(
    claim: ClaimObject, raw: dict, pass2: dict
) -> list[str]:
    """
    Cross-validate key fields between Pass 1 (raw) and Pass 2 (pass2) (§6).

    When both passes found a value for the same field:
      - If they agree  → update provenance confidence to 0.97 (cross-validated)
      - If they disagree → set confidence to 0.50, store both in disputed_values

    Returns a list of field names that have disagreements (for warnings).
    """
    # Fields that both passes can extract — eligible for cross-validation
    _CV_FIELDS: list[tuple[str, str]] = [
        # (provenance_key, pass2_key_in_llm_result)
        ("date_of_denial",              "date_of_denial"),
        ("claim_reference_number",      "claim_reference_number"),
        ("billed_amount",               "billed_amount"),
        ("allowed_amount",              "allowed_amount"),
        ("insurer_paid_amount",         "insurer_paid_amount"),
        ("denied_amount",               "denied_amount"),
        ("patient_responsibility_total","patient_responsibility_total"),
    ]

    fl = raw.get("financial_labeled") or {}
    disputed_fields: list[str] = []

    for prov_key, p2_key in _CV_FIELDS:
        # Get Pass 1 value (already in provenance from _populate_provenance_pass1)
        p1_prov = claim.provenance.get(prov_key)
        p1_val = p1_prov.value if p1_prov else None

        # For financial fields, also check the raw labeled dict as source
        if p1_val is None and prov_key in (
            "billed_amount", "allowed_amount", "insurer_paid_amount",
            "denied_amount", "patient_responsibility_total",
        ):
            p1_val = fl.get(prov_key)

        # Raw date fields use the iso string form
        if p1_val is None and prov_key == "date_of_denial":
            p1_val = raw.get("date_of_denial")
        if p1_val is None and prov_key == "claim_reference_number":
            p1_val = raw.get("claim_reference_number")

        p2_val = pass2.get(p2_key)

        conf, agreed, disputed = cross_validate_field(prov_key, p1_val, p2_val)
        if conf == 0.0:
            continue   # only one pass found it — no cross-validation applicable

        existing = claim.provenance.get(prov_key)
        if agreed:
            # Both passes agree — upgrade to cross-validated confidence
            if existing:
                existing.confidence = conf
            else:
                claim.provenance[prov_key] = FieldProvenance(
                    value=p2_val,
                    extractor="llm",
                    confidence=conf,
                )
        else:
            # Disagreement — flag the conflict
            disputed_fields.append(prov_key)
            if existing:
                existing.confidence = 0.50
                existing.disputed_values = disputed
            else:
                claim.provenance[prov_key] = FieldProvenance(
                    value=p1_val,
                    extractor="regex",
                    confidence=0.50,
                    disputed_values=disputed,
                )

    return disputed_fields


def _confidence_from_results(
    claim: ClaimObject, pass1: dict, pass2: dict
) -> ExtractionConfidence:
    """
    Compute per-field confidence scores from provenance + both passes (§6).

    Priority:
      1. If field is in claim.provenance → use its confidence (feature-based, cross-validated)
      2. LLM-reported confidence from pass2 `<field>_confidence` keys
      3. Legacy 0.7/0.9/1.0 step-function fallback for fields not in provenance

    Weighted overall: critical fields (`date_of_denial`, `carc_codes`,
    `denial_reason_narrative`) count 2×; others count 1×.
    """
    per_field: dict[str, float] = {}

    # (field_name, pass1_key, pass2_key, weight)
    key_fields: list[tuple[str, str | None, str | None, int]] = [
        ("date_of_denial",          "date_of_denial",           None,                      2),
        ("carc_codes",              "carc_codes",               None,                      2),
        ("denial_reason_narrative", None,                       "denial_reason_narrative",  2),
        ("claim_reference_number",  "claim_reference_number",   None,                      1),
        ("plan_policy_number",      "plan_policy_number",       None,                      1),
        ("patient_member_id",       "patient_member_id",        None,                      1),
        ("patient_full_name",       None,                       "patient_full_name",        1),
        ("treating_provider_name",  None,                       "treating_provider_name",   1),
        ("icd10_diagnosis_codes",   "icd10_diagnosis_codes",    None,                      1),
        ("cpt_procedure_codes",     "cpt_procedure_codes",      None,                      1),
        ("prior_auth_status",       "prior_auth_status",        "prior_auth_status",        1),
        ("treating_provider_npi",   "treating_provider_npi",    None,                      1),
        ("billed_amount",           None,                       "billed_amount",            1),
    ]

    weighted_total = 0.0
    weight_sum = 0

    for field_name, p1_key, p2_key, weight in key_fields:
        # 1. Prefer provenance confidence (feature-based + cross-validated)
        prov = claim.provenance.get(field_name)
        if prov and prov.extractor != "missing" and prov.confidence > 0.0:
            score = prov.confidence
        else:
            # 2. Legacy step-function fallback for fields not in provenance
            p1_val = pass1.get(p1_key) if p1_key else None
            p2_val = pass2.get(p2_key) if p2_key else None
            llm_confidence = pass2.get(f"{p2_key}_confidence") if p2_key else None

            has_p1 = p1_val is not None and p1_val != "" and p1_val != []
            has_p2 = p2_val is not None and p2_val != "" and p2_val != []

            score = 0.0
            if has_p2 and isinstance(llm_confidence, (int, float)):
                score = float(llm_confidence)
                if has_p1:
                    score = min(1.0, score + 0.05)
            elif has_p1 and has_p2:
                score = 1.0
            elif has_p2:
                score = 0.9
            elif has_p1:
                score = 0.7

        per_field[field_name] = round(score, 3)
        weighted_total += score * weight
        weight_sum += weight

    return ExtractionConfidence(
        overall=round(weighted_total / weight_sum, 2) if weight_sum else 0.0,
        per_field=per_field,
    )


@router.post("/extract", response_model=ExtractResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def extract_entities(request: Request, body: ExtractRequest) -> ExtractResponse:
    warnings: list[str] = []
    doc_types: dict[str, str] = {}

    # Combine text from all documents
    doc_texts = [
        {"doc_id": doc.doc_id, "text": doc.text_extracted}
        for doc in body.documents
        if doc.text_extracted.strip()
    ]

    if not doc_texts:
        warnings.append(
            "No text content found in uploaded documents. "
            "If these are scanned PDFs or images, please run OCR client-side first."
        )
        empty_claim = ClaimObject(
            upload_id=body.upload_id,
            source_documents=[d.doc_id for d in body.documents],
        )
        return ExtractResponse(
            claim_object=empty_claim,
            extraction_confidence=ExtractionConfidence(overall=0.0),
            warnings=warnings,
        )

    # ── Pass 1: Regex extraction (with multi-doc stitching) ──
    if len(doc_texts) > 1:
        raw, stitch_warnings, doc_types = stitch_documents(doc_texts)
        warnings.extend(stitch_warnings)
    else:
        raw = extract_pass1(doc_texts[0]["text"])
        doc_types = {doc_texts[0]["doc_id"]: classify_document(doc_texts[0]["text"])}

    # Build ClaimObject from Pass 1 results
    claim = ClaimObject(
        upload_id=body.upload_id,
        source_documents=[d.doc_id for d in body.documents],
    )

    # Identification
    claim.identification.claim_reference_number = raw.get("claim_reference_number")
    claim.identification.plan_policy_number = raw.get("plan_policy_number")
    claim.identification.group_number = raw.get("group_number")
    if raw.get("date_of_denial"):
        claim.identification.date_of_denial = _safe_parse_date(raw["date_of_denial"])
    if raw.get("date_of_service"):
        claim.identification.date_of_service = _safe_parse_date(raw["date_of_service"])
    if body.plan_context:
        claim.identification.plan_type = body.plan_context.plan_type
        claim.identification.erisa_or_state_regulated = body.plan_context.regulation_type
        claim.identification.plan_jurisdiction = body.plan_context.state
        claim.identification.regulation_type_source = (
            body.plan_context.regulation_type_source or "user"
        )

    # Patient / Provider
    claim.patient_provider.patient_member_id = raw.get("patient_member_id")
    claim.patient_provider.treating_provider_npi = raw.get("treating_provider_npi")

    # Service & Billing
    claim.service_billing.icd10_diagnosis_codes = raw.get("icd10_diagnosis_codes", [])
    claim.service_billing.cpt_procedure_codes = raw.get("cpt_procedure_codes", [])
    claim.service_billing.hcpcs_codes = raw.get("hcpcs_codes", [])
    claim.service_billing.modifier_codes = raw.get("modifier_codes", [])
    claim.service_billing.place_of_service_code = raw.get("place_of_service_code")

    # Financial — labeled regex (Pass 1), then legacy positional $-amount order, then Pass 2 LLM
    fl = raw.get("financial_labeled") or {}
    for attr in (
        "billed_amount",
        "allowed_amount",
        "insurer_paid_amount",
        "denied_amount",
        "patient_responsibility_total",
        "copay_amount",
        "coinsurance_amount",
        "deductible_applied",
    ):
        val = fl.get(attr)
        if val is not None:
            setattr(claim.financial, attr, float(val))

    amounts = raw.get("currency_amounts", [])
    if claim.financial.billed_amount is None and amounts:
        claim.financial.billed_amount = amounts[0]
    if claim.financial.denied_amount is None and len(amounts) > 1:
        claim.financial.denied_amount = amounts[1]

    # Denial reason
    claim.denial_reason.carc_codes = raw.get("carc_codes", [])
    claim.denial_reason.rarc_codes = raw.get("rarc_codes", [])
    claim.denial_reason.carc_codes_with_group = raw.get("carc_code_groups", {})
    claim.denial_reason.prior_auth_status = raw.get("prior_auth_status")
    claim.denial_reason.prior_auth_number = raw.get("prior_auth_number")

    # Appeal rights
    claim.appeal_rights.expedited_review_available = raw.get("expedited_review_available")
    claim.appeal_rights.insurer_appeals_phone = raw.get("insurer_appeals_phone")
    claim.appeal_rights.state_commissioner_info_present = raw.get("state_commissioner_info_present")

    # ── Provenance: Pass 1 ──
    primary_doc_id = doc_texts[0]["doc_id"] if len(doc_texts) == 1 else None
    _populate_provenance_pass1(claim, raw, primary_doc_id)

    # ── Pass 2: LLM extraction ──
    combined_text = "\n\n".join(d["text"] for d in doc_texts)
    pass2_results = await extract_pass2(combined_text, raw)

    if pass2_results:
        _apply_pass2_to_claim(claim, pass2_results)
        _update_provenance_llm(claim, pass2_results)
        # Cross-validate fields where both passes have values (§6)
        disputed = _cross_validate_and_finalize_provenance(claim, raw, pass2_results)
        if disputed:
            for field in disputed:
                prov = claim.provenance.get(field)
                vals = prov.disputed_values if prov else []
                warnings.append(
                    f"Pass 1 and Pass 2 disagreed on '{field}' "
                    f"(values: {vals[0]!r} vs {vals[1]!r}). "
                    "Verify this field manually."
                )
        logger.info(f"Pass 2 enriched {len(pass2_results)} fields")
    else:
        warnings.append(
            "LLM extraction (Pass 2) was skipped or returned no results. "
            "Results are based on regex extraction only."
        )

    # ── Warnings ──
    if not claim.service_billing.icd10_diagnosis_codes:
        warnings.append("No ICD-10 diagnosis codes found.")
    if not claim.service_billing.cpt_procedure_codes:
        warnings.append("No CPT procedure codes found.")
    if not claim.denial_reason.carc_codes:
        warnings.append("No CARC denial codes found.")
    if not claim.patient_provider.patient_full_name:
        warnings.append("Patient name not extracted. Please verify manually.")
    if not claim.denial_reason.denial_reason_narrative:
        warnings.append("Denial reason narrative not extracted — critical for analysis.")

    confidence = _confidence_from_results(claim, raw, pass2_results)

    return ExtractResponse(
        claim_object=claim,
        extraction_confidence=confidence,
        warnings=warnings,
        document_types=doc_types,
    )
