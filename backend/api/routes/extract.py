"""
POST /api/v1/documents/extract

Runs the full two-pass entity extraction pipeline:
  Pass 1: Deterministic regex extraction (free, instant)
  Pass 2: LLM-powered extraction via Gemini (contextual entities)

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
from extraction.schema import ClaimObject, ExtractionConfidence, PlanContext

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
    """Compute confidence scores from both extraction passes."""
    per_field: dict[str, float] = {}
    total = 0.0
    count = 0

    # Key fields to score
    key_fields = {
        "claim_reference_number": ("claim_reference_number", None),
        "plan_policy_number": ("plan_policy_number", None),
        "patient_member_id": ("patient_member_id", None),
        "patient_full_name": (None, "patient_full_name"),
        "treating_provider_name": (None, "treating_provider_name"),
        "icd10_diagnosis_codes": ("icd10_diagnosis_codes", None),
        "cpt_procedure_codes": ("cpt_procedure_codes", None),
        "carc_codes": ("carc_codes", None),
        "denial_reason_narrative": (None, "denial_reason_narrative"),
        "prior_auth_status": ("prior_auth_status", "prior_auth_status"),
        "treating_provider_npi": ("treating_provider_npi", None),
        "billed_amount": (None, "billed_amount"),
    }

    for field_name, (p1_key, p2_key) in key_fields.items():
        score = 0.0
        p1_val = pass1.get(p1_key) if p1_key else None
        p2_val = pass2.get(p2_key) if p2_key else None

        if p1_val is not None and p1_val != "" and p1_val != []:
            score = 0.7  # Regex found something
        if p2_val is not None and p2_val != "" and p2_val != []:
            score = max(score, 0.9)  # LLM found something — higher confidence
        if score == 0.7 and p2_val is not None:
            score = 1.0  # Both passes agree — highest confidence

        per_field[field_name] = score
        total += score
        count += 1

    return ExtractionConfidence(
        overall=round(total / count, 2) if count else 0.0,
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

    # Patient / Provider
    claim.patient_provider.patient_member_id = raw.get("patient_member_id")
    claim.patient_provider.treating_provider_npi = raw.get("treating_provider_npi")

    # Service & Billing
    claim.service_billing.icd10_diagnosis_codes = raw.get("icd10_diagnosis_codes", [])
    claim.service_billing.cpt_procedure_codes = raw.get("cpt_procedure_codes", [])
    claim.service_billing.hcpcs_codes = raw.get("hcpcs_codes", [])
    claim.service_billing.modifier_codes = raw.get("modifier_codes", [])
    claim.service_billing.place_of_service_code = raw.get("place_of_service_code")

    # Financial — positional assignment from Pass 1 (overridden by Pass 2)
    amounts = raw.get("currency_amounts", [])
    if amounts:
        claim.financial.billed_amount = amounts[0] if len(amounts) > 0 else None
        claim.financial.denied_amount = amounts[1] if len(amounts) > 1 else None

    # Denial reason
    claim.denial_reason.carc_codes = raw.get("carc_codes", [])
    claim.denial_reason.rarc_codes = raw.get("rarc_codes", [])
    claim.denial_reason.prior_auth_status = raw.get("prior_auth_status")
    claim.denial_reason.prior_auth_number = raw.get("prior_auth_number")

    # Appeal rights
    claim.appeal_rights.expedited_review_available = raw.get("expedited_review_available")
    claim.appeal_rights.insurer_appeals_phone = raw.get("insurer_appeals_phone")
    claim.appeal_rights.state_commissioner_info_present = raw.get("state_commissioner_info_present")

    # ── Pass 2: LLM extraction ──
    combined_text = "\n\n".join(d["text"] for d in doc_texts)
    pass2_results = await extract_pass2(combined_text, raw)

    if pass2_results:
        _apply_pass2_to_claim(claim, pass2_results)
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

    confidence = _confidence_from_results(raw, pass2_results)

    return ExtractResponse(
        claim_object=claim,
        extraction_confidence=confidence,
        warnings=warnings,
        document_types=doc_types,
    )
