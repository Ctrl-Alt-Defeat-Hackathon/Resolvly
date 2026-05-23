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
import logging
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from tools.regulatory_fetch import fetch_applicable_laws_for_profile

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

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


class EmployerSize(str, Enum):
    under_50 = "under_50"          # ALEs exempt; almost never self-funded
    size_50_999 = "size_50_999"    # mixed; moderate prior for self-funded
    size_1000_plus = "size_1000_plus"  # strong prior for ERISA self-funded (~80%)
    unknown = "unknown"


class MarketplaceType(str, Enum):
    subsidized = "subsidized"      # HealthCare.gov / state exchange with subsidy
    off_exchange = "off_exchange"  # directly from insurer, no subsidy
    unknown = "unknown"


class WizardRequest(BaseModel):
    source: PlanSource
    employer_plan_type: EmployerPlanType | None = None
    employer_size: EmployerSize | None = None
    marketplace_type: MarketplaceType | None = None
    state: str = "IN"
    # Set to True when the extracted denial letter explicitly cites ERISA § 503
    erisa_citation_in_denial: bool = False


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
    # How the regulation_type was determined — displayed in the assumptions panel
    regulation_type_source: str = "user"       # "user" | "extracted" | "defaulted"
    assumption_note: str = ""                  # human-readable explanation of any assumption made


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
# Routing logic — applicable_laws[] populated at request time from live eCFR API
# ---------------------------------------------------------------------------


async def _merge_dynamic_laws(resp: WizardResponse, profile: str) -> WizardResponse:
    """profile: erisa | state_aca | medicaid"""
    try:
        laws = await fetch_applicable_laws_for_profile(profile)
        if laws:
            resp.applicable_laws = laws
    except Exception as e:
        logger.warning("Live regulatory fetch failed (%s): %s", profile, e)
    return resp


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
        applicable_laws=[],
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
        applicable_laws=[],
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
        applicable_laws=[],
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
        applicable_laws=[],
        state_specific=state_doi,
    )


def _employer_size_suggests_erisa(size: EmployerSize | None) -> bool:
    """Large employers (1000+) self-fund ~80% of the time → strong ERISA prior."""
    return size == EmployerSize.size_1000_plus


@router.post("/plan-type", response_model=WizardResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def plan_type_wizard(request: Request, body: WizardRequest) -> WizardResponse:
    state = body.state.upper() if body.state else "IN"

    # ERISA citation override: if the denial letter explicitly cites ERISA § 503,
    # trust the extracted evidence over the wizard's answer.
    if body.erisa_citation_in_denial:
        resp = _build_erisa_response(state)
        resp = await _merge_dynamic_laws(resp, "erisa")
        resp.regulation_type_source = "extracted"
        resp.assumption_note = (
            "Your denial letter explicitly cites ERISA § 503. "
            "We are treating this plan as ERISA-governed (overrides your wizard selection)."
        )
        return resp

    if body.source == PlanSource.employer:
        emp_type = body.employer_plan_type or EmployerPlanType.unknown

        if emp_type == EmployerPlanType.erisa:
            resp = await _merge_dynamic_laws(_build_erisa_response(state), "erisa")
            resp.regulation_type_source = "user"
            return resp

        elif emp_type == EmployerPlanType.fully_insured:
            resp = await _merge_dynamic_laws(_build_state_response(state), "state_aca")
            resp.regulation_type_source = "user"
            return resp

        else:
            # employer_type = unknown: apply Bayesian update from employer_size.
            # Large employers (1000+) self-fund ~80% → default to ERISA.
            # Otherwise default to fully-insured (state-regulated): ~60% of employer plans.
            if _employer_size_suggests_erisa(body.employer_size):
                resp = await _merge_dynamic_laws(_build_erisa_response(state), "erisa")
                resp.regulation_type_source = "defaulted"
                resp.assumption_note = (
                    "We assumed ERISA self-funded based on your employer size (1,000+ employees). "
                    "Large employers self-fund ~80% of health plans. "
                    "Verify with your HR department — if the plan is fully insured, "
                    "re-run this wizard selecting 'Fully insured (state-regulated)'."
                )
                resp.applicable_laws = list(resp.applicable_laws) + [
                    {
                        "law": "Plan type assumed — ERISA self-funded (large employer)",
                        "section": "Verify with HR / Summary Plan Description",
                        "relevance": resp.assumption_note,
                        "url": "https://www.dol.gov/agencies/ebsa",
                        "source": "U.S. Department of Labor (EBSA)",
                    }
                ]
                return resp
            else:
                resp = _build_state_response(state)
                resp = await _merge_dynamic_laws(resp, "state_aca")
                resp.regulation_type_source = "defaulted"
                resp.assumption_note = (
                    "We assumed your employer plan is fully insured (state-regulated) "
                    "because most employer plans are (~60%). "
                    "If your employer has 1,000+ employees and the plan is ERISA self-funded, "
                    "re-run this wizard selecting 'ERISA self-funded' — ERISA plans have "
                    "different appeal rules (DOL EBSA regulates; external review may not apply)."
                )
                resp.applicable_laws = list(resp.applicable_laws) + [
                    {
                        "law": "Plan type assumed — fully insured (state-regulated)",
                        "section": "Verify SPD / plan documents",
                        "relevance": resp.assumption_note,
                        "url": "https://www.dol.gov/agencies/ebsa",
                        "source": "U.S. Department of Labor (EBSA)",
                    }
                ]
                return resp

    elif body.source == PlanSource.marketplace:
        resp = await _merge_dynamic_laws(_build_state_response(state), "state_aca")
        resp.regulation_type_source = "user"
        if body.marketplace_type == MarketplaceType.subsidized:
            resp.assumption_note = (
                "Subsidized marketplace plans (HealthCare.gov / state exchange) are ACA-compliant "
                "and subject to full external review requirements."
            )
        elif body.marketplace_type == MarketplaceType.off_exchange:
            resp.assumption_note = (
                "Off-exchange individual plans must still comply with ACA requirements "
                "including internal and external appeal rights."
            )
        return resp

    elif body.source == PlanSource.medicaid:
        resp = await _merge_dynamic_laws(_build_medicaid_response(state), "medicaid")
        resp.regulation_type_source = "user"
        return resp

    elif body.source == PlanSource.individual:
        resp = await _merge_dynamic_laws(_build_individual_response(state), "state_aca")
        resp.regulation_type_source = "user"
        return resp

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown plan source.")
