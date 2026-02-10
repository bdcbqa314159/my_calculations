#!/usr/bin/env python3
"""
CLN (Credit-Linked Note) — Full Capital Stack

A Credit-Linked Note is a FUNDED credit derivative: the investor buys a
note whose redemption is contingent on a reference entity not defaulting.

Capital charges:

  1. Counterparty Credit Risk (CCR)  — NONE (funded instrument, like a bond)
  2. CVA Risk Capital                — NONE (not a derivative in CCR sense)
  3. Credit Risk                     — DUAL default: reference entity + issuer
  4. Market Risk                     — FRTB-SA / FRTB-IMA on credit spreads + IR

What makes a CLN special?
  - NO CCR and NO CVA because the investor has already paid cash upfront.
    (Compare with CDS where the protection seller has unfunded exposure.)
  - DUAL CREDIT EXPOSURE: the investor loses if EITHER the reference entity
    OR the note issuer defaults.  Under Basel III:
      • Banking book: first-to-default treatment (CRE22) — risk weight is
        the higher of the two obligors' risk weights.
      • Trading book: two separate DRC positions and two CR risk factors.
  - For FRTB-IMA, the ES includes BOTH:
      • Reference entity credit spread (CR risk class)
      • Issuer credit spread (CR risk class, possibly different sub-category)
      • Interest rate risk on the note's fixed coupon (IR risk class)
  - The DRC model must capture the CORRELATION between the reference entity
    and the issuer — a CLN concentrates wrong-way risk when the issuer
    and reference entity are in the same sector.

Usage:
    cd rwa_calc
    ./venv/bin/python examples/cln_full_capital.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Optional

from rwa_calc import RATING_TO_PD, calculate_sa_rwa
from market_risk import calculate_frtb_sa
from frtb_ima import (
    ESRiskFactor, DRCPosition, FRTBIMAConfig,
    calculate_frtb_ima_capital,
)


# =====================================================================
# CLN data model  (not in the base library — defined here)
# =====================================================================

@dataclass
class CLNTrade:
    """Credit-Linked Note trade parameters."""
    notional: float               # face value of the note
    coupon_rate: float            # annual coupon (e.g. 0.05 = 5%)
    maturity_years: float
    # Reference entity (embedded credit derivative)
    reference_entity: str
    reference_rating: str
    reference_sector: str = "corporate"
    reference_recovery: float = 0.40
    # Note issuer (funding risk)
    issuer: str = "SPV"
    issuer_rating: str = "A"
    issuer_sector: str = "financial"
    issuer_recovery: float = 0.40
    # Book assignment
    is_trading_book: bool = True


def calculate_cln_credit_rwa(trade: CLNTrade) -> dict:
    """
    Banking-book credit RWA for a CLN.

    Under CRE22 (first-to-default baskets with ≤2 names), the risk weight
    is the HIGHER of:
      - Reference entity risk weight
      - Issuer risk weight

    This is a conservative treatment reflecting dual default exposure.
    """
    ref_rwa = calculate_sa_rwa(trade.notional, "corporate", trade.reference_rating)
    issuer_rwa = calculate_sa_rwa(trade.notional, "corporate", trade.issuer_rating)

    # First-to-default: use the worse (higher) risk weight
    if ref_rwa["risk_weight_pct"] >= issuer_rwa["risk_weight_pct"]:
        binding = "reference_entity"
        rw = ref_rwa["risk_weight_pct"]
    else:
        binding = "issuer"
        rw = issuer_rwa["risk_weight_pct"]

    rwa = trade.notional * rw / 100

    return {
        "approach": "SA-CR (first-to-default)",
        "binding_obligor": binding,
        "risk_weight_pct": rw,
        "rwa": rwa,
        "reference_rw": ref_rwa["risk_weight_pct"],
        "issuer_rw": issuer_rwa["risk_weight_pct"],
        "ccr_rwa": 0.0,   # funded — no CCR
        "cva_rwa": 0.0,   # funded — no CVA
    }


def run_cln_example(trade: CLNTrade, label: str):
    """Run the full capital stack for a CLN."""

    print("=" * 72)
    print(f"CLN Full Capital Stack — {label}")
    print("=" * 72)
    print(f"  Notional:        ${trade.notional:,.0f}")
    print(f"  Coupon:          {trade.coupon_rate*100:.1f}%,  Maturity: {trade.maturity_years}y")
    print(f"  Reference:       {trade.reference_entity} ({trade.reference_rating}, "
          f"{trade.reference_sector})")
    print(f"  Issuer:          {trade.issuer} ({trade.issuer_rating}, {trade.issuer_sector})")
    print(f"  Book:            {'Trading' if trade.is_trading_book else 'Banking'}")

    # -----------------------------------------------------------------
    # Credit RWA  (no CCR, no CVA — funded note)
    # -----------------------------------------------------------------
    credit_result = calculate_cln_credit_rwa(trade)

    print(f"\n  Credit RWA")
    print(f"    CCR:                              none (funded)")
    print(f"    CVA:                              none (funded)")
    print(f"    Reference entity RW:     {credit_result['reference_rw']:>13.0f}%")
    print(f"    Issuer RW:               {credit_result['issuer_rw']:>13.0f}%")
    print(f"    Binding obligor:         {credit_result['binding_obligor']:>14}")
    print(f"    Applied RW:              {credit_result['risk_weight_pct']:>13.0f}%")
    print(f"    Credit RWA:              ${credit_result['rwa']:>14,.0f}")

    if not trade.is_trading_book:
        print(f"\n  Market Risk:               Banking book → no FRTB")
        print(f"\n  {'='*50}")
        print(f"  TOTAL RWA:                        ${credit_result['rwa']:>14,.0f}")
        print(f"  {'='*50}")
        return credit_result, None, None

    # -----------------------------------------------------------------
    # FRTB-SA:  two CSR sensitivities + GIRR + two DRC positions
    # -----------------------------------------------------------------
    # Duration for spread/rate sensitivity
    mod_duration = (1 - (1 + trade.coupon_rate)**(-trade.maturity_years)) / trade.coupon_rate

    # CS01 on reference entity
    ref_cs01 = trade.notional * mod_duration * 0.0001
    # CS01 on issuer (issuer spread also affects the note price)
    iss_cs01 = trade.notional * mod_duration * 0.0001 * 0.3  # partial sensitivity

    def _csr_params(rating):
        if rating in ("AAA","AA+","AA","AA-","A+","A","A-","BBB+","BBB","BBB-"):
            return "corporate_IG", 1.0, "IG_corporate"
        return "corporate_HY", 5.0, "HY"

    ref_bucket, ref_rw, ref_cr_sub = _csr_params(trade.reference_rating)
    iss_bucket, iss_rw, iss_cr_sub = _csr_params(trade.issuer_rating)

    # IR sensitivity (DV01)
    dv01 = trade.notional * mod_duration * 0.0001

    delta_positions_sa = {
        "CSR": [
            {"bucket": ref_bucket, "sensitivity": ref_cs01, "risk_weight": ref_rw},
            {"bucket": iss_bucket, "sensitivity": iss_cs01, "risk_weight": iss_rw},
        ],
        "GIRR": [
            {"bucket": "5Y", "sensitivity": dv01, "risk_weight": 1.1},
        ],
    }

    ref_pd = RATING_TO_PD.get(trade.reference_rating, 0.004)
    iss_pd = RATING_TO_PD.get(trade.issuer_rating, 0.004)

    drc_sa = [
        {"obligor": trade.reference_entity, "notional": trade.notional,
         "rating": trade.reference_rating, "seniority": "senior",
         "sector": trade.reference_sector, "is_long": True},
        {"obligor": trade.issuer, "notional": trade.notional,
         "rating": trade.issuer_rating, "seniority": "senior",
         "sector": trade.issuer_sector, "is_long": True},
    ]

    sa_result = calculate_frtb_sa(delta_positions=delta_positions_sa, drc_positions=drc_sa)

    print(f"\n  FRTB-SA")
    print(f"    GIRR SbM:            ${sa_result['sbm_by_risk_class'].get('GIRR', {}).get('total_capital', 0):>14,.0f}")
    print(f"    CSR SbM:             ${sa_result['sbm_by_risk_class'].get('CSR', {}).get('total_capital', 0):>14,.0f}")
    print(f"    DRC (ref + issuer):  ${sa_result['drc_capital']:>14,.0f}")
    print(f"    Total FRTB-SA:       ${sa_result['total_capital']:>14,.0f}")

    # -----------------------------------------------------------------
    # FRTB-IMA:  ES on two credit spread factors + IR + DRC on both names
    # -----------------------------------------------------------------
    # Reference entity spread ES
    ref_spread_vol = 150 * 0.10  # 150bp avg spread, 10% vol
    es_ref_10d = ref_cs01 * ref_spread_vol * 2.338

    # Issuer spread ES
    iss_spread_vol = 80 * 0.08
    es_iss_10d = iss_cs01 * iss_spread_vol * 2.338

    # IR ES
    ir_vol_10d = 0.0080 / (252**0.5) * (10**0.5)
    es_ir_10d = abs(dv01 * ir_vol_10d * 10000) * 2.338

    es_factors = [
        ESRiskFactor("CR", ref_cr_sub, es_ref_10d, stressed_es_10day=es_ref_10d * 2.0),
        ESRiskFactor("CR", iss_cr_sub, es_iss_10d, stressed_es_10day=es_iss_10d * 1.5),
        ESRiskFactor("IR", "major", es_ir_10d, stressed_es_10day=es_ir_10d * 1.5),
    ]

    # DRC: TWO positions — the key CLN feature
    # If reference and issuer are in the same sector, use higher systematic_factor
    # to capture wrong-way risk correlation
    same_sector = trade.reference_sector == trade.issuer_sector
    rho_ref = 0.24 if same_sector else 0.20
    rho_iss = 0.24 if same_sector else 0.18

    drc_ima = [
        DRCPosition(
            f"cln_ref", trade.reference_entity,
            trade.notional, trade.notional,
            pd=ref_pd, lgd=1.0 - trade.reference_recovery,
            sector=trade.reference_sector, systematic_factor=rho_ref,
            is_long=True,
        ),
        DRCPosition(
            f"cln_iss", trade.issuer,
            trade.notional, trade.notional,
            pd=iss_pd, lgd=1.0 - trade.issuer_recovery,
            sector=trade.issuer_sector, systematic_factor=rho_iss,
            is_long=True,
        ),
    ]

    ima_config = FRTBIMAConfig(drc_num_simulations=50_000, backtesting_exceptions=1)
    ima_result = calculate_frtb_ima_capital(es_factors, drc_ima, ima_config)

    print(f"\n  FRTB-IMA")
    print(f"    ES (ref CR + iss CR + IR): ${ima_result['es']['es_total']:>11,.0f}")
    print(f"    SES:                 ${ima_result['ses']['ses_total']:>14,.0f}")
    print(f"    IMCC:                ${ima_result['imcc']:>14,.0f}")
    print(f"    DRC (99.9%, 2 names):${ima_result['drc_charge']:>14,.0f}")
    print(f"      mean loss:         ${ima_result['drc_detail']['mean_loss']:>14,.0f}")
    print(f"      99% loss:          ${ima_result['drc_detail']['percentile_99']:>14,.0f}")
    print(f"    Total IMA capital:   ${ima_result['total_capital']:>14,.0f}")

    print(f"\n  {'='*50}")
    print(f"  Credit RWA (funded, dual default):${credit_result['rwa']:>14,.0f}")
    print(f"  Market RWA (SA):                  ${sa_result['total_rwa']:>14,.0f}")
    print(f"  Market RWA (IMA):                 ${ima_result['total_rwa']:>14,.0f}")
    print(f"  Combined (SA):                    ${credit_result['rwa'] + sa_result['total_rwa']:>14,.0f}")
    print(f"  Combined (IMA):                   ${credit_result['rwa'] + ima_result['total_rwa']:>14,.0f}")
    print(f"  {'='*50}")
    return credit_result, sa_result, ima_result


# =====================================================================
# Example 1:  IG CLN  (reference IG, issuer IG)
# =====================================================================

cln_ig = CLNTrade(
    notional=20_000_000,
    coupon_rate=0.045,
    maturity_years=5.0,
    reference_entity="Acme Corp",
    reference_rating="BBB",
    reference_sector="industrial",
    reference_recovery=0.40,
    issuer="Bank SPV I",
    issuer_rating="A",
    issuer_sector="financial",
    issuer_recovery=0.45,
    is_trading_book=True,
)

run_cln_example(cln_ig, "IG Reference + IG Issuer")

print("\n\n")

# =====================================================================
# Example 2:  Wrong-way CLN  (same sector, HY reference)
# =====================================================================

cln_wwr = CLNTrade(
    notional=15_000_000,
    coupon_rate=0.075,
    maturity_years=3.0,
    reference_entity="Energy Co",
    reference_rating="BB",
    reference_sector="energy",
    reference_recovery=0.30,
    issuer="Energy Finance SPV",
    issuer_rating="BBB-",
    issuer_sector="energy",          # SAME sector as reference → wrong-way risk
    issuer_recovery=0.35,
    is_trading_book=True,
)

run_cln_example(cln_wwr, "Wrong-Way Risk (same sector, HY reference)")
