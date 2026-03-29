"""
Pydantic models for the Claim Object — the central data structure that flows
through the entire pipeline from extraction → enrichment → analysis → output.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PlanType(str, Enum):
    employer_erisa = "employer_erisa"
    employer_fully_insured = "employer_fully_insured"
    employer_unknown = "employer_unknown"
    marketplace = "marketplace"
    medicaid = "medicaid"
    individual = "individual"


class RegulationType(str, Enum):
    erisa = "erisa"
    state = "state"
    medicaid = "medicaid"
    unknown = "unknown"


class SeverityTriage(str, Enum):
    urgent = "urgent"
    time_sensitive = "time_sensitive"
    routine = "routine"


class RootCauseCategory(str, Enum):
    medical_necessity = "medical_necessity"
    prior_authorization = "prior_authorization"
    coding_billing_error = "coding_billing_error"
    network_coverage = "network_coverage"
    eligibility_enrollment = "eligibility_enrollment"
    procedural_administrative = "procedural_administrative"


# ---------------------------------------------------------------------------
# 3.1 Claim Identification
# ---------------------------------------------------------------------------

class ClaimIdentification(BaseModel):
    claim_reference_number: Optional[str] = None
    date_of_service: Optional[date] = None
    date_of_denial: Optional[date] = None
    date_of_eob: Optional[date] = None
    plan_policy_number: Optional[str] = None
    group_number: Optional[str] = None
    plan_type: Optional[PlanType] = None
    plan_jurisdiction: Optional[str] = None          # e.g. "IN"
    erisa_or_state_regulated: Optional[RegulationType] = None


# ---------------------------------------------------------------------------
# 3.2 Patient & Provider
# ---------------------------------------------------------------------------

class PatientProviderEntities(BaseModel):
    patient_full_name: Optional[str] = None
    patient_member_id: Optional[str] = None
    patient_dob: Optional[date] = None
    treating_provider_name: Optional[str] = None
    treating_provider_npi: Optional[str] = None
    treating_provider_specialty: Optional[str] = None
    facility_name: Optional[str] = None
    facility_address: Optional[str] = None
    network_status: Optional[str] = None             # e.g. "in-network", "out-of-network"


# ---------------------------------------------------------------------------
# 3.3 Service & Billing Codes
# ---------------------------------------------------------------------------

class ServiceBillingEntities(BaseModel):
    icd10_diagnosis_codes: list[str] = Field(default_factory=list)
    cpt_procedure_codes: list[str] = Field(default_factory=list)
    hcpcs_codes: list[str] = Field(default_factory=list)
    procedure_description: Optional[str] = None
    service_date_range: Optional[str] = None
    place_of_service_code: Optional[str] = None
    units_of_service: Optional[int] = None
    modifier_codes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3.4 Financial
# ---------------------------------------------------------------------------

class FinancialEntities(BaseModel):
    billed_amount: Optional[float] = None
    allowed_amount: Optional[float] = None
    insurer_paid_amount: Optional[float] = None
    denied_amount: Optional[float] = None
    patient_responsibility_total: Optional[float] = None
    copay_amount: Optional[float] = None
    coinsurance_amount: Optional[float] = None
    deductible_applied: Optional[float] = None
    out_of_pocket_remaining: Optional[float] = None


# ---------------------------------------------------------------------------
# 3.5 Denial Reason
# ---------------------------------------------------------------------------

class DenialReasonEntities(BaseModel):
    carc_codes: list[str] = Field(default_factory=list)
    rarc_codes: list[str] = Field(default_factory=list)
    denial_reason_narrative: Optional[str] = None
    plan_provision_cited: Optional[str] = None
    clinical_criteria_cited: Optional[str] = None
    medical_necessity_statement: Optional[str] = None
    prior_auth_status: Optional[str] = None          # e.g. "required_not_obtained", "approved", "denied"
    prior_auth_number: Optional[str] = None


# ---------------------------------------------------------------------------
# 3.6 Appeal Rights & Contact
# ---------------------------------------------------------------------------

class AppealRightsEntities(BaseModel):
    internal_appeal_deadline_stated: Optional[str] = None
    external_review_deadline_stated: Optional[str] = None
    expedited_review_available: Optional[bool] = None
    insurer_appeals_contact_name: Optional[str] = None
    insurer_appeals_phone: Optional[str] = None
    insurer_appeals_address: Optional[str] = None
    insurer_appeals_fax: Optional[str] = None
    state_commissioner_info_present: Optional[bool] = None


# ---------------------------------------------------------------------------
# 3.7 Derived / Computed (filled by Analysis Agent)
# ---------------------------------------------------------------------------

class DerivedEntities(BaseModel):
    root_cause_category: Optional[RootCauseCategory] = None
    responsible_party: Optional[str] = None
    denial_completeness_score: Optional[float] = None    # 0.0 – 1.0
    appeal_deadline_internal: Optional[date] = None
    appeal_deadline_external: Optional[date] = None
    appeal_deadline_expedited: Optional[date] = None
    approval_probability_score: Optional[float] = None   # 0.0 – 1.0
    severity_triage: Optional[SeverityTriage] = None


# ---------------------------------------------------------------------------
# Top-level Claim Object
# ---------------------------------------------------------------------------

class ClaimObject(BaseModel):
    # Extraction metadata
    upload_id: str
    source_documents: list[str] = Field(default_factory=list)   # doc_ids

    identification: ClaimIdentification = Field(default_factory=ClaimIdentification)
    patient_provider: PatientProviderEntities = Field(default_factory=PatientProviderEntities)
    service_billing: ServiceBillingEntities = Field(default_factory=ServiceBillingEntities)
    financial: FinancialEntities = Field(default_factory=FinancialEntities)
    denial_reason: DenialReasonEntities = Field(default_factory=DenialReasonEntities)
    appeal_rights: AppealRightsEntities = Field(default_factory=AppealRightsEntities)
    derived: DerivedEntities = Field(default_factory=DerivedEntities)


# ---------------------------------------------------------------------------
# Extraction confidence
# ---------------------------------------------------------------------------

class ExtractionConfidence(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    per_field: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Plan context (user-provided via wizard)
# ---------------------------------------------------------------------------

class PlanContext(BaseModel):
    plan_type: PlanType
    regulation_type: RegulationType
    state: str = "IN"
