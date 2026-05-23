"""
Regulation Agent

Fetches the specific federal regulations and legal provisions relevant to
this claim based on regulation type and denial category.

Input:  ClaimObject (with plan type and root cause)
Output: RegulationEnrichment (applicable laws, appeal rules, deadlines, citations)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from extraction.schema import ClaimObject, RegulationType, RootCauseCategory
from tools.ecfr_search import search_ecfr
from tools.erisa_search import search_erisa, ERISAResult
from tools.aca_search import search_aca_provisions, ACAResult
from tools.cms_coverage import search_cms_coverage

logger = logging.getLogger(__name__)


class LegalCitation(BaseModel):
    law: str
    section: str
    relevance: str
    url: str = ""
    quoted_text: str = ""    # verbatim 1-2 sentence excerpt for appeal letter citations
    last_verified: str = ""  # ISO date string — when the cached text was last checked against eCFR


class RegulationEnrichment(BaseModel):
    regulation_type: str = ""
    applicable_laws: list[LegalCitation] = []
    appeal_rules: dict[str, Any] = {}
    appeal_process: list[str] = []
    internal_appeal_deadline_days: int = 180
    plan_review_deadline_days: int = 60
    expedited_turnaround_hours: int = 72
    external_review_available: bool = False
    required_notice_elements: list[str] = []
    coverage_determination: str = ""
    coverage_url: str = ""
    legal_citations: list[dict] = []
    raw_texts: list[str] = []


# HCPCS codes that indicate air ambulance (trigger NSA IDR process)
_NSA_AIR_AMBULANCE_HCPCS = frozenset({"A0430", "A0431"})
# Place of service codes for emergency department
_NSA_EMERGENCY_POS = frozenset({"23"})


def _is_nsa_eligible(claim: ClaimObject) -> bool:
    """
    Return True when the No Surprises Act IDR process applies instead of standard
    internal appeal.  Triggers when root_cause is network_coverage AND the claim
    involves an emergency (POS 23) or air ambulance, or is explicitly out-of-network.
    """
    if claim.derived.root_cause_category != RootCauseCategory.network_coverage:
        return False
    pos = claim.service_billing.place_of_service_code or ""
    hcpcs = set(claim.service_billing.hcpcs_codes)
    network = (claim.patient_provider.network_status or "").lower()
    return (
        pos in _NSA_EMERGENCY_POS
        or bool(hcpcs & _NSA_AIR_AMBULANCE_HCPCS)
        or "out-of-network" in network
    )


async def run_regulation_agent(claim: ClaimObject) -> RegulationEnrichment:
    """
    Fetch federal regulations relevant to this claim.

    Dispatches different regulation tools based on plan type:
      - ERISA:       search_erisa + eCFR 29 CFR § 2560.503-1
      - ACA/state:   search_aca_provisions + eCFR 45 CFR § 147.136
      - Medicaid:    eCFR 42 CFR § 431.220
      - Med necessity: CMS Coverage Database
    """
    regulation_type = claim.identification.erisa_or_state_regulated or RegulationType.unknown
    root_cause = claim.derived.root_cause_category

    enrichment = RegulationEnrichment(regulation_type=regulation_type.value)

    # Determine denial type for deadline adjustments
    denial_type = ""
    if root_cause == RootCauseCategory.prior_authorization:
        denial_type = "prior_authorization"

    # NSA check — routes entire appeal to IDR process, not standard internal appeal
    nsa_eligible = _is_nsa_eligible(claim)
    if nsa_eligible:
        logger.info("Regulation Agent: No Surprises Act IDR process applies (network/emergency claim)")
        enrichment.applicable_laws.append(LegalCitation(
            law="No Surprises Act",
            section="45 CFR § 149.510",
            relevance=(
                "Federal Independent Dispute Resolution (IDR) process applies to "
                "out-of-network emergency and air ambulance claims. Standard internal "
                "appeal may still be filed but the IDR process runs in parallel."
            ),
            url="https://www.cms.gov/nosurprises",
            quoted_text=(
                "Under the No Surprises Act, patients are protected from surprise "
                "medical bills for emergency services and certain non-emergency services "
                "at in-network facilities provided by out-of-network providers."
            ),
            last_verified="2025-01-01",
        ))
        enrichment.appeal_process = [
            "You are protected by the No Surprises Act — your cost-sharing is limited to in-network amounts.",
            "Submit a dispute to the Federal Independent Dispute Resolution (IDR) portal at cms.gov/nosurprises.",
            "The IDR process must be initiated within 4 business days after the 30-day open negotiation period expires.",
            "You may still file a standard internal appeal with your insurer in parallel.",
            "File a complaint with the No Surprises Help Desk at 1-800-985-3059 if the insurer violates NSA protections.",
        ]
        enrichment.external_review_available = True

    # Run regulation lookups in parallel
    tasks = []

    if regulation_type == RegulationType.erisa:
        tasks.append(("erisa", search_erisa(plan_type="erisa", denial_type=denial_type)))
        tasks.append(("ecfr_erisa_503", search_ecfr(
            query="ERISA claims procedure appeal 503",
            cfr_section="29 CFR 2560.503-1",
        )))
        # ACA labor-side parallel rule (applies to ERISA plans subject to ACA)
        tasks.append(("ecfr_erisa_2719", search_ecfr(
            query="ACA internal external claims review ERISA group health plans",
            cfr_section="29 CFR 2590.715-2719",
        )))
    elif regulation_type in (RegulationType.state, RegulationType.unknown):
        tasks.append(("aca", search_aca_provisions(plan_type="aca", denial_type=denial_type)))
        tasks.append(("ecfr_aca_147", search_ecfr(
            query="ACA internal external review 2719",
            cfr_section="45 CFR 147.136",
        )))
        # ACA tax-side parallel rule
        tasks.append(("ecfr_aca_tax", search_ecfr(
            query="ACA internal external review group health plans tax",
            cfr_section="26 CFR 54.9815-2719",
        )))
        # Essential health benefits (relevant to medical necessity denials)
        tasks.append(("ecfr_ehb", search_ecfr(
            query="essential health benefits coverage requirements",
            cfr_section="45 CFR 156.122",
        )))
    elif regulation_type == RegulationType.medicaid:
        tasks.append(("ecfr_medicaid_431", search_ecfr(
            query="Medicaid fair hearing adverse action",
            cfr_section="42 CFR 431.220",
        )))
        # Medicaid managed care appeals (distinct from fair hearing)
        tasks.append(("ecfr_medicaid_438", search_ecfr(
            query="Medicaid managed care organization appeal grievance",
            cfr_section="42 CFR 438.402",
        )))

    # Always look up CMS coverage if medical necessity denial
    if root_cause == RootCauseCategory.medical_necessity:
        tasks.append(("cms_coverage", search_cms_coverage(
            procedure_description=claim.service_billing.procedure_description or "",
            cpt_codes=claim.service_billing.cpt_procedure_codes,
            icd10_codes=claim.service_billing.icd10_diagnosis_codes,
        )))

    if not tasks:
        logger.warning("No regulation tasks dispatched — unknown regulation type")
        return enrichment

    logger.info(f"Regulation Agent: running {len(tasks)} lookups in parallel")
    names = [t[0] for t in tasks]
    coroutines = [t[1] for t in tasks]
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    for name, result in zip(names, results):
        if isinstance(result, Exception):
            logger.error(f"Regulation lookup '{name}' failed: {result}")
            continue

        if name == "erisa":
            erisa: ERISAResult = result
            enrichment.appeal_process = erisa.appeal_process
            enrichment.internal_appeal_deadline_days = erisa.internal_appeal_deadline_days
            enrichment.plan_review_deadline_days = erisa.plan_review_deadline_days
            enrichment.expedited_turnaround_hours = erisa.expedited_turnaround_hours
            enrichment.required_notice_elements = erisa.required_notice_elements
            enrichment.legal_citations.extend(erisa.legal_citations)
            if erisa.raw_text:
                enrichment.raw_texts.append(erisa.raw_text)
            for citation in erisa.legal_citations:
                enrichment.applicable_laws.append(LegalCitation(**citation))

        elif name == "aca":
            aca: ACAResult = result
            enrichment.appeal_process = aca.appeal_process
            enrichment.internal_appeal_deadline_days = aca.internal_appeal_deadline_days
            enrichment.plan_review_deadline_days = aca.plan_internal_review_deadline_days
            enrichment.expedited_turnaround_hours = aca.expedited_turnaround_hours
            enrichment.external_review_available = aca.external_review_available
            enrichment.required_notice_elements = aca.required_notice_elements
            enrichment.legal_citations.extend(aca.legal_citations)
            if aca.raw_text:
                enrichment.raw_texts.append(aca.raw_text)
            for citation in aca.legal_citations:
                enrichment.applicable_laws.append(LegalCitation(**citation))

        elif name in (
            "ecfr_erisa_503", "ecfr_erisa_2719",
            "ecfr_aca_147", "ecfr_aca_tax", "ecfr_ehb",
            "ecfr_medicaid_431", "ecfr_medicaid_438",
        ):
            if result.found and result.excerpt:
                enrichment.raw_texts.append(result.excerpt)
                enrichment.applicable_laws.append(LegalCitation(
                    law=result.cfr_reference,
                    section=result.cfr_reference,
                    relevance=result.title,
                    url=result.url,
                    quoted_text=result.excerpt[:500] if result.excerpt else "",
                ))
            # Medicaid managed care defaults (42 CFR § 438.402)
            if name == "ecfr_medicaid_438" and result.found:
                enrichment.applicable_laws.append(LegalCitation(
                    law="42 CFR § 438.402",
                    section="42 CFR § 438.402",
                    relevance="Medicaid managed care organization (MCO) appeal and grievance procedures — precede state fair hearing",
                    url=result.url,
                    last_verified="2025-01-01",
                ))
            # Medicaid fair hearing defaults (42 CFR § 431.220)
            if name == "ecfr_medicaid_431":
                enrichment.internal_appeal_deadline_days = 90
                enrichment.appeal_process = [
                    "If enrolled in Medicaid managed care (MCO/HMO), first file an internal appeal with your MCO (deadline: 60 days from denial).",
                    "If MCO appeal is denied, request a Medicaid fair hearing from your state Medicaid agency within 90 days of the denial.",
                    "Submit hearing request to your state Medicaid agency in writing.",
                    "Benefits must continue pending hearing if requested within 10 days of notice.",
                    "Hearing must be held within 90 days of your request.",
                    "You may bring legal representation or an authorized representative.",
                ]

        elif name == "cms_coverage":
            if result.found:
                enrichment.coverage_determination = result.coverage_determination
                enrichment.coverage_url = result.coverage_url
                if result.ncd_title:
                    enrichment.applicable_laws.append(LegalCitation(
                        law="CMS NCD",
                        section=result.ncd_id or "NCD",
                        relevance=f"CMS National Coverage Determination: {result.ncd_title}",
                        url=result.coverage_url,
                    ))

    logger.info(
        f"Regulation Agent complete: {len(enrichment.applicable_laws)} laws, "
        f"{len(enrichment.appeal_process)} process steps"
    )
    return enrichment
