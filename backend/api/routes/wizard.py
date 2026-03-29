"""
POST /api/v1/wizard/plan-type

Determines the regulatory framework (ERISA vs. state vs. Medicaid) for a claim
based on the user's answers to 3 questions, and returns:
  - regulation_type
  - appeal_path (ordered list of steps)
  - primary_regulator (name, url, phone)
  - applicable_laws (citations)
  - state_specific (DOI contact block + relevant state resources)
"""

import json
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_DOI_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "state_doi_contacts.json"

with open(_DOI_DATA_PATH) as f:
    _STATE_DOI: dict = json.load(f)


class PlanSource(str, Enum):
    employer = "employer"
    marketplace = "marketplace"
    medicaid = "medicaid"
    individual = "individual"


class EmployerPlanType(str, Enum):
    erisa = "erisa"
    fully_insured = "fully_insured"
    unknown = "unknown"


class WizardRequest(BaseModel):
    source: PlanSource
    employer_plan_type: EmployerPlanType | None = None
    state: str = "IN"


class Regulator(BaseModel):
    name: str
    url: str
    phone: str


class StateSpecific(BaseModel):
    doi_name: str
    doi_phone: str
    doi_address: str
    doi_complaint_url: str
    doi_website: str
    external_review_url: str | None = None
    consumer_guide_url: str | None = None


class WizardResponse(BaseModel):
    regulation_type: str
    appeal_path: list[str]
    primary_regulator: Regulator
    applicable_laws: list[dict]
    state_specific: StateSpecific | None


def _get_state_doi(state: str) -> StateSpecific | None:
    state = state.upper()
    entry = _STATE_DOI.get(state)
    if not entry:
        return None
    return StateSpecific(
        doi_name=entry["name"],
        doi_phone=entry["phone"],
        doi_address=entry["address"],
        doi_complaint_url=entry["complaint_url"],
        doi_website=entry["website"],
        external_review_url=entry.get("external_review_url"),
        consumer_guide_url=entry.get("consumer_guide_url"),
    )


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

_ERISA_LAWS = [
    {
        "law": "ERISA",
        "section": "§503 (29 U.S.C. §1133)",
        "relevance": "Requires internal appeal procedures for self-funded employer plans",
        "url": "https://www.dol.gov/general/topic/health-plans/erisa",
    },
    {
        "law": "29 CFR §2560.503-1",
        "section": "Claims Procedure Regulation",
        "relevance": "Specifies timelines, notices, and appeal rights for ERISA plans",
        "url": "https://www.ecfr.gov/current/title-29/subtitle-B/chapter-XXV/subchapter-G/part-2560/section-2560.503-1",
    },
    {
        "law": "ACA §2719",
        "section": "45 CFR §147.136",
        "relevance": "Internal/external appeal rules (applies to non-grandfathered plans)",
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.136",
    },
]

_ACA_STATE_LAWS = [
    {
        "law": "ACA §2719",
        "section": "45 CFR §147.136",
        "relevance": "Requires internal and external appeal rights for fully-insured plans",
        "url": "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-B/part-147/section-147.136",
    },
    {
        "law": "PPACA §1001",
        "section": "Public Health Service Act §2719",
        "relevance": "Mandates external independent review for adverse benefit determinations",
        "url": "https://www.hhs.gov/healthcare/rights/appeal/index.html",
    },
]

_MEDICAID_LAWS = [
    {
        "law": "42 CFR §431.200–§431.250",
        "section": "Medicaid Fair Hearing Requirements",
        "relevance": "Federal regulations governing Medicaid beneficiary appeal rights",
        "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-C/part-431/subpart-E",
    },
    {
        "law": "42 U.S.C. §1396a(a)(3)",
        "section": "Social Security Act",
        "relevance": "State Medicaid plans must provide opportunity for a fair hearing",
        "url": "https://www.ssa.gov/OP_Home/ssact/title19/1902.htm",
    },
]

_INDIVIDUAL_LAWS = _ACA_STATE_LAWS  # Individual market plans are state-regulated, ACA applies


def _build_erisa_response(state: str) -> WizardResponse:
    return WizardResponse(
        regulation_type="erisa",
        appeal_path=[
            "File an internal appeal with your employer's plan administrator (deadline: 180 days from denial date under ACA; 60 days under ERISA minimum).",
            "Request the full claim file and internal guidelines from the plan within 30 days.",
            "If internal appeal is denied, file for External Independent Review (IRO) — required for non-grandfathered ERISA plans.",
            "If all internal/external options exhausted, file a complaint with the U.S. Department of Labor (DOL) Employee Benefits Security Administration (EBSA).",
            "Consider legal action in federal court under ERISA §502(a).",
        ],
        primary_regulator=Regulator(
            name="U.S. Department of Labor – Employee Benefits Security Administration (EBSA)",
            url="https://www.dol.gov/agencies/ebsa",
            phone="1-866-444-3272",
        ),
        applicable_laws=_ERISA_LAWS,
        state_specific=_get_state_doi(state),
    )


