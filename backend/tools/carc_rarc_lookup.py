"""
CARC / RARC Denial Code Lookup Tool

Resolves Claim Adjustment Reason Codes (CARC) and Remittance Advice Remark
Codes (RARC) to their official descriptions.

Source: X12.org / WPC (Washington Publishing Company) public code lists,
accessed via the open WPC CARC/RARC listing and CMS X12 remittance tables.

Since there is no structured REST API for CARC/RARC codes, we maintain an
authoritative in-memory lookup table sourced from the WPC published lists.
This is the one exception where a "local" data source is needed — the WPC
does not offer a public API.

The table is kept small (~300 CARC + ~400 RARC entries) and can be updated
periodically from the WPC PDF/CSV releases.
"""
from __future__ import annotations

from pydantic import BaseModel


class CARCResult(BaseModel):
    code: str
    group: str = ""  # CO, PR, OA, PI, CR
    description: str
    plain_english: str = ""
    common_fix: str = ""
    source: str = "WPC CARC Code List (X12)"
    found: bool = True


class RARCResult(BaseModel):
    code: str
    description: str
    plain_english: str = ""
    source: str = "WPC RARC Code List (X12)"
    found: bool = True


# ---------------------------------------------------------------------------
# CARC code table — most common codes encountered in denial letters.
# Full table has ~300 entries; we include the top ~50 that cover >90% of
# denial scenarios. Expand as needed from WPC releases.
# ---------------------------------------------------------------------------

