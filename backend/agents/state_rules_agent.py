"""
State Rules Agent

Fetches state-specific insurance regulations, external review procedures,
and consumer resources. Indiana-first implementation with full 50-state
DOI contact support.

Input:  ClaimObject (with state/regulation type)
Output: StateRulesEnrichment
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from extraction.schema import ClaimObject, RegulationType
from tools.idoi_search import search_idoi, IDOIResult
from tools.state_doi_lookup import get_doi_contact

logger = logging.getLogger(__name__)


class StateRulesEnrichment(BaseModel):
    state: str = ""
    doi_contact: dict[str, Any] = {}
    appeal_rules: list[str] = []
    state_deadlines: dict[str, str] = {}
    consumer_resources: list[dict] = []
    external_review_available: bool = False
    external_review_url: str = ""
    regulatory_routing: str = ""   # "erisa_federal" | "state_doi" | "medicaid_state"
    routing_reason: str = ""


def _determine_routing(
    regulation_type: RegulationType,
    state: str,
) -> tuple[str, str]:
    """
    Determine whether this claim is routed to federal ERISA, state DOI, or Medicaid.
    Returns (routing_key, routing_reason).
    """
    if regulation_type == RegulationType.erisa:
        return (
            "erisa_federal",
            "This plan is governed by ERISA (self-funded employer plan). "
            "State insurance regulations do NOT apply. "
            "Appeals go to the plan administrator. "
            "Federal court (ERISA § 502) is the ultimate recourse.",
        )
    elif regulation_type == RegulationType.medicaid:
        return (
            "medicaid_state",
            f"This is a Medicaid claim. "
            f"Contact your state Medicaid agency for a fair hearing under 42 CFR § 431.220.",
        )
    else:
        # State-regulated (fully insured, marketplace, individual)
        doi = get_doi_contact(state)
        doi_name = doi.get("name", f"{state} Department of Insurance") if doi else f"{state} Department of Insurance"
        return (
            "state_doi",
            f"This plan is state-regulated (fully insured, marketplace, or individual market). "
            f"The {doi_name} oversees this plan. "
            f"You have the right to file a complaint and request external review.",
        )


async def run_state_rules_agent(claim: ClaimObject) -> StateRulesEnrichment:
    """
    Fetch state-specific rules and DOI information for this claim.
    """
    state = (claim.identification.plan_jurisdiction or "IN").upper().strip()
    regulation_type = claim.identification.erisa_or_state_regulated or RegulationType.unknown

    routing, routing_reason = _determine_routing(regulation_type, state)
    enrichment = StateRulesEnrichment(
        state=state,
        regulatory_routing=routing,
        routing_reason=routing_reason,
    )

    # Always fetch DOI contact (useful even for ERISA plans — state AG may have jurisdiction)
    idoi_result: IDOIResult = await search_idoi(state=state)

    if idoi_result.found:
        enrichment.doi_contact = {
            "name": idoi_result.doi_name,
            "phone": idoi_result.doi_phone,
            "address": idoi_result.doi_address,
            "complaint_url": idoi_result.doi_complaint_url,
            "website": idoi_result.doi_website,
            "external_review_url": idoi_result.external_review_url,
            "consumer_guide_url": idoi_result.consumer_guide_url,
        }
        enrichment.external_review_available = idoi_result.external_review_available
        enrichment.external_review_url = idoi_result.external_review_url
        enrichment.consumer_resources = idoi_result.consumer_resources

        # Only include state-specific appeal rules if plan is state-regulated
        if regulation_type != RegulationType.erisa:
            enrichment.appeal_rules = idoi_result.appeal_rules
            enrichment.state_deadlines = idoi_result.state_deadlines
        else:
            # For ERISA: DOI is not the regulator, but state AG may help
            enrichment.appeal_rules = [
                "ERISA self-funded plans are not regulated by the state DOI",
                "However, you may contact the state DOI for general guidance",
                "The U.S. Department of Labor (DOL) EBSA handles ERISA complaints",
                f"DOL EBSA: 1-866-444-3272 | https://www.dol.gov/agencies/ebsa",
                "If the employer plan is fully insured (insurance company underwrites it), "
                "state DOI rules DO apply — verify plan type with your HR department",
            ]

    logger.info(
        f"State Rules Agent complete: state={state}, routing={routing}, "
        f"doi_found={idoi_result.found}"
    )
    return enrichment
