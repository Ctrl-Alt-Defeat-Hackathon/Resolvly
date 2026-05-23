"""
Structured error types for the analysis pipeline (§7).

ClaimGap — 422 response body when critical fields are missing from the
extracted ClaimObject before the orchestrator can run meaningfully.

Only four fields are truly "blocking" — the pipeline can produce a
partial-but-useful result without everything else.
"""
from __future__ import annotations

from pydantic import BaseModel

from extraction.schema import ClaimObject


class ClaimGapField(BaseModel):
    field_name: str
    display_label: str
    where_to_look: str
    regulation_basis: str


class ClaimGap(BaseModel):
    upload_id: str
    missing_fields: list[ClaimGapField]
    can_proceed_partial: bool = False


# Fields whose absence blocks meaningful analysis
_BLOCKING_FIELDS: list[ClaimGapField] = [
    ClaimGapField(
        field_name="date_of_denial",
        display_label="Date of Denial",
        where_to_look="Look for 'Date of Denial' or 'Denial Date' near the top of the denial letter or EOB.",
        regulation_basis="Required to compute internal appeal deadline (29 C.F.R. §2560.503-1(g)(1)(i) / ACA §2719)",
    ),
    ClaimGapField(
        field_name="denial_reason_narrative",
        display_label="Denial Reason",
        where_to_look="Look for a paragraph starting with 'This claim was denied because…' or 'Reason for denial:'.",
        regulation_basis="Required for root-cause classification and appeal letter drafting (29 C.F.R. §2560.503-1(g)(1)(ii))",
    ),
    ClaimGapField(
        field_name="claim_reference_number",
        display_label="Claim / Reference Number",
        where_to_look="Usually printed near the top of the EOB as 'Claim #', 'Reference #', or 'ICN'.",
        regulation_basis="Required to identify the specific claim being appealed (insurer and regulatory correspondence)",
    ),
    ClaimGapField(
        field_name="regulation_type",
        display_label="Regulation Type (ERISA vs. State)",
        where_to_look="Complete the plan-type wizard, or look for 'self-funded', 'ERISA', or the insurer's state of incorporation.",
        regulation_basis="Determines which appeal deadlines, external review rights, and regulations apply",
    ),
]


def check_blocking_fields(claim: ClaimObject) -> ClaimGap | None:
    """
    Return a ClaimGap if any blocking field is missing; None if the claim is ready.

    Blocking criteria:
      - date_of_denial        : None
      - denial_reason_narrative: None or empty string
      - claim_reference_number : None or empty string
      - regulation_type        : None (i.e., the wizard was not completed and extraction failed)
    """
    missing: list[ClaimGapField] = []

    if claim.identification.date_of_denial is None:
        missing.append(_BLOCKING_FIELDS[0])

    narrative = claim.denial_reason.denial_reason_narrative
    if not narrative or not narrative.strip():
        missing.append(_BLOCKING_FIELDS[1])

    ref = claim.identification.claim_reference_number
    if not ref or not ref.strip():
        missing.append(_BLOCKING_FIELDS[2])

    if claim.identification.erisa_or_state_regulated is None:
        missing.append(_BLOCKING_FIELDS[3])

    if not missing:
        return None

    # Allow partial proceed only when exactly one non-critical field is absent
    # (regulation_type alone — the pipeline can still produce deadlines for both paths)
    can_partial = (
        len(missing) == 1
        and missing[0].field_name == "regulation_type"
    )

    return ClaimGap(
        upload_id=claim.upload_id,
        missing_fields=missing,
        can_proceed_partial=can_partial,
    )
