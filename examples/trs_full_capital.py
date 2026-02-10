#!/usr/bin/env python3
"""
TRS — Full Capital Stack (Credit RWA + FRTB-IMA + FRTB-SA)

A Total Return Swap generates capital charges across four pillars:

  1. Counterparty Credit Risk (CCR)  — SA-CCR on the dealer
  2. CVA Risk Capital                — BA-CVA charge on the dealer
  3. Reference/Asset Risk            — synthetic exposure to the underlying
  4. Market Risk                     — FRTB-SA (delta sensitivity + DRC)
                                       FRTB-IMA (ES + DRC if credit underlying)

What makes a TRS special?
  - The UNDERLYING TYPE determines which risk class feeds into ES:
      equity       → EQ (large_cap / small_cap)
      bond / loan  → CR (IG_corporate / HY) + IR for duration risk
      commodity    → COM (energy / precious_metals / other)
      credit index → CR (IG_corporate / HY)
  - Only bond/loan/credit underlyings generate a DRC position.
    Equity and commodity TRS have NO default risk charge.
  - The TRS receiver has a synthetic LONG position in the underlying;
    the payer has a synthetic SHORT.
  - SA-CCR asset class mapping depends on underlying type
    (EQ_SINGLE, CR_*, COM_*, etc.).

Usage:
    cd rwa_calc
    ./venv/bin/python examples/trs_full_capital.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trs_rwa import TRSTrade, calculate_trs_rwa
from market_risk import calculate_frtb_sa
from frtb_ima import (
    ESRiskFactor, DRCPosition, FRTBIMAConfig,
    calculate_frtb_ima_capital,
)
from rwa_calc import RATING_TO_PD


def run_trs_example(trade: TRSTrade, label: str):
    """Run the full capital stack for a single TRS trade."""

    # Resolve underlying rating/pd for later use
    und_rating = trade.underlying_rating or "BBB"
    und_pd = trade.underlying_pd or RATING_TO_PD.get(und_rating, 0.004)

    print("=" * 72)
    print(f"TRS Full Capital Stack — {label}")
    print("=" * 72)
    direction_str = "Receiver (long underlying)" if trade.is_total_return_receiver \
                    else "Payer (short underlying)"
    print(f"  Notional:      ${trade.notional:,.0f}")
    print(f"  Underlying:    {trade.underlying_type} ({und_rating})")
    print(f"  Direction:     {direction_str}")
    print(f"  Counterparty:  {trade.counterparty_rating} ({trade.counterparty_sector})")

    # -----------------------------------------------------------------
    # Credit RWA
    # -----------------------------------------------------------------
    credit_result = calculate_trs_rwa(trade)

    print(f"\n  Credit RWA (trs_rwa)")
    print(f"    SA-CCR EAD:          ${credit_result['ccr']['sa_ccr_ead']:>14,.0f}")
    print(f"    CCR RWA:             ${credit_result['ccr']['ccr_rwa']:>14,.0f}")
    print(f"    CVA RWA:             ${credit_result['cva']['cva_rwa']:>14,.0f}")
    print(f"    Reference risk RWA:  ${credit_result['reference_risk']['rwa']:>14,.0f}")
    print(f"    Total credit RWA:    ${credit_result['total_rwa']:>14,.0f}")

    # -----------------------------------------------------------------
    # Map underlying to FRTB risk classes
    # -----------------------------------------------------------------
    direction = 1.0 if trade.is_total_return_receiver else -1.0
    sensitivity = trade.notional * 0.01 * direction   # 1% sensitivity

    es_factors = []
    delta_sa = {}
    drc_sa = []
    drc_ima = []
    has_drc = False

    if trade.underlying_type in ("equity", "equity_index"):
        # Equity: EQ risk class, no DRC
        is_large = trade.notional >= 10_000_000
        sub_cat = "large_cap" if is_large else "small_cap"
        sa_bucket = "large_cap_developed" if is_large else "small_cap_developed"
        sa_rw = 20 if is_large else 30

        # ES: equity vol assumption (~20% annualized → ~6.3% 10-day)
        eq_vol_10d = trade.notional * 0.20 / (252**0.5) * (10**0.5)
        es_10d = eq_vol_10d * 2.338  # ES/VaR ratio at 97.5%

        es_factors.append(ESRiskFactor("EQ", sub_cat, es_10d,
                                       stressed_es_10day=es_10d * 1.8))
        delta_sa = {"EQ": [{"bucket": sa_bucket, "sensitivity": sensitivity,
                            "risk_weight": sa_rw}]}

    elif trade.underlying_type in ("bond", "loan", "credit", "credit_index"):
        # Credit underlying: CR risk class + DRC
        has_drc = True

        if und_rating in ("AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-"):
            cr_sub = "IG_corporate"
            csr_bucket = "corporate_IG"
            csr_rw = 1.0
        else:
            cr_sub = "HY"
            csr_bucket = "corporate_HY"
            csr_rw = 5.0

        # Spread sensitivity ≈ notional × duration × 1bp
        duration = trade.maturity * 0.9
        cs01 = trade.notional * duration * 0.0001
        spread_vol_10d = 150 * 0.10  # assume 150bp spread, 10% vol
        es_10d = cs01 * spread_vol_10d * 2.338

        es_factors.append(ESRiskFactor("CR", cr_sub, abs(es_10d),
                                       stressed_es_10day=abs(es_10d) * 2.0))
        delta_sa = {"CSR": [{"bucket": csr_bucket, "sensitivity": direction * cs01,
                             "risk_weight": csr_rw}]}

        # DRC
        recovery = 0.40
        drc_sa = [{"obligor": f"und_{und_rating}", "notional": trade.notional,
                   "rating": und_rating, "seniority": "senior",
                   "sector": trade.underlying_sector,
                   "is_long": trade.is_total_return_receiver}]
        drc_ima = [DRCPosition(
            "trs_und", f"und_{und_rating}", trade.notional, trade.notional,
            pd=und_pd, lgd=1.0 - recovery, sector=trade.underlying_sector,
            systematic_factor=0.20, is_long=trade.is_total_return_receiver,
        )]

    elif trade.underlying_type == "commodity":
        # Commodity: COM risk class, no DRC
        com_vol_10d = trade.notional * 0.30 / (252**0.5) * (10**0.5)
        es_10d = com_vol_10d * 2.338

        es_factors.append(ESRiskFactor("COM", "energy", es_10d,
                                       stressed_es_10day=es_10d * 2.0))
        delta_sa = {"COM": [{"bucket": "energy_liquid", "sensitivity": sensitivity,
                             "risk_weight": 25}]}

    # -----------------------------------------------------------------
    # FRTB-SA
    # -----------------------------------------------------------------
    sa_result = calculate_frtb_sa(
        delta_positions=delta_sa,
        drc_positions=drc_sa if has_drc else [],
    )

    print(f"\n  FRTB-SA (market_risk)")
    print(f"    SbM capital:         ${sa_result['sbm_capital']:>14,.0f}")
    if has_drc:
        print(f"    DRC capital:         ${sa_result['drc_capital']:>14,.0f}")
    else:
        print(f"    DRC capital:                      n/a  "
              f"(no default risk for {trade.underlying_type})")
    print(f"    Total FRTB-SA:       ${sa_result['total_capital']:>14,.0f}")

    # -----------------------------------------------------------------
    # FRTB-IMA
    # -----------------------------------------------------------------
    ima_config = FRTBIMAConfig(drc_num_simulations=50_000, backtesting_exceptions=1)
    ima_result = calculate_frtb_ima_capital(es_factors, drc_ima, ima_config)

    print(f"\n  FRTB-IMA (frtb_ima)")
    print(f"    ES:                  ${ima_result['es']['es_total']:>14,.0f}")
    print(f"    SES:                 ${ima_result['ses']['ses_total']:>14,.0f}")
    print(f"    IMCC:                ${ima_result['imcc']:>14,.0f}")
    if has_drc:
        print(f"    DRC (99.9%):         ${ima_result['drc_charge']:>14,.0f}")
    else:
        print(f"    DRC:                              n/a")
    print(f"    Total IMA capital:   ${ima_result['total_capital']:>14,.0f}")

    # -----------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------
    print(f"\n  {'='*50}")
    print(f"  Credit RWA:                       ${credit_result['total_rwa']:>14,.0f}")
    print(f"  Market RWA (SA):                  ${sa_result['total_rwa']:>14,.0f}")
    print(f"  Market RWA (IMA):                 ${ima_result['total_rwa']:>14,.0f}")
    print(f"  Combined (SA):                    ${credit_result['total_rwa'] + sa_result['total_rwa']:>14,.0f}")
    print(f"  Combined (IMA):                   ${credit_result['total_rwa'] + ima_result['total_rwa']:>14,.0f}")
    print(f"  {'='*50}")
    return credit_result, sa_result, ima_result


# =====================================================================
# Example 1:  Equity TRS  (no DRC)
# =====================================================================

eq_trs = TRSTrade(
    notional=30_000_000,
    maturity=3.0,
    underlying_type="equity",
    is_total_return_receiver=True,      # synthetic long equity
    counterparty_rating="A",
    book="trading",
)

run_trs_example(eq_trs, "Equity TRS (Receiver = long equity)")

print("\n\n")

# =====================================================================
# Example 2:  Bond TRS  (has DRC)
# =====================================================================

bond_trs = TRSTrade(
    notional=25_000_000,
    maturity=5.0,
    underlying_type="bond",
    is_total_return_receiver=True,      # synthetic long bond
    underlying_rating="BB",
    underlying_sector="corporate",
    counterparty_rating="AA",
    book="trading",
)

run_trs_example(bond_trs, "Bond TRS (Receiver = long credit, HAS DRC)")
