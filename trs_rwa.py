"""
TRS (Total Return Swap) RWA Calculator

Unified calculator for all capital charges associated with a TRS position:
- Counterparty Credit Risk (SA-CCR EAD on the dealer)
- CVA Risk Charge (BA-CVA on the counterparty)
- Credit/Market Risk on Reference Asset (synthetic long/short exposure)
- Market Risk (FRTB-SA delta sensitivity for trading book)

Usage:
    from trs_rwa import calculate_trs_rwa, quick_trs_rwa, TRSTrade

    result = quick_trs_rwa(10_000_000, pd=0.02, maturity=3.0)
    print(result["total_rwa"])
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from counterparty_risk import calculate_sa_ccr_ead, calculate_ba_cva
from rwa_calc import calculate_rwa, calculate_sa_rwa, RATING_TO_PD
from market_risk import (
    EQ_RISK_WEIGHTS,
    CSR_RISK_WEIGHTS,
    COM_RISK_WEIGHTS,
    FX_RISK_WEIGHT,
)


# =============================================================================
# Helpers
# =============================================================================

def _resolve_pd(pd: Optional[float], rating: Optional[str]) -> float:
    """Get PD from explicit value or rating lookup."""
    if pd is not None:
        return pd
    if rating is not None and rating != "unrated":
        return RATING_TO_PD.get(rating, RATING_TO_PD.get("BBB", 0.004))
    return 0.004


def _resolve_rating(rating: Optional[str], pd: Optional[float]) -> str:
    """Get a rating string, falling back to PD-based estimation."""
    if rating is not None:
        return rating
    if pd is not None:
        best, best_dist = "unrated", float("inf")
        for r, rpd in RATING_TO_PD.items():
            d = abs(math.log(max(pd, 1e-8)) - math.log(max(rpd, 1e-8)))
            if d < best_dist:
                best, best_dist = r, d
        return best
    return "unrated"


# =============================================================================
# Underlying → SA-CCR asset class mapping
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


def _underlying_to_sa_ccr_class(underlying_type: str, rating: str = "BBB") -> str:
    """Map a TRS underlying type to its SA-CCR asset class bucket."""
    if underlying_type == "equity":
        return "EQ_SINGLE"
    elif underlying_type == "equity_index":
        return "EQ_INDEX"
    elif underlying_type == "commodity":
        return "COM_OTHER"
    elif underlying_type in ("bond", "loan", "credit"):
        return _RATING_TO_SA_CCR_SINGLE.get(rating, "CR_BBB")
    elif underlying_type == "credit_index":
        return "CR_INDEX_IG" if rating in _IG_RATINGS else "CR_INDEX_SG"
    else:
        return "CR_BBB"


# =============================================================================
# FRTB-SA bucket mapping for market risk
# =============================================================================

def _underlying_to_frtb_bucket(underlying_type: str) -> tuple:
    """Map underlying type to FRTB risk class and bucket for delta sensitivity."""
    if underlying_type in ("equity", "equity_index"):
        return "EQ", "large_cap_developed"
    elif underlying_type in ("bond", "loan", "credit", "credit_index"):
        return "CSR", "corporate_IG"
    elif underlying_type == "commodity":
        return "COM", "energy_liquid"
    else:
        return "EQ", "other"


def _get_frtb_rw(risk_class: str, bucket: str) -> float:
    """Get the FRTB-SA delta risk weight (%) for a given risk class + bucket."""
    if risk_class == "EQ":
        return EQ_RISK_WEIGHTS.get(bucket, (50, 0.75))[0]
    elif risk_class == "CSR":
        weights = CSR_RISK_WEIGHTS.get(bucket, (5.0, 5.0, 5.0, 5.0))
        return weights[2]  # use 5Y tenor as representative
    elif risk_class == "COM":
        return COM_RISK_WEIGHTS.get(bucket, 50)
    else:
        return FX_RISK_WEIGHT


# =============================================================================
# Data model
# =============================================================================

@dataclass
class TRSTrade:
    """All parameters describing a TRS position for RWA purposes."""

    # Core trade economics
    notional: float = 10_000_000
    maturity: float = 3.0
    is_total_return_receiver: bool = True  # receiver = synthetic long
    mtm: Optional[float] = None
    spread_bps: float = 50.0
    funding_spread_bps: float = 20.0

    # Underlying reference asset
    underlying_type: str = "equity"  # equity, equity_index, bond, loan, credit, credit_index, commodity
    underlying_rating: Optional[str] = None
    underlying_pd: Optional[float] = None
    underlying_sector: str = "corporate"

    # Counterparty (dealer)
    counterparty_pd: Optional[float] = None
    counterparty_rating: Optional[str] = None
    counterparty_sector: str = "financial"

    # Regulatory treatment
    approach: str = "sa"           # "sa" or "irb"
    book: str = "banking"          # "banking" or "trading"

    # Collateral / margin
    collateral_held: float = 0.0
    collateral_posted: float = 0.0
    is_margined: bool = False


# =============================================================================
# MTM estimation
# =============================================================================

def estimate_trs_mtm(
    notional: float,
    spread_bps: float,
    funding_spread_bps: float,
    maturity: float,
    price_change_pct: float = 0.0,
) -> float:
    """
    Estimate mark-to-market of a TRS from spread/price moves.

    MTM for receiver ≈ notional * price_change + notional * (spread - funding) * duration
    Returns the MTM for the total return receiver.
    """
    net_carry = (spread_bps - funding_spread_bps) / 10_000
    duration_approx = min(maturity, 5.0) * 0.9  # rough duration proxy
    carry_mtm = notional * net_carry * duration_approx
    price_mtm = notional * price_change_pct
    return carry_mtm + price_mtm


# =============================================================================
# Component calculators
# =============================================================================

def calculate_trs_ccr(trade: TRSTrade) -> dict:
    """
    Counterparty credit risk: SA-CCR EAD and RWA on the dealer.

    Maps underlying to the appropriate SA-CCR asset class.
    """
    und_rating = _resolve_rating(trade.underlying_rating, trade.underlying_pd)
    asset_class = _underlying_to_sa_ccr_class(trade.underlying_type, und_rating)

    # Delta: receiver is long the underlying → delta = +1
    delta = 1.0 if trade.is_total_return_receiver else -1.0

    # MTM
    if trade.mtm is not None:
        mtm = trade.mtm
    else:
        receiver_mtm = estimate_trs_mtm(
            trade.notional, trade.spread_bps, trade.funding_spread_bps, trade.maturity
        )
        mtm = receiver_mtm if trade.is_total_return_receiver else -receiver_mtm

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

    # Risk weight the EAD against the counterparty
    cp_rating = _resolve_rating(trade.counterparty_rating, trade.counterparty_pd)
    cp_pd = _resolve_pd(trade.counterparty_pd, trade.counterparty_rating)

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


def calculate_trs_cva(trade: TRSTrade, ead: float) -> dict:
    """CVA risk charge on the dealer counterparty (BA-CVA)."""
    cp_rating = _resolve_rating(trade.counterparty_rating, trade.counterparty_pd)

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


def calculate_trs_reference_risk(trade: TRSTrade) -> dict:
    """
    Credit / asset risk on the reference asset.

    Total return receiver has a synthetic long exposure to the underlying.
    Total return payer has no credit risk on the underlying (has passed it on).
    """
    if not trade.is_total_return_receiver:
        return {
            "rwa": 0.0,
            "details": "TRS payer has no direct credit risk on the reference asset.",
        }

    # Receiver: synthetic long → treat notional as exposure
    und_pd = _resolve_pd(trade.underlying_pd, trade.underlying_rating)
    und_rating = _resolve_rating(trade.underlying_rating, trade.underlying_pd)

    if trade.approach == "irb":
        lgd = 0.45
        result = calculate_rwa(
            ead=trade.notional,
            pd=und_pd,
            lgd=lgd,
            maturity=trade.maturity,
            asset_class="corporate",
        )
    else:
        result = calculate_sa_rwa(
            ead=trade.notional,
            exposure_class=trade.underlying_sector,
            rating=und_rating,
        )

    return {
        "rwa": result["rwa"],
        "details": result,
    }


def calculate_trs_market_risk(trade: TRSTrade) -> dict:
    """
    Market risk charge for TRS in the trading book.

    Uses FRTB-SA delta sensitivity on the underlying.
    Only applies if book == "trading".
    """
    if trade.book != "trading":
        return {"delta_charge": 0.0, "rwa": 0.0, "details": "Banking book - no market risk charge."}

    risk_class, bucket = _underlying_to_frtb_bucket(trade.underlying_type)
    rw_pct = _get_frtb_rw(risk_class, bucket)
    rw = rw_pct / 100.0

    # Delta sensitivity ≈ notional for a linear TRS
    sensitivity = trade.notional
    delta_charge = sensitivity * rw
    rwa = delta_charge * 12.5

    return {
        "delta_charge": delta_charge,
        "rwa": rwa,
        "risk_class": risk_class,
        "bucket": bucket,
        "risk_weight_pct": rw_pct,
        "details": f"FRTB-SA delta: {risk_class}/{bucket} -> {rw_pct:.1f}% RW",
    }


# =============================================================================
# Main calculator
# =============================================================================

def calculate_trs_rwa(trade: TRSTrade) -> dict:
    """
    Calculate all RWA components for a TRS position.

    Returns a dict with ccr, cva, reference_risk, market_risk, and totals.
    """
    # 1. Counterparty credit risk (SA-CCR EAD → RWA)
    ccr = calculate_trs_ccr(trade)
    ead = ccr["sa_ccr_ead"]

    # 2. CVA risk charge
    cva = calculate_trs_cva(trade, ead)

    # 3. Credit/asset risk on the reference asset (receiver only)
    reference_risk = calculate_trs_reference_risk(trade)

    # 4. Market risk (trading book only)
    market_risk = calculate_trs_market_risk(trade)

    # Totals
    total_rwa = ccr["ccr_rwa"] + cva["cva_rwa"] + reference_risk["rwa"] + market_risk["rwa"]
    total_capital = total_rwa * 0.08

    und_rating = _resolve_rating(trade.underlying_rating, trade.underlying_pd)
    und_pd = _resolve_pd(trade.underlying_pd, trade.underlying_rating)

    trade_summary = {
        "notional": trade.notional,
        "maturity": trade.maturity,
        "direction": "receiver" if trade.is_total_return_receiver else "payer",
        "underlying_type": trade.underlying_type,
        "underlying_rating": und_rating,
        "underlying_pd": und_pd,
        "counterparty_rating": _resolve_rating(trade.counterparty_rating, trade.counterparty_pd),
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
        "reference_risk": {
            "rwa": reference_risk["rwa"],
            "details": reference_risk["details"],
        },
        "market_risk": {
            "delta_charge": market_risk.get("delta_charge", 0.0),
            "rwa": market_risk["rwa"],
        },
        "total_rwa": total_rwa,
        "total_capital": total_capital,
    }


# =============================================================================
# Convenience functions
# =============================================================================

def quick_trs_rwa(
    notional: float,
    pd: float = 0.02,
    maturity: float = 3.0,
    is_total_return_receiver: bool = True,
    underlying_type: str = "equity",
    counterparty_rating: str = "A",
    approach: str = "sa",
    book: str = "banking",
) -> dict:
    """
    Minimal-input TRS RWA calculation with sensible defaults.

    Parameters
    ----------
    notional : float
        TRS notional amount.
    pd : float
        PD of the underlying reference asset.
    maturity : float
        Remaining maturity in years.
    is_total_return_receiver : bool
        True = receiving total return (synthetic long).
    underlying_type : str
        Type of underlying (equity, bond, etc.).
    counterparty_rating : str
        Dealer credit rating.
    approach : str
        "sa" or "irb".
    book : str
        "banking" or "trading".

    Returns
    -------
    dict
        Full RWA breakdown from calculate_trs_rwa.
    """
    trade = TRSTrade(
        notional=notional,
        maturity=maturity,
        is_total_return_receiver=is_total_return_receiver,
        underlying_type=underlying_type,
        underlying_pd=pd,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )
    return calculate_trs_rwa(trade)


def compare_receiver_vs_payer(
    notional: float,
    pd: float = 0.02,
    maturity: float = 3.0,
    underlying_type: str = "equity",
    counterparty_rating: str = "A",
    approach: str = "sa",
    book: str = "banking",
) -> dict:
    """
    Compare RWA for total return receiver vs. payer on the same TRS.

    Returns a dict with 'receiver', 'payer', and 'comparison' keys.
    """
    receiver = quick_trs_rwa(
        notional, pd, maturity,
        is_total_return_receiver=True,
        underlying_type=underlying_type,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )
    payer = quick_trs_rwa(
        notional, pd, maturity,
        is_total_return_receiver=False,
        underlying_type=underlying_type,
        counterparty_rating=counterparty_rating,
        approach=approach,
        book=book,
    )

    return {
        "receiver": receiver,
        "payer": payer,
        "comparison": {
            "receiver_total_rwa": receiver["total_rwa"],
            "payer_total_rwa": payer["total_rwa"],
            "rwa_difference": receiver["total_rwa"] - payer["total_rwa"],
            "receiver_capital": receiver["total_capital"],
            "payer_capital": payer["total_capital"],
        },
    }


# =============================================================================
# CLI demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("TRS RWA Calculator")
    print("=" * 70)

    result = quick_trs_rwa(10_000_000, pd=0.02, maturity=3.0, underlying_type="equity")

    ts = result["trade_summary"]
    print(f"\n  Direction:        {ts['direction']}")
    print(f"  Notional:         ${ts['notional']:,.0f}")
    print(f"  Maturity:         {ts['maturity']}y")
    print(f"  Underlying:       {ts['underlying_type']}")
    print(f"  Underlying PD:    {ts['underlying_pd']:.2%}")
    print(f"  Underlying Rating:{ts['underlying_rating']}")
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

    print(f"\n  --- Reference Asset Risk ---")
    print(f"  Reference RWA:    ${result['reference_risk']['rwa']:,.0f}")

    print(f"\n  --- Market Risk ---")
    print(f"  Delta Charge:     ${result['market_risk']['delta_charge']:,.0f}")
    print(f"  Market Risk RWA:  ${result['market_risk']['rwa']:,.0f}")

    print(f"\n  {'='*40}")
    print(f"  TOTAL RWA:        ${result['total_rwa']:,.0f}")
    print(f"  TOTAL CAPITAL:    ${result['total_capital']:,.0f}")

    print("\n" + "=" * 70)
    print("Receiver vs Payer Comparison")
    print("=" * 70)

    comp = compare_receiver_vs_payer(10_000_000, pd=0.02, maturity=3.0,
                                      underlying_type="equity")
    c = comp["comparison"]
    print(f"\n  Receiver Total RWA: ${c['receiver_total_rwa']:,.0f}")
    print(f"  Payer Total RWA:    ${c['payer_total_rwa']:,.0f}")
    print(f"  RWA Difference:     ${c['rwa_difference']:,.0f}")
    print(f"  Receiver Capital:   ${c['receiver_capital']:,.0f}")
    print(f"  Payer Capital:      ${c['payer_capital']:,.0f}")
