#!/usr/bin/env python3
"""
CDS — Full Capital Stack (Credit RWA + FRTB-IMA + FRTB-SA)

A Credit Default Swap generates capital charges across four pillars:

  1. Counterparty Credit Risk (CCR)  — SA-CCR exposure on the dealer
  2. CVA Risk Capital                — BA-CVA charge on the dealer
  3. Credit Risk on Reference Entity — protection seller only
  4. Market Risk                     — FRTB-SA (credit spread sensitivity + DRC)
                                       FRTB-IMA (ES on credit spread + DRC Monte Carlo)

What makes a CDS special?
  - The protection direction (buyer vs seller) flips the sign of both the
    SA-CCR delta AND the FRTB-IMA DRC position.
  - The reference entity's rating drives the ES sub-category (IG vs HY)
    and the DRC PD.
  - The counterparty (dealer) is the CCR/CVA exposure; the reference entity
    is the credit-risk / market-risk exposure.  These are different obligors.
  - CDS spread × risky duration is the main credit-spread sensitivity that
    feeds into FRTB-SA CSR delta and FRTB-IMA ES.

Usage:
    cd rwa_calc
    ./venv/bin/python examples/cds_full_capital.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cds_rwa import CDSTrade, calculate_cds_rwa
from market_risk import calculate_frtb_sa
from frtb_ima import (
    ESRiskFactor, DRCPosition, FRTBIMAConfig,
    calculate_frtb_ima_capital,
)
from rwa_calc import RATING_TO_PD


# =====================================================================
# 1.  Define the trade
# =====================================================================
# CDSTrade fields:
#   notional, maturity, is_protection_buyer, is_index, spread_bps, mtm,
#   recovery_rate, reference_entity_pd, reference_entity_rating,
#   reference_entity_sector, counterparty_pd, counterparty_rating,
#   counterparty_sector, approach, book, collateral_held,
#   collateral_posted, is_margined

trade = CDSTrade(
    notional=50_000_000,
    maturity=5.0,
    spread_bps=150,                        # 150 bp running spread
    is_protection_buyer=False,             # we SELL protection → long credit risk
    reference_entity_rating="BBB",
    reference_entity_sector="corporate",
    counterparty_rating="A",
    counterparty_sector="financial",
    recovery_rate=0.40,
    book="trading",                        # sits in the trading book
    collateral_held=2_000_000,
)

ref_rating = trade.reference_entity_rating
ref_pd = RATING_TO_PD.get(ref_rating, 0.004)

print("=" * 72)
print("CDS Full Capital Stack")
print("=" * 72)
direction_str = "Protection Seller (long credit)" if not trade.is_protection_buyer \
                else "Protection Buyer (short credit)"
print(f"  Notional:      ${trade.notional:,.0f}")
print(f"  Direction:     {direction_str}")
print(f"  Reference:     {ref_rating} ({trade.reference_entity_sector})")
print(f"  Counterparty:  {trade.counterparty_rating} ({trade.counterparty_sector})")
print(f"  Spread:        {trade.spread_bps} bp,  Maturity: {trade.maturity}y")


# =====================================================================
# 2.  Credit RWA  (CCR + CVA + Reference Credit Risk)
# =====================================================================

credit_result = calculate_cds_rwa(trade)

print("\n" + "-" * 72)
print("PILLAR 1 — Credit RWA  (cds_rwa module)")
print("-" * 72)
print(f"  SA-CCR EAD:            ${credit_result['ccr']['sa_ccr_ead']:>14,.0f}")
print(f"  CCR RWA:               ${credit_result['ccr']['ccr_rwa']:>14,.0f}")
print(f"  CVA capital:           ${credit_result['cva']['cva_capital']:>14,.0f}")
print(f"  CVA RWA:               ${credit_result['cva']['cva_rwa']:>14,.0f}")
print(f"  Reference credit RWA:  ${credit_result['credit_risk']['rwa']:>14,.0f}")
print(f"  Market risk (basic):   ${credit_result['market_risk']['rwa']:>14,.0f}")
print(f"  ---")
print(f"  Total credit RWA:      ${credit_result['total_rwa']:>14,.0f}")


# =====================================================================
# 3.  FRTB-SA  (Standardised market risk)
# =====================================================================
#
# For a CDS, the key sensitivity is the credit spread:
#   CS01 ≈ notional × risky_duration × 1bp
# This goes into the CSR (Credit Spread Risk) risk class.

risky_duration = (1 - (1 - trade.recovery_rate)) * trade.maturity  # simplified
cs01 = trade.notional * risky_duration * 0.0001  # per 1bp

# Protection seller is LONG credit spread risk (loses if spreads widen)
direction = 1.0 if not trade.is_protection_buyer else -1.0

# CSR bucket depends on rating: IG vs HY
if ref_rating in ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
                   "BBB+", "BBB", "BBB-"):
    csr_bucket = "corporate_IG"
    csr_rw = 1.0   # 1% risk weight for IG corporate (MAR21.53)
else:
    csr_bucket = "corporate_HY"
    csr_rw = 5.0   # 5% for HY corporate

delta_positions_sa = {
    "CSR": [
        {
            "bucket": csr_bucket,
            "sensitivity": direction * cs01,
            "risk_weight": csr_rw,
        }
    ],
}

# DRC position for SA
drc_positions_sa = [
    {
        "obligor": f"ref_{ref_rating}",
        "notional": trade.notional,
        "rating": ref_rating,
        "seniority": "senior",
        "sector": trade.reference_entity_sector,
        "is_long": not trade.is_protection_buyer,  # seller = long credit
    }
]

sa_result = calculate_frtb_sa(
    delta_positions=delta_positions_sa,
    drc_positions=drc_positions_sa,
)

print("\n" + "-" * 72)
print("PILLAR 2a — FRTB Standardised Approach  (market_risk module)")
print("-" * 72)
print(f"  CS01 (1bp):            ${cs01:>14,.0f}")
print(f"  CSR bucket:            {csr_bucket:>14}")
print(f"  SbM capital:           ${sa_result['sbm_capital']:>14,.0f}")
print(f"  DRC capital:           ${sa_result['drc_capital']:>14,.0f}")
print(f"  Total FRTB-SA:         ${sa_result['total_capital']:>14,.0f}")
print(f"  FRTB-SA RWA:           ${sa_result['total_rwa']:>14,.0f}")


# =====================================================================
# 4.  FRTB-IMA  (Internal Models — ES + Monte Carlo DRC)
# =====================================================================
#
# CDS-specific mapping:
#   - ES risk factor: credit spread → CR risk class
#       sub_category depends on rating:
#         IG sovereign → "IG_sovereign" (20d LH)
#         IG corporate → "IG_corporate" (40d LH)
#         HY           → "HY"           (60d LH)
#   - The 10-day ES is estimated from the CS01 and a spread vol assumption.
#   - DRC position: reference entity with PD from rating, LGD = 1 - recovery.
#   - Direction: seller = long credit = is_long=True in DRC.

spread_vol_10d = trade.spread_bps * 0.10   # assume 10% 10-day spread vol
es_10day = cs01 * spread_vol_10d * 2.338   # ES ≈ VaR × (ES/VaR ratio at 97.5%)

# Stressed ES: use a stress multiplier (e.g., 2× spread vol)
stressed_es_10day = es_10day * 2.0

# Sub-category for liquidity horizon
if ref_rating in ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
                   "BBB+", "BBB", "BBB-"):
    cr_sub = "IG_corporate"  # 40-day liquidity horizon
else:
    cr_sub = "HY"            # 60-day liquidity horizon

es_risk_factors = [
    ESRiskFactor(
        risk_class="CR",
        sub_category=cr_sub,
        es_10day=abs(es_10day),
        stressed_es_10day=abs(stressed_es_10day),
    ),
]

# DRC position for IMA Monte Carlo
drc_positions_ima = [
    DRCPosition(
        position_id="cds_ref",
        obligor=f"ref_{ref_rating}",
        notional=trade.notional,
        market_value=trade.notional,
        pd=ref_pd,
        lgd=1.0 - trade.recovery_rate,
        seniority="senior_unsecured",
        sector=trade.reference_entity_sector,
        systematic_factor=0.20,
        is_long=not trade.is_protection_buyer,
    ),
]

ima_config = FRTBIMAConfig(
    plus_factor=0.0,
    drc_num_simulations=50_000,
    backtesting_exceptions=2,
)

ima_result = calculate_frtb_ima_capital(
    es_risk_factors, drc_positions_ima, ima_config,
)

print("\n" + "-" * 72)
print("PILLAR 2b — FRTB Internal Models Approach  (frtb_ima module)")
print("-" * 72)
print(f"  ES (liquidity-adj):    ${ima_result['es']['es_total']:>14,.0f}")
print(f"  SES:                   ${ima_result['ses']['ses_total']:>14,.0f}")
print(f"  NMRF:                  ${ima_result['imcc_detail']['nmrf']:>14,.0f}")
print(f"  IMCC:                  ${ima_result['imcc']:>14,.0f}")
print(f"  DRC (99.9%):           ${ima_result['drc_charge']:>14,.0f}")
print(f"    mean loss:           ${ima_result['drc_detail']['mean_loss']:>14,.0f}")
print(f"    99% loss:            ${ima_result['drc_detail']['percentile_99']:>14,.0f}")
print(f"  ---")
print(f"  Total IMA capital:     ${ima_result['total_capital']:>14,.0f}")
print(f"  Total IMA RWA:         ${ima_result['total_rwa']:>14,.0f}")

bt = ima_result['backtesting']
print(f"\n  Backtesting:  {bt['num_exceptions']} exceptions → {bt['zone']} zone "
      f"(plus_factor={bt['plus_factor']:.2f})")


# =====================================================================
# 5.  Combined summary
# =====================================================================

print("\n" + "=" * 72)
print("COMBINED CAPITAL SUMMARY")
print("=" * 72)
print(f"  Credit RWA  (CCR+CVA+Ref):        ${credit_result['total_rwa']:>14,.0f}")
print(f"  Market Risk — FRTB-SA:            ${sa_result['total_rwa']:>14,.0f}")
print(f"  Market Risk — FRTB-IMA:           ${ima_result['total_rwa']:>14,.0f}")
print()
print(f"  Using SA:   total RWA =           ${credit_result['total_rwa'] + sa_result['total_rwa']:>14,.0f}")
print(f"  Using IMA:  total RWA =           ${credit_result['total_rwa'] + ima_result['total_rwa']:>14,.0f}")
