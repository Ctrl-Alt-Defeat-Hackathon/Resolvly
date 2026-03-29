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

    # Run regulation lookups in parallel
    tasks = []

    if regulation_type == RegulationType.erisa:
        tasks.append(("erisa", search_erisa(plan_type="erisa", denial_type=denial_type)))
        tasks.append(("ecfr_erisa", search_ecfr(
            query="ERISA claims procedure appeal 503",
            cfr_section="29 CFR 2560.503-1",
        )))
    elif regulation_type in (RegulationType.state, RegulationType.unknown):
        tasks.append(("aca", search_aca_provisions(plan_type="aca", denial_type=denial_type)))
        tasks.append(("ecfr_aca", search_ecfr(
            query="ACA internal external review 2719",
            cfr_section="45 CFR 147.136",
        )))
    elif regulation_type == RegulationType.medicaid:
        tasks.append(("ecfr_medicaid", search_ecfr(
            query="Medicaid fair hearing adverse action",
            cfr_section="42 CFR 431.220",
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

        elif name in ("ecfr_erisa", "ecfr_aca", "ecfr_medicaid"):
            if result.found and result.excerpt:
                enrichment.raw_texts.append(result.excerpt)
                enrichment.applicable_laws.append(LegalCitation(
                    law=result.cfr_reference,
                    section=result.cfr_reference,
                    relevance=result.title,
                    url=result.url,
                ))
            # Medicaid-specific defaults
            if name == "ecfr_medicaid":
                enrichment.internal_appeal_deadline_days = 90
                enrichment.appeal_process = [
                    "Request a Medicaid fair hearing within 90 days of the denial notice",
                    "Submit hearing request to your state Medicaid agency",
                    "Benefits must continue pending hearing if requested within 10 days of notice",
                    "Hearing must be held within 90 days of your request",
                    "You may bring legal representation or an authorized representative",
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
