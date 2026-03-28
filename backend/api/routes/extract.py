"""
POST /api/v1/documents/extract

Runs Pass 1 (regex) entity extraction on previously uploaded document text.
Pass 2 (LLM structured output) is implemented in Week 2.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from extraction.regex_extractor import extract_pass1
from extraction.schema import ClaimObject, ExtractionConfidence, PlanContext

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


def _confidence_from_pass1(raw: dict) -> ExtractionConfidence:
    """Rough heuristic confidence scores based on what was found."""
    per_field: dict[str, float] = {}
    total = 0.0
    count = 0

    def score(key: str, value) -> float:
        if value is None:
            return 0.0
        if isinstance(value, list):
            return 1.0 if value else 0.0
        return 1.0 if str(value).strip() else 0.0

    for key in [
        "claim_reference_number", "plan_policy_number", "patient_member_id",
        "icd10_diagnosis_codes", "cpt_procedure_codes", "carc_codes",
        "currency_amounts", "prior_auth_status", "treating_provider_npi",
    ]:
        s = score(key, raw.get(key))
        per_field[key] = s
        total += s
        count += 1

    return ExtractionConfidence(
        overall=round(total / count, 2) if count else 0.0,
        per_field=per_field,
    )


@router.post("/extract", response_model=ExtractResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def extract_entities(request: Request, body: ExtractRequest) -> ExtractResponse:
    warnings: list[str] = []

    # Combine text from all documents
    combined_text = "\n\n".join(
        f"=== Document {doc.doc_id} ===\n{doc.text_extracted}"
        for doc in body.documents
        if doc.text_extracted.strip()
    )

    if not combined_text.strip():
        warnings.append("No text content found in uploaded documents. If these are scanned PDFs or images, please run OCR client-side first.")
        empty_claim = ClaimObject(
            upload_id=body.upload_id,
            source_documents=[d.doc_id for d in body.documents],
        )
        return ExtractResponse(
            claim_object=empty_claim,
            extraction_confidence=ExtractionConfidence(overall=0.0),
            warnings=warnings,
        )

    # Pass 1: regex extraction
    raw = extract_pass1(combined_text)

    # Build ClaimObject from Pass 1 results
    dates = raw.get("dates_found", [])

    claim = ClaimObject(
        upload_id=body.upload_id,
        source_documents=[d.doc_id for d in body.documents],
    )

    # Identification
    claim.identification.claim_reference_number = raw.get("claim_reference_number")
    claim.identification.plan_policy_number = raw.get("plan_policy_number")
    claim.identification.group_number = raw.get("group_number")
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

    # Financial — assign currency amounts positionally if no labels found
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

    # Warnings
    if not claim.service_billing.icd10_diagnosis_codes:
        warnings.append("No ICD-10 diagnosis codes found. Pass 2 (LLM extraction) may recover these.")
    if not claim.service_billing.cpt_procedure_codes:
        warnings.append("No CPT procedure codes found.")
    if not claim.denial_reason.carc_codes:
        warnings.append("No CARC denial codes found.")

    confidence = _confidence_from_pass1(raw)

    return ExtractResponse(
        claim_object=claim,
        extraction_confidence=confidence,
        warnings=warnings,
    )
