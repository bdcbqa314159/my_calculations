"""
Loan RWA Calculator

Unified calculator for all capital charges associated with a loan position:
- Credit Risk (SA-CR or IRB) on the borrower
- Credit Risk Mitigation (CRM) via collateral, guarantees, credit derivatives
- Credit Conversion Factors (CCF) for undrawn commitments
- No CCR or CVA (loans are not derivatives)
- No Market Risk (banking book)

Usage:
    from loan_rwa import calculate_loan_rwa, quick_loan_rwa, LoanTrade

    result = quick_loan_rwa(50_000_000, drawn=30_000_000, pd=0.01, maturity=3.0)
    print(result["total_rwa"])
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from rwa_calc import calculate_rwa, calculate_sa_rwa, calculate_airb_rwa
from ratings import RATING_TO_PD, resolve_pd, resolve_rating_log_scale
from capital_framework import calculate_ead_off_balance_sheet, calculate_exposure_with_crm


# =============================================================================
# Data model
# =============================================================================

@dataclass
class LoanTrade:
    """All parameters describing a loan position for RWA purposes."""

    # Core economics
    total_commitment: float = 50_000_000
    drawn_amount: float = 50_000_000
    maturity: float = 3.0
    is_revolving: bool = False

    # Borrower
    borrower_pd: Optional[float] = None
    borrower_rating: Optional[str] = None
    borrower_sector: str = "corporate"
    is_sme: bool = False
    sales_turnover: Optional[float] = None  # EUR millions, for SME adjustment

    # Collateral & guarantees
    collateral: list = field(default_factory=list)   # list of dicts
    guarantee_value: float = 0.0
    guarantor_rw: Optional[float] = None

    # Regulatory treatment
    approach: str = "sa"              # "sa", "firb", "airb"
    commitment_type: str = "commitment_over_1y"
    borrower_lgd: Optional[float] = None  # bank-estimated LGD for A-IRB


# =============================================================================
# Component calculators
# =============================================================================

def calculate_loan_ead(trade: LoanTrade) -> dict:
    """
    Calculate EAD for a loan, including undrawn commitments.

    EAD = drawn + CCF * undrawn
    """
    if trade.is_revolving or trade.drawn_amount < trade.total_commitment:
        approach_label = "SA" if trade.approach == "sa" else "IRB"
        ead_result = calculate_ead_off_balance_sheet(
            commitment_amount=trade.total_commitment,
            commitment_type=trade.commitment_type,
            drawn_amount=trade.drawn_amount,
            approach=approach_label,
        )
        return ead_result
    else:
        # Fully drawn term loan
        return {
            "commitment_amount": trade.total_commitment,
            "commitment_type": "fully_drawn",
            "drawn_amount": trade.drawn_amount,
            "undrawn_amount": 0.0,
            "ccf": 1.0,
            "ccf_pct": 100.0,
            "ead": trade.drawn_amount,
            "approach": trade.approach.upper(),
        }


def calculate_loan_credit_risk(trade: LoanTrade, ead: float) -> dict:
    """
    Credit risk RWA on the borrower.

    Routes to SA-CR, F-IRB, or A-IRB depending on trade.approach.
    """
    borrower_pd = resolve_pd(trade.borrower_pd, trade.borrower_rating)
    borrower_rating = resolve_rating_log_scale(trade.borrower_rating, trade.borrower_pd)

    if trade.approach == "airb":
        lgd = trade.borrower_lgd if trade.borrower_lgd is not None else 0.35
        result = calculate_airb_rwa(
            ead=ead,
            pd=borrower_pd,
            lgd=lgd,
            maturity=trade.maturity,
            asset_class="corporate",
            sales_turnover=trade.sales_turnover,
        )
    elif trade.approach == "firb":
        lgd = 0.45  # prescribed senior unsecured
        result = calculate_rwa(
            ead=ead,
            pd=borrower_pd,
            lgd=lgd,
            maturity=trade.maturity,
            asset_class="corporate",
            sales_turnover=trade.sales_turnover,
        )
    else:
        exposure_class = trade.borrower_sector
        if trade.is_sme:
            exposure_class = "sme_corporate"
        result = calculate_sa_rwa(
            ead=ead,
            exposure_class=exposure_class,
            rating=borrower_rating,
            is_sme=trade.is_sme,
        )

    return {
        "rwa": result["rwa"],
        "risk_weight_pct": result["risk_weight_pct"],
        "details": result,
    }


def calculate_loan_crm(trade: LoanTrade, ead: float, exposure_rw: float) -> dict:
    """
    Credit Risk Mitigation: collateral haircuts, guarantees, credit derivatives.

    Returns adjusted exposure and RWA after CRM.
    """
    if not trade.collateral and trade.guarantee_value <= 0:
        return {
            "original_exposure": ead,
            "exposure_after_crm": ead,
            "rwa_after_crm": ead * exposure_rw,
            "rwa_reduction": 0.0,
            "details": "No CRM applied.",
        }

    crm_result = calculate_exposure_with_crm(
        exposure_value=ead,
        collateral=trade.collateral,
        guarantee_value=trade.guarantee_value,
        guarantor_rw=trade.guarantor_rw,
        exposure_rw=exposure_rw,
    )

    return {
        "original_exposure": crm_result["original_exposure"],
        "exposure_after_crm": crm_result["exposure_after_crm"],
        "rwa_after_crm": crm_result["rwa_after_crm"],
        "rwa_reduction": crm_result["rwa_reduction"],
        "details": crm_result,
    }


# =============================================================================
# Main calculator
# =============================================================================

def calculate_loan_rwa(trade: LoanTrade) -> dict:
    """
    Calculate all RWA components for a loan position.

    Returns a dict with ead, credit_risk, crm, and totals.
    Loans have no CCR, CVA, or market risk components.
    """
    # 1. EAD (drawn + CCF * undrawn)
    ead_result = calculate_loan_ead(trade)
    ead = ead_result["ead"]

    # 2. Credit risk on borrower (before CRM)
    credit_risk = calculate_loan_credit_risk(trade, ead)
    rw_decimal = credit_risk["risk_weight_pct"] / 100.0

    # 3. Credit risk mitigation
    crm = calculate_loan_crm(trade, ead, rw_decimal)

    # Total RWA is the CRM-adjusted figure (or raw credit risk if no CRM)
    total_rwa = crm["rwa_after_crm"]
    total_capital = total_rwa * 0.08

    borrower_rating = resolve_rating_log_scale(trade.borrower_rating, trade.borrower_pd)
    borrower_pd = resolve_pd(trade.borrower_pd, trade.borrower_rating)

    trade_summary = {
        "total_commitment": trade.total_commitment,
        "drawn_amount": trade.drawn_amount,
        "maturity": trade.maturity,
        "is_revolving": trade.is_revolving,
        "borrower_rating": borrower_rating,
        "borrower_pd": borrower_pd,
        "borrower_sector": trade.borrower_sector,
        "is_sme": trade.is_sme,
        "approach": trade.approach.upper(),
    }

    return {
        "trade_summary": trade_summary,
        "ead": {
            "ead": ead,
            "ccf": ead_result.get("ccf", 1.0),
            "drawn": ead_result["drawn_amount"],
            "undrawn": ead_result.get("undrawn_amount", 0.0),
        },
        "credit_risk": {
            "rwa_before_crm": credit_risk["rwa"],
            "risk_weight_pct": credit_risk["risk_weight_pct"],
            "details": credit_risk["details"],
        },
        "crm": {
            "exposure_after_crm": crm["exposure_after_crm"],
            "rwa_after_crm": crm["rwa_after_crm"],
            "rwa_reduction": crm["rwa_reduction"],
        },
        "ccr": {"rwa": 0.0, "details": "Loans have no counterparty credit risk."},
        "cva": {"rwa": 0.0, "details": "Loans are not subject to CVA charges."},
        "market_risk": {"rwa": 0.0, "details": "Banking book - no market risk charge."},
        "total_rwa": total_rwa,
        "total_capital": total_capital,
    }


# =============================================================================
# Convenience functions
# =============================================================================

def quick_loan_rwa(
    total_commitment: float,
    drawn: float = None,
    pd: float = 0.01,
    maturity: float = 3.0,
    approach: str = "sa",
    is_revolving: bool = False,
    borrower_sector: str = "corporate",
) -> dict:
    """
    Minimal-input loan RWA calculation with sensible defaults.

    Parameters
    ----------
    total_commitment : float
        Total facility amount.
    drawn : float
        Amount currently drawn (defaults to total_commitment).
    pd : float
        Borrower PD (e.g. 0.01 for 1%).
    maturity : float
        Remaining maturity in years.
    approach : str
        "sa", "firb", or "airb".
    is_revolving : bool
        True for revolving/committed facilities.
    borrower_sector : str
        Borrower sector for SA risk weight lookup.

    Returns
    -------
    dict
        Full RWA breakdown from calculate_loan_rwa.
    """
    if drawn is None:
        drawn = total_commitment

    trade = LoanTrade(
        total_commitment=total_commitment,
        drawn_amount=drawn,
        maturity=maturity,
        is_revolving=is_revolving,
        borrower_pd=pd,
        borrower_sector=borrower_sector,
        approach=approach,
    )
    return calculate_loan_rwa(trade)


def compare_approaches(
    total_commitment: float,
    drawn: float = None,
    pd: float = 0.01,
    maturity: float = 3.0,
    borrower_sector: str = "corporate",
    airb_lgd: float = 0.35,
) -> dict:
    """
    Compare RWA for SA vs F-IRB vs A-IRB on the same loan.

    Returns a dict with 'sa', 'firb', 'airb', and 'comparison' keys.
    """
    if drawn is None:
        drawn = total_commitment

    results = {}
    for approach in ("sa", "firb", "airb"):
        trade = LoanTrade(
            total_commitment=total_commitment,
            drawn_amount=drawn,
            maturity=maturity,
            borrower_pd=pd,
            borrower_sector=borrower_sector,
            approach=approach,
            borrower_lgd=airb_lgd if approach == "airb" else None,
        )
        results[approach] = calculate_loan_rwa(trade)

    return {
        "sa": results["sa"],
        "firb": results["firb"],
        "airb": results["airb"],
        "comparison": {
            "sa_rwa": results["sa"]["total_rwa"],
            "firb_rwa": results["firb"]["total_rwa"],
            "airb_rwa": results["airb"]["total_rwa"],
            "sa_capital": results["sa"]["total_capital"],
            "firb_capital": results["firb"]["total_capital"],
            "airb_capital": results["airb"]["total_capital"],
        },
    }


# =============================================================================
# CLI demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Loan RWA Calculator")
    print("=" * 70)

    result = quick_loan_rwa(50_000_000, drawn=30_000_000, pd=0.01, maturity=3.0,
                            is_revolving=True)

    ts = result["trade_summary"]
    print(f"\n  Commitment:       ${ts['total_commitment']:,.0f}")
    print(f"  Drawn:            ${ts['drawn_amount']:,.0f}")
    print(f"  Maturity:         {ts['maturity']}y")
    print(f"  Revolving:        {ts['is_revolving']}")
    print(f"  Borrower PD:      {ts['borrower_pd']:.2%}")
    print(f"  Borrower Rating:  {ts['borrower_rating']}")
    print(f"  Sector:           {ts['borrower_sector']}")
    print(f"  Approach:         {ts['approach']}")

    print(f"\n  --- EAD ---")
    print(f"  Drawn:            ${result['ead']['drawn']:,.0f}")
    print(f"  Undrawn:          ${result['ead']['undrawn']:,.0f}")
    print(f"  CCF:              {result['ead']['ccf']*100:.0f}%")
    print(f"  EAD:              ${result['ead']['ead']:,.0f}")

    print(f"\n  --- Credit Risk ---")
    print(f"  Risk Weight:      {result['credit_risk']['risk_weight_pct']:.1f}%")
    print(f"  RWA (before CRM): ${result['credit_risk']['rwa_before_crm']:,.0f}")

    print(f"\n  --- CRM ---")
    print(f"  Exposure after:   ${result['crm']['exposure_after_crm']:,.0f}")
    print(f"  RWA after CRM:    ${result['crm']['rwa_after_crm']:,.0f}")
    print(f"  RWA Reduction:    ${result['crm']['rwa_reduction']:,.0f}")

    print(f"\n  --- Not Applicable ---")
    print(f"  CCR RWA:          ${result['ccr']['rwa']:,.0f}  (no derivatives)")
    print(f"  CVA RWA:          ${result['cva']['rwa']:,.0f}  (no derivatives)")
    print(f"  Market Risk RWA:  ${result['market_risk']['rwa']:,.0f}  (banking book)")

    print(f"\n  {'='*40}")
    print(f"  TOTAL RWA:        ${result['total_rwa']:,.0f}")
    print(f"  TOTAL CAPITAL:    ${result['total_capital']:,.0f}")

    print("\n" + "=" * 70)
    print("SA vs F-IRB vs A-IRB Comparison")
    print("=" * 70)

    comp = compare_approaches(50_000_000, drawn=50_000_000, pd=0.01, maturity=3.0)
    c = comp["comparison"]
    print(f"\n  SA Total RWA:     ${c['sa_rwa']:,.0f}")
    print(f"  F-IRB Total RWA:  ${c['firb_rwa']:,.0f}")
    print(f"  A-IRB Total RWA:  ${c['airb_rwa']:,.0f}")
    print(f"  SA Capital:       ${c['sa_capital']:,.0f}")
    print(f"  F-IRB Capital:    ${c['firb_capital']:,.0f}")
    print(f"  A-IRB Capital:    ${c['airb_capital']:,.0f}")
