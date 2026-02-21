"""
CDS RWA Calculator

Unified calculator for all capital charges associated with a CDS position:
- Counterparty Credit Risk (SA-CCR EAD)
- CVA Risk Charge (BA-CVA)
- Credit Risk on Reference Entity (SA-CR or IRB)
- Market Risk Specific Risk Charge (trading book)

Usage:
    from cds_rwa import calculate_cds_rwa, quick_cds_rwa, CDSTrade

    result = quick_cds_rwa(10_000_000, pd=0.02, maturity=5.0)
    print(result["total_rwa"])
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from counterparty_risk import calculate_sa_ccr_ead, calculate_ba_cva, calculate_sa_cva
from rwa_calc import calculate_rwa, calculate_sa_rwa, calculate_airb_rwa
from ratings import RATING_TO_PD, resolve_pd, resolve_rating_log_scale


# =============================================================================
# Rating-to-SA-CCR asset class mapping
# =============================================================================

_IG_RATINGS = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}

_RATING_TO_SA_CCR_SINGLE = {
    "AAA": "CR_AAA_AA", "AA+": "CR_AAA_AA", "AA": "CR_AAA_AA", "AA-": "CR_AAA_AA",
    "A+": "CR_A", "A": "CR_A", "A-": "CR_A",
    "BBB+": "CR_BBB", "BBB": "CR_BBB", "BBB-": "CR_BBB",
    "BB+": "CR_BB", "BB": "CR_BB", "BB-": "CR_BB",
    "B+": "CR_B", "B": "CR_B", "B-": "CR_B",
    "CCC+": "CR_CCC", "CCC": "CR_CCC", "CCC-": "CR_CCC",
    "below_CCC-": "CR_CCC",
}


def rating_to_sa_ccr_asset_class(rating: str, is_index: bool = False) -> str:
    """Map a credit rating to the SA-CCR credit asset class bucket."""
    if is_index:
        return "CR_INDEX_IG" if rating in _IG_RATINGS else "CR_INDEX_SG"
    return _RATING_TO_SA_CCR_SINGLE.get(rating, "CR_BBB")


# =============================================================================
# Specific risk charge weights for trading book (MAR20/MAR21)
# =============================================================================

_SPECIFIC_RISK_WEIGHTS = {
    "AAA": 0.0, "AA+": 0.0, "AA": 0.0, "AA-": 0.0,
    "A+": 0.0025, "A": 0.0025, "A-": 0.0025,
    "BBB+": 0.01, "BBB": 0.01, "BBB-": 0.01,
    "BB+": 0.04, "BB": 0.04, "BB-": 0.04,
    "B+": 0.04, "B": 0.04, "B-": 0.04,
    "CCC+": 0.08, "CCC": 0.08, "CCC-": 0.08,
    "below_CCC-": 0.12,
    "unrated": 0.08,
}


# =============================================================================
# Data model
# =============================================================================

# Note: resolve_pd and resolve_rating_log_scale are imported from ratings.py


@dataclass
class CDSTrade:
    """All parameters describing a CDS position for RWA purposes."""

    # Core trade economics
    notional: float = 10_000_000
    maturity: float = 5.0
    is_protection_buyer: bool = True
    is_index: bool = False
    spread_bps: float = 100.0
    mtm: Optional[float] = None
    recovery_rate: float = 0.40

    # Reference entity
    reference_entity_pd: Optional[float] = None
    reference_entity_rating: Optional[str] = None
    reference_entity_sector: str = "corporate"

    # Counterparty (dealer)
    counterparty_pd: Optional[float] = None
    counterparty_rating: Optional[str] = None
    counterparty_sector: str = "financial"

    # Regulatory treatment
    approach: str = "sa"       # "sa" or "irb"
    book: str = "banking"      # "banking" or "trading"

    # Collateral / margin
    collateral_held: float = 0.0
    collateral_posted: float = 0.0
    is_margined: bool = False


# =============================================================================
# MTM estimation
# =============================================================================

def estimate_cds_mtm(
    notional: float,
    spread_bps: float,
    maturity: float,
    recovery_rate: float = 0.40,
    par_spread_bps: float = 100.0,
) -> float:
    """
    Estimate mark-to-market of a CDS from current spread.

    Uses a risky-duration approximation:
        MTM ≈ notional × (spread - par_spread) × risky_duration
    where risky_duration ≈ (1 - exp(-r*M)) / r  with r = spread/(1-R).

    Protection buyer has positive MTM when spreads have widened.
    Returns the MTM for the protection buyer.
    """
    spread = spread_bps / 10_000
    par = par_spread_bps / 10_000
    hazard = spread / (1 - recovery_rate)
    discount = 0.03  # rough risk-free rate
    r = hazard + discount
    if r <= 0 or maturity <= 0:
        return 0.0
    risky_dur = (1 - math.exp(-r * maturity)) / r
    return notional * (spread - par) * risky_dur


# =============================================================================
# Component calculators
# =============================================================================

def calculate_cds_ccr(trade: CDSTrade) -> dict:
    """
    Counterparty credit risk: SA-CCR EAD and RWA on the dealer.

    CDS is a credit derivative → SA-CCR credit asset class.
    """
    ref_rating = resolve_rating_log_scale(trade.reference_entity_rating, trade.reference_entity_pd)
    asset_class = rating_to_sa_ccr_asset_class(ref_rating, trade.is_index)

    # Delta: protection buyer is short credit risk of the reference → delta = -1
    delta = -1.0 if trade.is_protection_buyer else 1.0

    # MTM
    if trade.mtm is not None:
        mtm = trade.mtm
    else:
        buyer_mtm = estimate_cds_mtm(
            trade.notional, trade.spread_bps, trade.maturity, trade.recovery_rate
        )
        mtm = buyer_mtm if trade.is_protection_buyer else -buyer_mtm

    sa_ccr_trade = {
        "notional": trade.notional,
        "asset_class": asset_class,
        "maturity": trade.maturity,
        "mtm": mtm,
        "delta": delta,
    }

    ead_result = calculate_sa_ccr_ead(
        trades=[sa_ccr_trade],
        collateral_held=trade.collateral_held,
        collateral_posted=trade.collateral_posted,
        is_margined=trade.is_margined,
    )
    ead = ead_result["ead"]

    # Risk weight the EAD against the counterparty (dealer)
    cp_rating = resolve_rating_log_scale(trade.counterparty_rating, trade.counterparty_pd)
    cp_pd = resolve_pd(trade.counterparty_pd, trade.counterparty_rating)

    if trade.approach == "irb":
        rw_result = calculate_rwa(ead=ead, pd=cp_pd, lgd=0.45, maturity=trade.maturity)
        rw_pct = rw_result["risk_weight_pct"]
        ccr_rwa = rw_result["rwa"]
    else:
        rw_result = calculate_sa_rwa(
            ead=ead,
            exposure_class="bank" if trade.counterparty_sector == "financial" else "corporate",
            rating=cp_rating,
        )
        rw_pct = rw_result["risk_weight_pct"]
        ccr_rwa = rw_result["rwa"]

    return {
        "sa_ccr_ead": ead,
        "sa_ccr_details": ead_result,
        "counterparty_rating": cp_rating,
        "counterparty_rw": rw_pct,
        "ccr_rwa": ccr_rwa,
    }


def calculate_cds_cva(trade: CDSTrade, ead: float) -> dict:
    """CVA risk charge on the dealer counterparty."""
    cp_rating = resolve_rating_log_scale(trade.counterparty_rating, trade.counterparty_pd)

    counterparty = {
        "ead": ead,
        "rating": cp_rating,
        "maturity": trade.maturity,
        "sector": trade.counterparty_sector,
    }

    cva_result = calculate_ba_cva([counterparty])
    return {
        "cva_capital": cva_result["k_cva"],
        "cva_rwa": cva_result["rwa"],
        "cva_details": cva_result,
    }


def calculate_cds_credit_risk(trade: CDSTrade) -> dict:
    """
    Credit risk on the reference entity.

    Protection seller: has a direct credit exposure equal to the notional.
    Protection buyer: no credit risk on the reference entity (has protection).
    """
    if trade.is_protection_buyer:
        return {
            "rwa": 0.0,
            "details": "Protection buyer has no direct credit risk on reference entity.",
        }

    # Protection seller: notional is the exposure
    ref_pd = resolve_pd(trade.reference_entity_pd, trade.reference_entity_rating)
    ref_rating = resolve_rating_log_scale(trade.reference_entity_rating, trade.reference_entity_pd)

    if trade.approach == "irb":
        lgd = 1 - trade.recovery_rate
        result = calculate_rwa(
            ead=trade.notional,
            pd=ref_pd,
            lgd=lgd,
            maturity=trade.maturity,
            asset_class="corporate",
        )
    else:
        result = calculate_sa_rwa(
            ead=trade.notional,
            exposure_class=trade.reference_entity_sector,
            rating=ref_rating,
        )

    return {
        "rwa": result["rwa"],
        "details": result,
    }


def calculate_cds_market_risk(trade: CDSTrade) -> dict:
    """
    Specific risk charge for CDS in the trading book.

    Uses the standardised specific-risk weight tables.
    Only applies if book == "trading".
    """
    if trade.book != "trading":
        return {"specific_risk_charge": 0.0, "rwa": 0.0, "details": "Banking book - no market risk charge."}

    ref_rating = resolve_rating_log_scale(trade.reference_entity_rating, trade.reference_entity_pd)
    weight = _SPECIFIC_RISK_WEIGHTS.get(ref_rating, _SPECIFIC_RISK_WEIGHTS["unrated"])

    # Index CDS gets a lower weight (simplified: 50% of single-name)
    if trade.is_index:
        weight *= 0.50

    specific_risk_charge = trade.notional * weight
    rwa = specific_risk_charge * 12.5

    return {
        "specific_risk_charge": specific_risk_charge,
        "rwa": rwa,
        "risk_weight": weight,
        "details": f"Specific risk: {ref_rating} -> {weight*100:.2f}% weight",
    }


# =============================================================================
# Main calculator
# =============================================================================

def calculate_cds_rwa(trade: CDSTrade) -> dict:
    """
    Calculate all RWA components for a CDS position.

    Returns a dict with ccr, cva, credit_risk, market_risk, and totals.
    """
    # 1. Counterparty credit risk (SA-CCR EAD → RWA)
    ccr = calculate_cds_ccr(trade)
    ead = ccr["sa_ccr_ead"]

    # 2. CVA risk charge
    cva = calculate_cds_cva(trade, ead)

    # 3. Credit risk on reference entity (protection seller only)
    credit_risk = calculate_cds_credit_risk(trade)

    # 4. Market risk (trading book only)
    market_risk = calculate_cds_market_risk(trade)

    # Totals
    total_rwa = ccr["ccr_rwa"] + cva["cva_rwa"] + credit_risk["rwa"] + market_risk["rwa"]
    total_capital = total_rwa * 0.08

    # Trade summary
    trade_summary = {
        "notional": trade.notional,
        "maturity": trade.maturity,
        "direction": "protection_buyer" if trade.is_protection_buyer else "protection_seller",
        "type": "index" if trade.is_index else "single_name",
        "spread_bps": trade.spread_bps,
        "reference_entity_rating": resolve_rating_log_scale(trade.reference_entity_rating, trade.reference_entity_pd),
        "reference_entity_pd": resolve_pd(trade.reference_entity_pd, trade.reference_entity_rating),
        "counterparty_rating": resolve_rating_log_scale(trade.counterparty_rating, trade.counterparty_pd),
        "approach": trade.approach.upper(),
        "book": trade.book,
    }

    return {
        "trade_summary": trade_summary,
        "ccr": {
            "sa_ccr_ead": ccr["sa_ccr_ead"],
            "counterparty_rw": ccr["counterparty_rw"],
            "ccr_rwa": ccr["ccr_rwa"],
        },
        "cva": {
            "cva_capital": cva["cva_capital"],
            "cva_rwa": cva["cva_rwa"],
        },
        "credit_risk": {
            "rwa": credit_risk["rwa"],
            "details": credit_risk["details"],
        },
        "market_risk": {
            "specific_risk_charge": market_risk["specific_risk_charge"],
            "rwa": market_risk["rwa"],
        },
        "total_rwa": total_rwa,
        "total_capital": total_capital,
    }


# =============================================================================
# Convenience functions
# =============================================================================

def quick_cds_rwa(
    notional: float,
    pd: float,
    maturity: float,
    is_protection_buyer: bool = True,
    spread_bps: float = 100.0,
    counterparty_rating: str = "A",
    approach: str = "sa",
    book: str = "banking",
) -> dict:
    """
    Minimal-input CDS RWA calculation with sensible defaults.

    Parameters
    ----------
    notional : float
        CDS notional amount.
    pd : float
        PD of the reference entity (e.g. 0.02 for 2%).
    maturity : float
        Remaining maturity in years.
    is_protection_buyer : bool
        True = bought protection (default).
    spread_bps : float
        Current CDS spread in basis points.
    counterparty_rating : str
        Dealer credit rating (default "A").
    approach : str
        "sa" or "irb".
    book : str
        "banking" or "trading".

    Returns
    -------
    dict
        Full RWA breakdown from calculate_cds_rwa.
    """
    trade = CDSTrade(
        notional=notional,
        maturity=maturity,
        is_protection_buyer=is_protection_buyer,
        reference_entity_pd=pd,
        spread_bps=spread_bps,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )
    return calculate_cds_rwa(trade)


def compare_buyer_vs_seller(
    notional: float,
    pd: float,
    maturity: float,
    spread_bps: float = 100.0,
    counterparty_rating: str = "A",
    approach: str = "sa",
    book: str = "banking",
) -> dict:
    """
    Compare RWA for protection buyer vs. seller on the same CDS.

    Returns a dict with 'buyer', 'seller', and 'comparison' keys.
    """
    buyer = quick_cds_rwa(
        notional, pd, maturity,
        is_protection_buyer=True,
        spread_bps=spread_bps,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )
    seller = quick_cds_rwa(
        notional, pd, maturity,
        is_protection_buyer=False,
        spread_bps=spread_bps,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )

    return {
        "buyer": buyer,
        "seller": seller,
        "comparison": {
            "buyer_total_rwa": buyer["total_rwa"],
            "seller_total_rwa": seller["total_rwa"],
            "rwa_difference": seller["total_rwa"] - buyer["total_rwa"],
            "buyer_capital": buyer["total_capital"],
            "seller_capital": seller["total_capital"],
        },
    }


# =============================================================================
# CLI demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("CDS RWA Calculator")
    print("=" * 70)

    result = quick_cds_rwa(10_000_000, pd=0.02, maturity=5.0)

    ts = result["trade_summary"]
    print(f"\n  Direction:        {ts['direction']}")
    print(f"  Notional:         ${ts['notional']:,.0f}")
    print(f"  Maturity:         {ts['maturity']}y")
    print(f"  Ref Entity PD:    {ts['reference_entity_pd']:.2%}")
    print(f"  Ref Entity Rating:{ts['reference_entity_rating']}")
    print(f"  Counterparty:     {ts['counterparty_rating']}")
    print(f"  Approach:         {ts['approach']}")
    print(f"  Book:             {ts['book']}")

    print(f"\n  --- CCR ---")
    print(f"  SA-CCR EAD:       ${result['ccr']['sa_ccr_ead']:,.0f}")
    print(f"  Counterparty RW:  {result['ccr']['counterparty_rw']:.1f}%")
    print(f"  CCR RWA:          ${result['ccr']['ccr_rwa']:,.0f}")

    print(f"\n  --- CVA ---")
    print(f"  CVA Capital:      ${result['cva']['cva_capital']:,.0f}")
    print(f"  CVA RWA:          ${result['cva']['cva_rwa']:,.0f}")

    print(f"\n  --- Credit Risk ---")
    print(f"  Credit Risk RWA:  ${result['credit_risk']['rwa']:,.0f}")

    print(f"\n  --- Market Risk ---")
    print(f"  Specific Risk:    ${result['market_risk']['specific_risk_charge']:,.0f}")
    print(f"  Market Risk RWA:  ${result['market_risk']['rwa']:,.0f}")

    print(f"\n  {'='*40}")
    print(f"  TOTAL RWA:        ${result['total_rwa']:,.0f}")
    print(f"  TOTAL CAPITAL:    ${result['total_capital']:,.0f}")

    print("\n" + "=" * 70)
    print("Buyer vs Seller Comparison")
    print("=" * 70)

    comp = compare_buyer_vs_seller(10_000_000, pd=0.02, maturity=5.0)
    c = comp["comparison"]
    print(f"\n  Buyer Total RWA:  ${c['buyer_total_rwa']:,.0f}")
    print(f"  Seller Total RWA: ${c['seller_total_rwa']:,.0f}")
    print(f"  RWA Difference:   ${c['rwa_difference']:,.0f}")
    print(f"  Buyer Capital:    ${c['buyer_capital']:,.0f}")
    print(f"  Seller Capital:   ${c['seller_capital']:,.0f}")
