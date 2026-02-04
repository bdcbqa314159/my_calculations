#!/usr/bin/env python3
"""
Repo / Reverse Repo — Full Capital Stack

A Repo (Securities Financing Transaction) generates capital charges from:

  1. Counterparty Credit Risk (CCR)  — Comprehensive Approach with haircuts
  2. CVA Risk Capital                — EXEMPT for SFTs (MAR50.7)
  3. Credit Risk                     — on the net exposure E* after haircuts
  4. Market Risk                     — typically banking book → no FRTB
                                       if trading book: IR + DRC on the bond

What makes a Repo special?
  - CVA is EXEMPT for securities financing transactions.
  - The exposure is calculated using the Comprehensive Approach:
        E* = max(0,  E×(1+He) − C×(1−Hc−Hfx))
    where E = cash lent, C = securities received (for reverse repo),
    He/Hc/Hfx = supervisory haircuts scaled for holding period.
  - Haircut scaling: H_adj = H × sqrt(holding_period / 10 business days)
  - Most repos live in the BANKING BOOK → no FRTB market risk.
    Only repos in the TRADING BOOK generate FRTB-SA/IMA charges.
  - For trading-book repos, the IR sensitivity of the bond drives ES,
    and the bond issuer contributes to DRC.
  - Repo maturity is typically very short (O/N to 3 months), so the
    ES liquidity horizon for IR (10 days) is particularly relevant.

Usage:
    cd /Users/bernardocohen/repos/work/rwa_calc
    ./venv/bin/python examples/repo_full_capital.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repo_rwa import RepoTrade, calculate_repo_rwa
from market_risk import calculate_frtb_sa
from frtb_ima import (
    ESRiskFactor, DRCPosition, FRTBIMAConfig,
    calculate_frtb_ima_capital,
)
from rwa_calc import RATING_TO_PD


def run_repo_example(trade: RepoTrade, label: str, is_trading_book: bool = False):
    """Run the full capital stack for a repo trade."""

    print("=" * 72)
    print(f"Repo Full Capital Stack — {label}")
    print("=" * 72)
    direction_str = "Repo (borrow cash, pledge securities)" if trade.is_repo \
                    else "Reverse Repo (lend cash, receive securities)"
    print(f"  Direction:     {direction_str}")
    print(f"  Cash:          ${trade.cash_amount:,.0f}")
    print(f"  Securities:    ${trade.securities_value:,.0f}")
    print(f"  Collateral:    {trade.security_type} ({trade.security_rating})")
    print(f"  Counterparty:  {trade.counterparty_rating} ({trade.counterparty_sector})")
    print(f"  Book:          {'Trading' if is_trading_book else 'Banking'}")

    # -----------------------------------------------------------------
    # Credit RWA  (Comprehensive Approach)
    # -----------------------------------------------------------------
    credit_result = calculate_repo_rwa(trade)

    print(f"\n  Credit RWA (repo_rwa)")
    print(f"    Net exposure (E*):   ${credit_result['exposure']['e_star']:>14,.0f}")
    print(f"    Security haircut:    {credit_result['exposure']['security_haircut']*100:>13.2f}%")
    print(f"    CCR RWA:             ${credit_result['ccr']['rwa']:>14,.0f}")
    print(f"    CVA:                         EXEMPT  (SFT)")
    print(f"    Total credit RWA:    ${credit_result['total_rwa']:>14,.0f}")

    # -----------------------------------------------------------------
    # Market Risk  (only if trading book)
    # -----------------------------------------------------------------
    if not is_trading_book:
        print(f"\n  Market Risk:           Banking book → no FRTB charges")
        print(f"\n  {'='*50}")
        print(f"  TOTAL RWA:                        ${credit_result['total_rwa']:>14,.0f}")
        print(f"  {'='*50}")
        return credit_result, None, None

    # For trading-book repo: the bond generates IR + credit spread risk
    bond_notional = trade.securities_value
    bond_rating = trade.security_rating

    # Duration approximation (use maturity bucket as a proxy)
    bucket_to_years = {"1y": 1.0, "5y": 5.0, "long": 10.0}
    bond_mat = bucket_to_years.get(trade.security_maturity_bucket, 5.0)
    coupon_rate = 0.04  # assume 4% coupon
    mod_duration = (1 - (1 + coupon_rate)**(-bond_mat)) / coupon_rate
    dv01 = bond_notional * mod_duration * 0.0001   # per 1bp

    # Direction: reverse repo = long the bond (we hold it)
    direction = -1.0 if trade.is_repo else 1.0

    # FRTB-SA: GIRR (interest rate) + CSR (credit spread)
    ir_sensitivity = direction * dv01
    cs01 = bond_notional * mod_duration * 0.0001 * direction

    if bond_rating in ("AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-"):
        csr_bucket = "corporate_IG"
        csr_rw = 1.0
        cr_sub = "IG_corporate"
    else:
        csr_bucket = "corporate_HY"
        csr_rw = 5.0
        cr_sub = "HY"

    delta_positions_sa = {
        "GIRR": [{"bucket": "5Y", "sensitivity": ir_sensitivity, "risk_weight": 1.1}],
        "CSR": [{"bucket": csr_bucket, "sensitivity": cs01, "risk_weight": csr_rw}],
    }

    # DRC for SA: bond issuer
    drc_sa = [{"obligor": f"issuer_{bond_rating}", "notional": bond_notional,
               "rating": bond_rating, "seniority": "senior", "sector": "corporate",
               "is_long": not trade.is_repo}]

    sa_result = calculate_frtb_sa(delta_positions=delta_positions_sa, drc_positions=drc_sa)

    print(f"\n  FRTB-SA (trading book)")
    print(f"    DV01:                ${abs(dv01):>14,.0f}")
    print(f"    GIRR SbM:            ${sa_result['sbm_by_risk_class'].get('GIRR', {}).get('total_capital', 0):>14,.0f}")
    print(f"    CSR SbM:             ${sa_result['sbm_by_risk_class'].get('CSR', {}).get('total_capital', 0):>14,.0f}")
    print(f"    DRC:                 ${sa_result['drc_capital']:>14,.0f}")
    print(f"    Total FRTB-SA:       ${sa_result['total_capital']:>14,.0f}")

    # FRTB-IMA
    # IR risk: rates vol ~ 80bp annualized → 10d vol
    ir_vol_10d = 0.0080 / (252**0.5) * (10**0.5)  # annualized → 10d
    es_ir_10d = abs(dv01 * ir_vol_10d * 10000) * 2.338  # dollar ES

    # Credit spread risk
    spread_vol_10d = 100 * 0.10
    es_cr_10d = abs(cs01) * spread_vol_10d * 2.338

    es_factors = [
        ESRiskFactor("IR", "major", es_ir_10d, stressed_es_10day=es_ir_10d * 1.5),
        ESRiskFactor("CR", cr_sub, es_cr_10d, stressed_es_10day=es_cr_10d * 2.0),
    ]

    ref_pd = RATING_TO_PD.get(bond_rating, 0.004)
    drc_ima = [DRCPosition(
        "repo_bond", f"issuer_{bond_rating}", bond_notional, bond_notional,
        pd=ref_pd, lgd=0.55, sector="corporate", systematic_factor=0.18,
        is_long=not trade.is_repo,
    )]

    ima_config = FRTBIMAConfig(drc_num_simulations=50_000)
    ima_result = calculate_frtb_ima_capital(es_factors, drc_ima, ima_config)

    print(f"\n  FRTB-IMA (trading book)")
    print(f"    ES (IR + CR):        ${ima_result['es']['es_total']:>14,.0f}")
    print(f"    SES:                 ${ima_result['ses']['ses_total']:>14,.0f}")
    print(f"    IMCC:                ${ima_result['imcc']:>14,.0f}")
    print(f"    DRC (99.9%):         ${ima_result['drc_charge']:>14,.0f}")
    print(f"    Total IMA capital:   ${ima_result['total_capital']:>14,.0f}")

    print(f"\n  {'='*50}")
    print(f"  Credit RWA:                       ${credit_result['total_rwa']:>14,.0f}")
    print(f"  Market RWA (SA):                  ${sa_result['total_rwa']:>14,.0f}")
    print(f"  Market RWA (IMA):                 ${ima_result['total_rwa']:>14,.0f}")
    print(f"  Combined (SA):                    ${credit_result['total_rwa'] + sa_result['total_rwa']:>14,.0f}")
    print(f"  Combined (IMA):                   ${credit_result['total_rwa'] + ima_result['total_rwa']:>14,.0f}")
    print(f"  {'='*50}")
    return credit_result, sa_result, ima_result


# =====================================================================
# Example 1:  Banking-Book Reverse Repo  (no FRTB)
# =====================================================================

banking_repo = RepoTrade(
    cash_amount=100_000_000,
    securities_value=105_000_000,        # 5% over-collateralized
    is_repo=False,                       # reverse repo: we lend cash
    security_type="sovereign_debt",
    security_rating="AA",
    security_maturity_bucket="5y",
    counterparty_rating="BBB",
    holding_period_days=10,
)

run_repo_example(banking_repo, "Banking Book Reverse Repo (no FRTB)")

print("\n\n")

# =====================================================================
# Example 2:  Trading-Book Reverse Repo  (with FRTB)
# =====================================================================

trading_repo = RepoTrade(
    cash_amount=50_000_000,
    securities_value=52_000_000,
    is_repo=False,                       # reverse repo
    security_type="corporate_bond",
    security_rating="BBB",
    security_maturity_bucket="5y",
    counterparty_rating="A",
    holding_period_days=10,
)

run_repo_example(trading_repo, "Trading Book Reverse Repo (with FRTB)", is_trading_book=True)