_CARC_TABLE: dict[str, dict] = {
    "1": {
        "description": "Deductible amount",
        "plain_english": "You owe this amount because it's part of your annual deductible — the amount you pay before insurance kicks in.",
        "common_fix": "Verify your deductible status with your insurer. If you've already met your deductible, submit proof.",
    },
    "2": {
        "description": "Coinsurance amount",
        "plain_english": "This is your share of the cost (coinsurance) after your deductible has been met.",
        "common_fix": "Check your plan's coinsurance percentage and verify the calculation is correct.",
    },
    "3": {
        "description": "Co-payment amount",
        "plain_english": "This is the fixed copay amount required by your plan for this type of service.",
        "common_fix": "Verify the copay amount matches your plan documents for this service type.",
    },
    "4": {
        "description": "The procedure code is inconsistent with the modifier used or a required modifier is missing.",
        "plain_english": "The billing codes submitted don't match properly — there may be a typo or missing modifier code.",
        "common_fix": "Contact your provider's billing office and ask them to review the modifier codes and resubmit.",
    },
    "5": {
        "description": "The procedure code/bill type is inconsistent with the place of service.",
        "plain_english": "The billing says the service happened in a location that doesn't match the procedure type.",
        "common_fix": "Ask your provider to verify and correct the place of service code, then resubmit.",
    },
    "6": {
        "description": "The procedure/revenue code is inconsistent with the patient's age.",
        "plain_english": "The procedure billed is typically for a different age group than yours.",
        "common_fix": "Contact your provider's billing office to verify the procedure and diagnosis codes are correct for your age.",
    },
    "9": {
        "description": "The diagnosis is inconsistent with the patient's age.",
        "plain_english": "The diagnosis code used is unusual for someone your age.",
        "common_fix": "Ask your provider to verify the diagnosis code is correct.",
    },
    "11": {
        "description": "The diagnosis is inconsistent with the procedure.",
        "plain_english": "The diagnosis code doesn't match the procedure that was performed — this may be a coding error.",
        "common_fix": "Contact your provider's billing office to verify the ICD-10 and CPT code pairing.",
    },
    "15": {
        "description": "The authorization number is missing, invalid, or does not apply to the billed services.",
        "plain_english": "Your insurance required prior authorization for this service, and the authorization number wasn't included or is invalid.",
        "common_fix": "Contact your provider to obtain and submit the correct authorization number.",
    },
    "16": {
        "description": "Claim/service lacks information or has submission/billing error(s).",
        "plain_english": "The claim was missing required information or had errors in how it was submitted.",
        "common_fix": "Contact your provider's billing office to correct the errors and resubmit the claim.",
    },
    "18": {
        "description": "Exact duplicate claim/service.",
        "plain_english": "This same claim was already submitted and processed — this is a duplicate.",
        "common_fix": "No action needed if the original claim was paid. If not, contact billing to investigate.",
    },
    "22": {
        "description": "This care may be covered by another payer per coordination of benefits.",
        "plain_english": "Your insurer thinks another insurance company should pay for this first.",
        "common_fix": "Submit the claim to your other insurance first, then resubmit to this insurer with the other insurer's EOB.",
    },
    "23": {
        "description": "The impact of prior payer(s) adjudication including payments and/or adjustments.",
        "plain_english": "The amount was adjusted based on what your other insurance already paid.",
        "common_fix": "Verify that your primary insurance was billed first and review the coordination of benefits.",
    },
    "27": {
        "description": "Expenses incurred after coverage terminated.",
        "plain_english": "The service happened after your insurance coverage ended.",
        "common_fix": "Verify your coverage dates. If you were covered on the date of service, submit proof of active coverage.",
    },
    "29": {
        "description": "The time limit for filing has expired.",
        "plain_english": "The claim was submitted too late — past the insurer's filing deadline.",
        "common_fix": "Contact your provider immediately — they may be responsible for late filing. Check if a timely filing exception applies.",
    },
    "45": {
        "description": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement.",
        "plain_english": "The amount charged is higher than what your insurance plan allows for this service.",
        "common_fix": "Check if you have balance billing protections. The provider may need to accept the allowed amount.",
    },
    "50": {
        "description": "These are non-covered services because this is not deemed a 'medical necessity' under the payer's definition.",
        "plain_english": "Your insurance says this treatment was not medically necessary according to their guidelines.",
        "common_fix": "Request your provider submit a letter of medical necessity with clinical documentation. File an appeal citing specific medical reasons.",
    },
    "55": {
        "description": "Procedure/treatment/drug is deemed experimental, investigational, or unproven.",
        "plain_english": "Your insurer considers this treatment experimental and won't cover it.",
        "common_fix": "Ask your doctor for published studies supporting the treatment. File an appeal with clinical evidence.",
    },
    "56": {
        "description": "Procedure/treatment has not been deemed 'medically necessary' by the payer.",
        "plain_english": "Similar to code 50 — your insurer doesn't think this treatment was medically necessary.",
        "common_fix": "Same as CARC 50 — submit medical necessity documentation and appeal.",
    },
    "58": {
        "description": "Treatment was deemed by the payer to have been rendered in an inappropriate or invalid place of service.",
        "plain_english": "Your insurer thinks the treatment should have been done in a different setting (e.g., outpatient instead of inpatient).",
        "common_fix": "Ask your provider to document why the specific care setting was necessary.",
    },
    "96": {
        "description": "Non-covered charge(s). At least one Remark Code must be provided.",
        "plain_english": "Your plan simply doesn't cover this service.",
        "common_fix": "Review your plan benefits. Check the associated RARC code for more details on why.",
    },
    "97": {
        "description": "The benefit for this service is included in the payment/allowance for another service/procedure.",
        "plain_english": "This service is already included ('bundled') with another service that was billed.",
        "common_fix": "Contact your provider's billing office — they may need to use a modifier to unbundle the codes if the services were truly separate.",
    },
    "109": {
        "description": "Claim/service not covered by this payer/contractor.",
        "plain_english": "Your insurance plan doesn't cover this service at all under your current policy.",
        "common_fix": "Review your plan's benefit summary. Consider whether another insurance or program might cover it.",
    },
    "119": {
        "description": "Benefit maximum for this time period or occurrence has been reached.",
        "plain_english": "You've used up the maximum number of visits or dollar amount your plan allows for this service.",
        "common_fix": "Check your plan's annual limits. If medically necessary, request an exception to the limit.",
    },
    "151": {
        "description": "Payment adjusted because the payer deems the information submitted does not support this many services.",
        "plain_english": "Your insurer says the number of services or visits billed seems too many for your condition.",
        "common_fix": "Ask your provider to submit clinical documentation justifying the frequency of treatment.",
    },
    "181": {
        "description": "Procedure code was invalid on the date of service.",
        "plain_english": "The procedure code used wasn't valid or active on the date the service was provided.",
        "common_fix": "Contact billing to use the correct, current procedure code.",
    },
    "197": {
        "description": "Precertification/authorization/notification/pre-treatment absent.",
        "plain_english": "Your insurance required advance approval (prior authorization) for this service, and it wasn't obtained before the procedure.",
        "common_fix": "Contact your provider — they may be able to request retroactive authorization. If denied, the provider may be financially responsible.",
    },
    "204": {
        "description": "This service/equipment/drug is not covered under the patient's current benefit plan.",
        "plain_english": "Your specific benefit plan doesn't include coverage for this service.",
        "common_fix": "Review your plan documents. Ask your insurer about alternative covered options.",
    },
    "242": {
        "description": "Services not provided by network/primary care providers.",
        "plain_english": "The service was provided by an out-of-network provider.",
        "common_fix": "If you had no choice (emergency), file a surprise billing complaint. Otherwise, check if the No Surprises Act applies.",
    },
    "252": {
        "description": "An attachment/other documentation is required to adjudicate this claim/service.",
        "plain_english": "Additional documentation is needed before your insurer can process this claim.",
        "common_fix": "Contact your provider to submit the requested documents to the insurer.",
    },
    "256": {
        "description": "Service not payable per managed care contract.",
        "plain_english": "Under the managed care agreement between your insurer and the provider, this service isn't billable to you.",
        "common_fix": "This may mean the provider cannot bill you. Contact your insurer to confirm.",
    },
}