def _build_state_response(state: str) -> WizardResponse:
    state_doi = _get_state_doi(state)
    regulator_name = state_doi.doi_name if state_doi else f"{state} Department of Insurance"
    regulator_url = state_doi.doi_website if state_doi else f"https://www.{state.lower()}.gov"
    regulator_phone = state_doi.doi_phone if state_doi else "Contact your state DOI"

    return WizardResponse(
        regulation_type="state",
        appeal_path=[
            "File an internal appeal with your insurer (deadline: 180 days from denial date under ACA §2719).",
            "Request the full claim file, internal guidelines, and denial reason in writing within 30 days.",
            "If internal appeal is denied, file for External Independent Review (IRO) — mandatory for fully-insured plans under ACA.",
            f"File a complaint with the {regulator_name} if the insurer violates state prompt payment or appeal rules.",
            "Contact a patient advocate or attorney if the denied amount is significant.",
        ],
        primary_regulator=Regulator(
            name=regulator_name,
            url=regulator_url,
            phone=regulator_phone,
        ),
        applicable_laws=_ACA_STATE_LAWS,
        state_specific=state_doi,
    )


def _build_medicaid_response(state: str) -> WizardResponse:
    state_doi = _get_state_doi(state)
    return WizardResponse(
        regulation_type="medicaid",
        appeal_path=[
            "Request a Medicaid Fair Hearing from your state Medicaid agency (deadline: 90 days from denial notice).",
            "You can continue receiving services pending the hearing decision (aid-pending continuation).",
            "Attend the fair hearing or submit written evidence.",
            "If the hearing decision is unfavorable, appeal to the state court system.",
            "Contact your state's Medicaid managed care ombudsman or legal aid for assistance.",
        ],
        primary_regulator=Regulator(
            name="Centers for Medicare & Medicaid Services (CMS)",
            url="https://www.medicaid.gov",
            phone="1-800-633-4227",
        ),
        applicable_laws=_MEDICAID_LAWS,
        state_specific=state_doi,
    )


def _build_individual_response(state: str) -> WizardResponse:
    state_doi = _get_state_doi(state)
    regulator_name = state_doi.doi_name if state_doi else f"{state} Department of Insurance"
    regulator_url = state_doi.doi_website if state_doi else f"https://www.{state.lower()}.gov"
    regulator_phone = state_doi.doi_phone if state_doi else "Contact your state DOI"

    return WizardResponse(
        regulation_type="state",
        appeal_path=[
            "File an internal appeal with your insurer (deadline: 180 days from denial date).",
            "Request complete denial documentation, plan documents, and internal guidelines.",
            "If internal appeal fails, request External Independent Review (required for individual market plans).",
            f"File a complaint with {regulator_name} if the insurer is non-compliant.",
            "Contact your state's marketplace navigator or consumer assistance program for help.",
        ],
        primary_regulator=Regulator(
            name=regulator_name,
            url=regulator_url,
            phone=regulator_phone,
        ),
        applicable_laws=_INDIVIDUAL_LAWS,
        state_specific=state_doi,
    )


@router.post("/plan-type", response_model=WizardResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def plan_type_wizard(request: Request, body: WizardRequest) -> WizardResponse:
    state = body.state.upper() if body.state else "IN"

    if body.source == PlanSource.employer:
        emp_type = body.employer_plan_type or EmployerPlanType.unknown
        if emp_type == EmployerPlanType.erisa:
            return _build_erisa_response(state)
        elif emp_type == EmployerPlanType.fully_insured:
            return _build_state_response(state)
        else:
            # Unknown employer plan: default to ERISA (most common for large employers)
            resp = _build_erisa_response(state)
            resp.applicable_laws = _ERISA_LAWS + [
                {
                    "law": "Note",
                    "section": "Plan type uncertain",
                    "relevance": "Large employers (>250 employees) are usually ERISA self-funded. Small employers are often fully-insured (state-regulated). Check your Summary Plan Description (SPD).",
                    "url": "https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/faqs/aca-implementation-part-i",
                }
            ]
            return resp

    elif body.source == PlanSource.marketplace:
        return _build_state_response(state)

    elif body.source == PlanSource.medicaid:
        return _build_medicaid_response(state)

    elif body.source == PlanSource.individual:
        return _build_individual_response(state)

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown plan source.")
