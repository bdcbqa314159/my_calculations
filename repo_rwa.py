"""
Repo / Reverse Repo (SFT) RWA Calculator

Unified calculator for all capital charges associated with a repo position:
- Counterparty Credit Risk via comprehensive approach with supervisory haircuts
  E* = max(0, E*(1+He) - C*(1-Hc-Hfx))
- Credit Risk (RW the net exposure E* against the counterparty)
- CVA Risk: SFTs are EXEMPT from CVA charges per Basel III (MAR50.7)
- Market Risk: Generally not applicable (banking book)

Usage:
    from repo_rwa import calculate_repo_rwa, quick_repo_rwa, RepoTrade

    result = quick_repo_rwa(50_000_000, securities_value=51_000_000, maturity=0.25)
    print(result["total_rwa"])
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from rwa_calc import calculate_rwa, calculate_sa_rwa
from ratings import RATING_TO_PD, resolve_pd, resolve_rating_log_scale
from capital_framework import SUPERVISORY_HAIRCUTS, calculate_collateral_haircut


# =============================================================================
# Supervisory haircut mapping for repo securities
# =============================================================================

# Map security types to SUPERVISORY_HAIRCUTS keys
_SECURITY_HAIRCUT_MAP = {
    # Sovereign debt
    ("sovereign_debt", "AAA", "1y"): "sovereign_AAA_AA_1y",
    ("sovereign_debt", "AAA", "5y"): "sovereign_AAA_AA_5y",
    ("sovereign_debt", "AAA", "long"): "sovereign_AAA_AA_long",
    ("sovereign_debt", "AA", "1y"): "sovereign_AAA_AA_1y",
    ("sovereign_debt", "AA", "5y"): "sovereign_AAA_AA_5y",
    ("sovereign_debt", "AA", "long"): "sovereign_AAA_AA_long",
    ("sovereign_debt", "A", "1y"): "sovereign_A_BBB_1y",
    ("sovereign_debt", "A", "5y"): "sovereign_A_BBB_5y",
    ("sovereign_debt", "A", "long"): "sovereign_A_BBB_long",
    ("sovereign_debt", "BBB", "1y"): "sovereign_A_BBB_1y",
    ("sovereign_debt", "BBB", "5y"): "sovereign_A_BBB_5y",
    ("sovereign_debt", "BBB", "long"): "sovereign_A_BBB_long",
    # Corporate bonds
    ("corporate_bond", "AAA", "1y"): "other_AAA_AA_1y",
    ("corporate_bond", "AAA", "5y"): "other_AAA_AA_5y",
    ("corporate_bond", "AAA", "long"): "other_AAA_AA_long",
    ("corporate_bond", "AA", "1y"): "other_AAA_AA_1y",
    ("corporate_bond", "AA", "5y"): "other_AAA_AA_5y",
    ("corporate_bond", "AA", "long"): "other_AAA_AA_long",
    ("corporate_bond", "A", "1y"): "other_A_BBB_1y",
    ("corporate_bond", "A", "5y"): "other_A_BBB_5y",
    ("corporate_bond", "A", "long"): "other_A_BBB_long",
    ("corporate_bond", "BBB", "1y"): "other_A_BBB_1y",
    ("corporate_bond", "BBB", "5y"): "other_A_BBB_5y",
    ("corporate_bond", "BBB", "long"): "other_A_BBB_long",
    # Equities
    ("equity_main_index", None, None): "equity_main_index",
    ("equity_other", None, None): "equity_other",
    # Cash
    ("cash", None, None): "cash",
    # Gold
    ("gold", None, None): "gold",
}


def _get_security_haircut(
    security_type: str,
    security_rating: str = "AAA",
    security_maturity_bucket: str = "5y",
) -> float:
    """Get the supervisory haircut Hc for the securities leg."""
    # Simplify rating to broad bucket
    if security_rating in ("AAA", "AA+", "AA", "AA-"):
        rating_bucket = "AAA"
    elif security_rating in ("A+", "A", "A-"):
        rating_bucket = "A"
    elif security_rating in ("BBB+", "BBB", "BBB-"):
        rating_bucket = "BBB"
    elif security_rating in ("AA",):
        rating_bucket = "AA"
    else:
        rating_bucket = "BBB"

    # Try exact lookup
    key = (security_type, rating_bucket, security_maturity_bucket)
    haircut_key = _SECURITY_HAIRCUT_MAP.get(key)

    # Try without rating/maturity (equities, cash, gold)
    if haircut_key is None:
        key_no_rating = (security_type, None, None)
        haircut_key = _SECURITY_HAIRCUT_MAP.get(key_no_rating)

    if haircut_key is None:
        # Default: other A-BBB 5y
        haircut_key = "other_A_BBB_5y"

    return SUPERVISORY_HAIRCUTS.get(haircut_key, 0.06)


# =============================================================================
# Data model
# =============================================================================

@dataclass
class RepoTrade:
    """All parameters describing a repo/reverse repo (SFT) for RWA purposes."""

    # Core economics
    cash_amount: float = 50_000_000       # Cash leg
    securities_value: float = 51_000_000  # Securities leg (market value)
    maturity: float = 0.25                # Typically short-term (days to weeks)

    # Direction: True = repo (lending securities, borrowing cash)
    #            False = reverse repo (borrowing securities, lending cash)
    is_repo: bool = True

    # Securities characteristics
    security_type: str = "sovereign_debt"  # sovereign_debt, corporate_bond, equity_main_index, equity_other, cash, gold
    security_rating: str = "AAA"
    security_maturity_bucket: str = "5y"   # 1y, 5y, long

    # Counterparty
    counterparty_pd: Optional[float] = None
    counterparty_rating: Optional[str] = None
    counterparty_sector: str = "financial"

    # Haircut parameters
    currency_mismatch: bool = False
    holding_period_days: int = 5  # Standard for repo is 5 business days

    # Regulatory treatment
    approach: str = "sa"                     # "sa" or "irb"
    haircut_approach: str = "supervisory"     # "supervisory" or "own_estimates"


# =============================================================================
# Component calculators
# =============================================================================

_STANDARD_HOLDING_PERIOD = 10  # 10 business days is the base for supervisory haircuts


def calculate_repo_exposure(trade: RepoTrade) -> dict:
    """
    Calculate net exposure E* via the comprehensive approach with supervisory haircuts.

    For a repo (lend securities, receive cash):
        E = securities_value (exposure = securities lent)
        C = cash_amount (collateral = cash received)
        He = haircut on exposure (securities)
        Hc = 0 (cash has zero haircut)
        E* = max(0, E*(1+He) - C*(1-Hc-Hfx))

    For a reverse repo (lend cash, receive securities):
        E = cash_amount (exposure = cash lent)
        C = securities_value (collateral = securities received)
        He = 0 (cash has zero haircut)
        Hc = haircut on collateral (securities)
        E* = max(0, E*(1+He) - C*(1-Hc-Hfx))
    """
    # Determine He (exposure haircut) and Hc (collateral haircut)
    security_haircut = _get_security_haircut(
        trade.security_type, trade.security_rating, trade.security_maturity_bucket
    )

    # Scale haircut for holding period (CRE22.56)
    # H_adjusted = H * sqrt(holding_period / standard_period)
    holding_scale = math.sqrt(trade.holding_period_days / _STANDARD_HOLDING_PERIOD)
    security_haircut_scaled = security_haircut * holding_scale

    # FX mismatch haircut
    h_fx = SUPERVISORY_HAIRCUTS.get("fx_mismatch", 0.08) if trade.currency_mismatch else 0.0
    h_fx_scaled = h_fx * holding_scale

    if trade.is_repo:
        # Repo: lend securities (E), receive cash (C)
        e = trade.securities_value
        c = trade.cash_amount
        h_e = security_haircut_scaled   # haircut on securities lent
        h_c = 0.0                        # cash has zero haircut
    else:
        # Reverse repo: lend cash (E), receive securities (C)
        e = trade.cash_amount
        c = trade.securities_value
        h_e = 0.0                        # cash has zero haircut
        h_c = security_haircut_scaled   # haircut on securities received

    # E* = max(0, E*(1+He) - C*(1-Hc-Hfx))
    e_star = max(0.0, e * (1 + h_e) - c * (1 - h_c - h_fx_scaled))

    return {
        "exposure_leg": e,
        "collateral_leg": c,
        "is_repo": trade.is_repo,
        "security_haircut_base": security_haircut,
        "security_haircut_scaled": security_haircut_scaled,
        "holding_period_days": trade.holding_period_days,
        "holding_scale": holding_scale,
        "h_e": h_e,
        "h_c": h_c,
        "h_fx": h_fx_scaled,
        "e_star": e_star,
        "overcollateralization": (c / e - 1) * 100 if e > 0 else 0,
    }


def calculate_repo_ccr(trade: RepoTrade, e_star: float) -> dict:
    """
    Risk-weight the net exposure E* against the counterparty.

    Uses SA-CR or IRB depending on trade.approach.
    """
    if e_star <= 0:
        return {
            "rwa": 0.0,
            "risk_weight_pct": 0.0,
            "details": "Net exposure E* is zero - fully collateralised.",
        }

    cp_rating = resolve_rating_log_scale(trade.counterparty_rating, trade.counterparty_pd)
    cp_pd = resolve_pd(trade.counterparty_pd, trade.counterparty_rating)

    if trade.approach == "irb":
        result = calculate_rwa(
            ead=e_star,
            pd=cp_pd,
            lgd=0.45,
            maturity=max(trade.maturity, 10 / 250),  # floor at 10 days
            asset_class="corporate",
        )
    else:
        result = calculate_sa_rwa(
            ead=e_star,
            exposure_class="bank" if trade.counterparty_sector == "financial" else "corporate",
            rating=cp_rating,
        )

    return {
        "rwa": result["rwa"],
        "risk_weight_pct": result["risk_weight_pct"],
        "details": result,
    }


# =============================================================================
# Main calculator
# =============================================================================

def calculate_repo_rwa(trade: RepoTrade) -> dict:
    """
    Calculate all RWA components for a repo/reverse repo position.

    SFTs are exempt from CVA charges per Basel III (MAR50.7).
    Market risk generally not applicable (banking book).

    Returns a dict with exposure, ccr, and totals.
    """
    # 1. Calculate net exposure via comprehensive approach
    exposure = calculate_repo_exposure(trade)
    e_star = exposure["e_star"]

    # 2. Risk-weight E* against counterparty
    ccr = calculate_repo_ccr(trade, e_star)

    # 3. CVA: exempt for SFTs
    cva = {"cva_capital": 0.0, "cva_rwa": 0.0, "details": "SFTs exempt from CVA (MAR50.7)."}

    # 4. Market risk: not applicable
    market_risk = {"rwa": 0.0, "details": "Banking book - no market risk charge."}

    # Total
    total_rwa = ccr["rwa"]
    total_capital = total_rwa * 0.08

    cp_rating = resolve_rating_log_scale(trade.counterparty_rating, trade.counterparty_pd)
    cp_pd = resolve_pd(trade.counterparty_pd, trade.counterparty_rating)

    trade_summary = {
        "cash_amount": trade.cash_amount,
        "securities_value": trade.securities_value,
        "maturity": trade.maturity,
        "direction": "repo" if trade.is_repo else "reverse_repo",
        "security_type": trade.security_type,
        "security_rating": trade.security_rating,
        "counterparty_rating": cp_rating,
        "counterparty_pd": cp_pd,
        "approach": trade.approach.upper(),
        "haircut_approach": trade.haircut_approach,
    }

    return {
        "trade_summary": trade_summary,
        "exposure": {
            "e_star": exposure["e_star"],
            "exposure_leg": exposure["exposure_leg"],
            "collateral_leg": exposure["collateral_leg"],
            "security_haircut": exposure["security_haircut_scaled"],
            "h_fx": exposure["h_fx"],
            "overcollateralization_pct": exposure["overcollateralization"],
        },
        "ccr": {
            "rwa": ccr["rwa"],
            "risk_weight_pct": ccr.get("risk_weight_pct", 0.0),
        },
        "cva": {
            "cva_capital": cva["cva_capital"],
            "cva_rwa": cva["cva_rwa"],
            "details": cva["details"],
        },
        "market_risk": {
            "rwa": market_risk["rwa"],
            "details": market_risk["details"],
        },
        "total_rwa": total_rwa,
        "total_capital": total_capital,
    }


# =============================================================================
# Convenience functions
# =============================================================================

def quick_repo_rwa(
    cash_amount: float,
    securities_value: float = None,
    maturity: float = 0.25,
    is_repo: bool = True,
    security_type: str = "sovereign_debt",
    security_rating: str = "AAA",
    counterparty_rating: str = "A",
    approach: str = "sa",
) -> dict:
    """
    Minimal-input repo RWA calculation with sensible defaults.

    Parameters
    ----------
    cash_amount : float
        Cash leg of the repo.
    securities_value : float
        Market value of securities leg (defaults to 102% of cash).
    maturity : float
        Remaining maturity in years.
    is_repo : bool
        True = repo (lend securities), False = reverse repo (lend cash).
    security_type : str
        Type of securities (sovereign_debt, corporate_bond, equity_main_index, etc.).
    security_rating : str
        Rating of the securities issuer.
    counterparty_rating : str
        Counterparty credit rating.
    approach : str
        "sa" or "irb".

    Returns
    -------
    dict
        Full RWA breakdown from calculate_repo_rwa.
    """
    if securities_value is None:
        securities_value = cash_amount * 1.02  # 2% overcollateralisation

    trade = RepoTrade(
        cash_amount=cash_amount,
        securities_value=securities_value,
        maturity=maturity,
        is_repo=is_repo,
        security_type=security_type,
        security_rating=security_rating,
        counterparty_rating=counterparty_rating,
        approach=approach,
    )
    return calculate_repo_rwa(trade)


def compare_repo_vs_reverse(
    cash_amount: float,
    securities_value: float = None,
    maturity: float = 0.25,
    security_type: str = "sovereign_debt",
    security_rating: str = "AAA",
    counterparty_rating: str = "A",
    approach: str = "sa",
) -> dict:
    """
    Compare RWA for repo vs. reverse repo on the same terms.

    Returns a dict with 'repo', 'reverse_repo', and 'comparison' keys.
    """
    if securities_value is None:
        securities_value = cash_amount * 1.02

    repo = quick_repo_rwa(
        cash_amount, securities_value, maturity,
        is_repo=True,
        security_type=security_type,
        security_rating=security_rating,
        counterparty_rating=counterparty_rating,
        approach=approach,
    )
    reverse = quick_repo_rwa(
        cash_amount, securities_value, maturity,
        is_repo=False,
        security_type=security_type,
        security_rating=security_rating,
        counterparty_rating=counterparty_rating,
        approach=approach,
    )

    return {
        "repo": repo,
        "reverse_repo": reverse,
        "comparison": {
            "repo_total_rwa": repo["total_rwa"],
            "reverse_total_rwa": reverse["total_rwa"],
            "rwa_difference": repo["total_rwa"] - reverse["total_rwa"],
            "repo_capital": repo["total_capital"],
            "reverse_capital": reverse["total_capital"],
        },
    }


# =============================================================================
# CLI demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Repo RWA Calculator")
    print("=" * 70)

    result = quick_repo_rwa(50_000_000, securities_value=51_000_000, maturity=0.25,
                            security_type="sovereign_debt", security_rating="AAA")

    ts = result["trade_summary"]
    print(f"\n  Direction:        {ts['direction']}")
    print(f"  Cash Amount:      ${ts['cash_amount']:,.0f}")
    print(f"  Securities Value: ${ts['securities_value']:,.0f}")
    print(f"  Maturity:         {ts['maturity']}y")
    print(f"  Security Type:    {ts['security_type']}")
    print(f"  Security Rating:  {ts['security_rating']}")
    print(f"  Counterparty:     {ts['counterparty_rating']}")
    print(f"  Approach:         {ts['approach']}")
    print(f"  Haircut Approach: {ts['haircut_approach']}")

    print(f"\n  --- Exposure (Comprehensive Approach) ---")
    exp = result["exposure"]
    print(f"  Exposure Leg:     ${exp['exposure_leg']:,.0f}")
    print(f"  Collateral Leg:   ${exp['collateral_leg']:,.0f}")
    print(f"  Security Haircut: {exp['security_haircut']*100:.2f}%")
    print(f"  FX Haircut:       {exp['h_fx']*100:.2f}%")
    print(f"  Overcollateral:   {exp['overcollateralization_pct']:.2f}%")
    print(f"  Net Exposure E*:  ${exp['e_star']:,.0f}")

    print(f"\n  --- Credit Risk on E* ---")
    print(f"  Risk Weight:      {result['ccr']['risk_weight_pct']:.1f}%")
    print(f"  CCR RWA:          ${result['ccr']['rwa']:,.0f}")

    print(f"\n  --- CVA ---")
    print(f"  CVA RWA:          ${result['cva']['cva_rwa']:,.0f}  ({result['cva']['details']})")

    print(f"\n  --- Market Risk ---")
    print(f"  Market Risk RWA:  ${result['market_risk']['rwa']:,.0f}  ({result['market_risk']['details']})")

    print(f"\n  {'='*40}")
    print(f"  TOTAL RWA:        ${result['total_rwa']:,.0f}")
    print(f"  TOTAL CAPITAL:    ${result['total_capital']:,.0f}")

    print("\n" + "=" * 70)
    print("Repo vs Reverse Repo Comparison")
    print("=" * 70)

    comp = compare_repo_vs_reverse(50_000_000, securities_value=51_000_000, maturity=0.25)
    c = comp["comparison"]
    print(f"\n  Repo Total RWA:       ${c['repo_total_rwa']:,.0f}")
    print(f"  Reverse Total RWA:    ${c['reverse_total_rwa']:,.0f}")
    print(f"  RWA Difference:       ${c['rwa_difference']:,.0f}")
    print(f"  Repo Capital:         ${c['repo_capital']:,.0f}")
    print(f"  Reverse Capital:      ${c['reverse_capital']:,.0f}")