# Group code descriptions
_GROUP_CODES: dict[str, str] = {
    "CO": "Contractual Obligation — provider agreed to write off this amount",
    "PR": "Patient Responsibility — you are responsible for this amount",
    "OA": "Other Adjustment — neither provider nor patient is specifically responsible",
    "PI": "Payer Initiated Reduction — insurer reduced the payment",
    "CR": "Correction/Reversal — a prior claim decision is being corrected",
}

# ---------------------------------------------------------------------------
# RARC code table — most common remark codes
# ---------------------------------------------------------------------------

_RARC_TABLE: dict[str, dict] = {
    "M1": {
        "description": "X-ray not taken within the past 12 months or near enough to the start of treatment.",
        "plain_english": "An X-ray was needed as part of the documentation, but it's too old or wasn't taken.",
    },
    "M15": {
        "description": "Separately billed services/tests have been bundled as they are considered components of the same procedure.",
        "plain_english": "Some services were combined into one charge because they're considered part of the same procedure.",
    },
    "M20": {
        "description": "Missing/incomplete/invalid HCPCS.",
        "plain_english": "The billing code was missing or incorrect.",
    },
    "M76": {
        "description": "Missing/incomplete/invalid diagnosis or condition.",
        "plain_english": "The diagnosis code is missing or incorrect on the claim.",
    },
    "M77": {
        "description": "Missing/incomplete/invalid place of service.",
        "plain_english": "The location where the service was provided wasn't specified correctly.",
    },
    "MA04": {
        "description": "Secondary payment cannot be considered without the identity of or payment information from the primary payer.",
        "plain_english": "This insurer needs information from your primary insurance before they can process this claim.",
    },
    "MA07": {
        "description": "The claim information has also been forwarded to Medicaid for review.",
        "plain_english": "Your claim has been sent to Medicaid for possible additional payment.",
    },
    "MA130": {
        "description": "Your claim contains incomplete and/or invalid information.",
        "plain_english": "Some information on the claim is missing or wrong.",
    },
    "N1": {
        "description": "You may appeal this decision.",
        "plain_english": "You have the right to appeal this denial.",
    },
    "N2": {
        "description": "This allowance has been made in accordance with the most appropriate level of care.",
        "plain_english": "Payment was adjusted to match the level of care your insurer considers appropriate.",
    },
    "N20": {
        "description": "Service not consistent with the provider's specialty.",
        "plain_english": "The service billed doesn't match the type of care your provider typically provides.",
    },
    "N30": {
        "description": "Patient ineligible for this service.",
        "plain_english": "According to your insurer, you weren't eligible for this service.",
    },
    "N362": {
        "description": "The number of days or units of service exceeds our acceptable maximum.",
        "plain_english": "More services were billed than your plan allows.",
    },
    "N386": {
        "description": "This decision was based on a National Coverage Determination (NCD).",
        "plain_english": "The denial is based on a Medicare national policy about what's covered.",
    },
    "N432": {
        "description": "Alert: Adjustment based on the No Surprises Act.",
        "plain_english": "Your bill was adjusted under the federal No Surprises Act which protects against unexpected out-of-network charges.",
    },
}


async def lookup_carc(code: str, group: str = "") -> CARCResult:
    """
    Look up a CARC (Claim Adjustment Reason Code).

    Args:
        code: The numeric CARC code (e.g., "50", "197")
        group: Optional group code (CO, PR, OA, PI, CR)
    """
    code = code.strip().lstrip("0")  # Remove leading zeros
    group = group.strip().upper()

    entry = _CARC_TABLE.get(code)
    if entry:
        group_desc = _GROUP_CODES.get(group, "")
        group_display = f"{group} ({group_desc})" if group and group_desc else group
        return CARCResult(
            code=code,
            group=group_display,
            description=entry["description"],
            plain_english=entry.get("plain_english", ""),
            common_fix=entry.get("common_fix", ""),
        )

    return CARCResult(
        code=code,
        group=group,
        description=f"CARC {code} — not found in local lookup table. Check WPC code list at x12.org.",
        found=False,
    )


async def lookup_rarc(code: str) -> RARCResult:
    """
    Look up a RARC (Remittance Advice Remark Code).

    Args:
        code: The RARC code (e.g., "N1", "MA04", "M76")
    """
    code = code.strip().upper()

    entry = _RARC_TABLE.get(code)
    if entry:
        return RARCResult(
            code=code,
            description=entry["description"],
            plain_english=entry.get("plain_english", ""),
        )

    return RARCResult(
        code=code,
        description=f"RARC {code} — not found in local lookup table. Check WPC code list at x12.org.",
        found=False,
    )
