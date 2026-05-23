"""
Pydantic models for the Claim Object — the central data structure that flows
through the entire pipeline from extraction → enrichment → analysis → output.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal, Optional
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
# Provenance — tracks where each extracted field came from
# ---------------------------------------------------------------------------

class FieldProvenance(BaseModel):
    """Tracks the origin and confidence of a single extracted field."""
    value: Any = None
    source_doc_id: Optional[str] = None
    extractor: Literal["regex", "llm", "user", "missing", "unknown"] = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_url: Optional[str] = None
    # Populated when Pass 1 and Pass 2 disagree on the same field.
    # Contains [pass1_value, pass2_value] so the caller can surface the conflict.
    disputed_values: list[Any] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# State-level appeal deadlines (replaces unstructured dict[str, str])
# ---------------------------------------------------------------------------

class StateDeadlines(BaseModel):
    """Structured deadline information for a state's appeal process."""
    internal_appeal_days: Optional[int] = None
    external_review_days: Optional[int] = None
    external_review_authority: Optional[str] = None
    expedited_hours: Optional[int] = None
    regulation_basis: Optional[str] = None
    source_url: Optional[str] = None
    last_verified: Optional[date] = None
    note: Optional[str] = None

    @classmethod
    def from_legacy_dict(cls, d: dict[str, str]) -> "StateDeadlines":
        """Convert from the old dict[str, str] format."""
        def _int(v: str | None) -> int | None:
            try:
                return int(v) if v else None
            except (ValueError, TypeError):
                return None

        return cls(
            internal_appeal_days=_int(d.get("internal_appeal_days")),
            external_review_days=_int(d.get("external_review_days")),
            expedited_hours=_int(d.get("expedited_hours")),
            regulation_basis=d.get("regulation_basis"),
            note=d.get("note"),
        )


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
    # Tracks how regulation_type was determined: "user" (wizard), "extracted" (denial letter), "defaulted"
    regulation_type_source: Optional[Literal["user", "extracted", "defaulted"]] = None


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
    # Codes extracted but not resolved against NLM/CMS — excluded from appeal letter citations
    unverified_codes: list[str] = Field(default_factory=list)


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
    # Maps each CARC code to its group prefix (CO, PR, OA, PI, CR, or "" for explicit form)
    # e.g. {"50": "CO", "1": "PR"} — drives responsible_party inference
    carc_codes_with_group: dict[str, str] = Field(default_factory=dict)
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
# 3.7 Derived / Computed (filled exclusively by Analysis Agent)
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

    # Per-field provenance: maps field name → extraction origin and confidence
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)


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
    # How the regulation_type was determined — surfaces in the assumptions panel
    regulation_type_source: Optional[Literal["user", "extracted", "defaulted"]] = None
