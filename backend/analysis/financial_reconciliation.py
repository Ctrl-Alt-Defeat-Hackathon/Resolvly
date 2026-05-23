"""
Financial Reconciliation (§5.2)

Verifies internal consistency of extracted financial figures and emits
discrepancy assumptions when the equations don't balance within tolerance.

Equations checked:
  1. patient_responsibility_total ≈ copay + coinsurance + deductible
  2. insurer_paid + patient_responsibility ≈ allowed_amount
  3. implied_adjustment = billed - allowed - denied  (flag if negative)
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from extraction.schema import ClaimObject

logger = logging.getLogger(__name__)

_TOLERANCE_DOLLARS = 1.00   # $1.00 rounding tolerance


class FinancialReconciliationResult(BaseModel):
    reconciled: bool = True
    discrepancies: list[str] = []
    assumptions: list[dict[str, Any]] = []
    implied_adjustment: float | None = None


def _fmt(v: float) -> str:
    return f"${v:,.2f}"


def check_financial_reconciliation(claim: ClaimObject) -> FinancialReconciliationResult:
    f = claim.financial
    result = FinancialReconciliationResult()

    # Equation 1: patient responsibility breakdown
    copay = f.copay_amount or 0.0
    coins = f.coinsurance_amount or 0.0
    ded = f.deductible_applied or 0.0
    resp_total = f.patient_responsibility_total

    components_present = any([f.copay_amount, f.coinsurance_amount, f.deductible_applied])
    if resp_total is not None and components_present:
        computed = copay + coins + ded
        diff = abs(resp_total - computed)
        if diff > _TOLERANCE_DOLLARS:
            msg = (
                f"Patient responsibility total ({_fmt(resp_total)}) does not match "
                f"copay + coinsurance + deductible "
                f"({_fmt(copay)} + {_fmt(coins)} + {_fmt(ded)} = {_fmt(computed)}). "
                f"Gap: {_fmt(diff)}. Verify EOB line items."
            )
            result.reconciled = False
            result.discrepancies.append(msg)
            result.assumptions.append({
                "assumption": msg,
                "confidence": 0.90,
                "impact": "medium",
                "category": "financial_reconciliation",
            })
            logger.warning("Financial reconciliation: eq1 mismatch — %s", msg)

    # Equation 2: insurer paid + patient responsibility ≈ allowed amount
    paid = f.insurer_paid_amount
    allowed = f.allowed_amount
    if paid is not None and resp_total is not None and allowed is not None:
        computed2 = paid + resp_total
        diff2 = abs(allowed - computed2)
        if diff2 > _TOLERANCE_DOLLARS:
            msg2 = (
                f"Insurer paid ({_fmt(paid)}) + patient responsibility ({_fmt(resp_total)}) "
                f"= {_fmt(computed2)}, but allowed amount is {_fmt(allowed)}. "
                f"Gap: {_fmt(diff2)}. Could indicate adjustments or write-offs not captured."
            )
            result.reconciled = False
            result.discrepancies.append(msg2)
            result.assumptions.append({
                "assumption": msg2,
                "confidence": 0.85,
                "impact": "medium",
                "category": "financial_reconciliation",
            })
            logger.warning("Financial reconciliation: eq2 mismatch — %s", msg2)

    # Equation 3: implied adjustment (billed - allowed - denied)
    billed = f.billed_amount
    denied = f.denied_amount
    if billed is not None and allowed is not None:
        denied_v = denied or 0.0
        implied = billed - allowed - denied_v
        result.implied_adjustment = implied
        if implied < -_TOLERANCE_DOLLARS:
            msg3 = (
                f"Implied adjustment is negative ({_fmt(implied)}): "
                f"billed ({_fmt(billed)}) - allowed ({_fmt(allowed)}) - denied ({_fmt(denied_v)}) < 0. "
                f"Check for data entry errors or missing charge lines."
            )
            result.reconciled = False
            result.discrepancies.append(msg3)
            result.assumptions.append({
                "assumption": msg3,
                "confidence": 0.80,
                "impact": "low",
                "category": "financial_reconciliation",
            })
            logger.warning("Financial reconciliation: eq3 negative adjustment — %s", msg3)

    if result.reconciled:
        logger.info("Financial reconciliation: all equations balance within tolerance")
    else:
        logger.info(
            "Financial reconciliation: %d discrepancies found",
            len(result.discrepancies),
        )

    return result
