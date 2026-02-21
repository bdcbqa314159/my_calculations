#!/usr/bin/env python3
"""
FRTB Internal Models Approach (IMA) Example

Demonstrates how to calculate FRTB-IMA capital including:
- Liquidity-adjusted Expected Shortfall (ES)
- Stressed Expected Shortfall (SES)
- Non-Modellable Risk Factor (NMRF) charge
- Internal Default Risk Charge (DRC)
- Backtesting evaluation
- P&L Attribution Test (PLA)

Usage:
    cd rwa_calc
    ./venv/bin/python examples/frtb_ima_example.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frtb_ima import (
    ESRiskFactor,
    DRCPosition,
    DeskPLA,
    FRTBIMAConfig,
    get_liquidity_horizon,
    calculate_liquidity_adjusted_es,
    calculate_stressed_es,
    calculate_nmrf_charge,
    calculate_ima_drc,
    evaluate_backtesting,
    evaluate_pla,
    calculate_imcc,
    calculate_frtb_ima_capital,
    quick_frtb_ima,
    compare_ima_vs_sa,
    LIQUIDITY_HORIZONS,
)


# =============================================================================
# Example 1: Liquidity Horizons
# =============================================================================

print("=" * 70)
print("EXAMPLE 1: Liquidity Horizons (MAR31.13)")
print("=" * 70)

print(f"""
  Risk factors are assigned to liquidity horizons based on their category.
  Longer horizons = less liquid = higher capital.

  {'Risk Class':<8} {'Sub-Category':<18} {'Liquidity Horizon':>18}
  {'-'*50}""")

for (risk_class, sub_cat), lh in sorted(LIQUIDITY_HORIZONS.items(), key=lambda x: (x[1], x[0])):
    print(f"  {risk_class:<8} {sub_cat:<18} {lh:>15} days")

print(f"""
  Unmapped combinations default to 120 days.
  Example: get_liquidity_horizon("CR", "unknown") = {get_liquidity_horizon("CR", "unknown")} days
""")


# =============================================================================
# Example 2: Expected Shortfall Calculation
# =============================================================================

print("=" * 70)
print("EXAMPLE 2: Liquidity-Adjusted Expected Shortfall")
print("=" * 70)

# Create risk factors with 10-day ES values
risk_factors = [
    ESRiskFactor("IR", "major",       es_10day=2_000_000),
    ESRiskFactor("IR", "other",       es_10day=500_000),
    ESRiskFactor("CR", "IG_sovereign", es_10day=300_000),
    ESRiskFactor("CR", "IG_corporate", es_10day=800_000),
    ESRiskFactor("EQ", "large_cap",   es_10day=1_200_000),
    ESRiskFactor("FX", "major",       es_10day=600_000),
]

es_result = calculate_liquidity_adjusted_es(risk_factors)

print(f"""
  Input: 6 modellable risk factors with 10-day ES values

  Formula (MAR31.12):
    ES = sqrt( sum_j [ ES_j(T=10) * sqrt((LH_j - LH_{{j-1}}) / 10) ]^2 )

  Calculation by liquidity bucket:
  {'Bucket':<10} {'ES_10day':>12} {'Scale':>8} {'Contribution':>14}
  {'-'*48}""")

for lh, info in sorted(es_result.get('es_by_bucket', {}).items()):
    print(f"  {lh:>3}d      ${info['es_10day_sum']:>10,.0f}   {info['scale_factor']:.3f}   "
          f"${info['contribution']:>12,.0f}")

print(f"""  {'-'*48}
  Liquidity-adjusted ES:  ${es_result['es_total']:>12,.0f}
""")


# =============================================================================
# Example 3: Stressed ES and NMRF
# =============================================================================

print("=" * 70)
print("EXAMPLE 3: Stressed ES and Non-Modellable Risk Factors")
print("=" * 70)

# Add stressed values and non-modellable factors
risk_factors_full = [
    # Modellable with stressed values
    ESRiskFactor("IR", "major",       es_10day=2_000_000, stressed_es_10day=3_500_000),
    ESRiskFactor("IR", "other",       es_10day=500_000,   stressed_es_10day=900_000),
    ESRiskFactor("CR", "IG_corporate", es_10day=800_000,  stressed_es_10day=1_600_000),
    ESRiskFactor("EQ", "large_cap",   es_10day=1_200_000, stressed_es_10day=2_400_000),
    # Non-modellable factors (is_modellable=False)
    ESRiskFactor("CR", "other",       es_10day=200_000,
                 is_modellable=False, stressed_es_10day=500_000),
    ESRiskFactor("COM", "other",      es_10day=100_000,
                 is_modellable=False, stressed_es_10day=300_000),
]

# Current ES (modellable only)
es_current = calculate_liquidity_adjusted_es(risk_factors_full)
print(f"  Current ES (modellable factors):  ${es_current['es_total']:>12,.0f}")

# Reduced set current ES (factors with stressed values)
reduced_factors = [rf for rf in risk_factors_full if rf.stressed_es_10day is not None and rf.is_modellable]
es_reduced_current = calculate_liquidity_adjusted_es(reduced_factors)['es_total']

# Stressed ES
ses_result = calculate_stressed_es(
    risk_factors_full,
    es_full_current=es_current['es_total'],
    es_reduced_current=es_reduced_current
)

print(f"""
  Stressed ES Calculation (MAR31.16-18):
    SES = ES_reduced_stressed * (ES_full / ES_reduced)

    ES full (current):       ${es_current['es_total']:>12,.0f}
    ES reduced (current):    ${es_reduced_current:>12,.0f}
    ES reduced (stressed):   ${ses_result['es_reduced_stressed']:>12,.0f}
    Ratio:                   {ses_result['ratio']:>12.3f}
    SES:                     ${ses_result['ses_total']:>12,.0f}
""")

# NMRF charge
nmrf_result = calculate_nmrf_charge(risk_factors_full)
print(f"  NMRF Charge (MAR31.24-31):")
print(f"    Non-modellable factors are aggregated with ZERO diversification.")
print(f"\n  {'Factor':<20} {'Charge_10d':>12} {'LH':>6} {'Scaled':>12}")
print(f"  {'-'*55}")
for f in nmrf_result['factors']:
    print(f"  {f['risk_class']+'/'+f['sub_category']:<20} ${f['charge_10day']:>10,.0f} "
          f"{f['liquidity_horizon']:>4}d ${f['scaled_charge']:>10,.0f}")
print(f"  {'-'*55}")
print(f"  NMRF Total:                                ${nmrf_result['nmrf_total']:>10,.0f}")


# =============================================================================
# Example 4: Internal DRC Model
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 4: Internal Default Risk Charge (DRC)")
print("=" * 70)

# Create DRC positions
drc_positions = [
    DRCPosition("bond_1", "Apple Inc",    10_000_000, 9_800_000, pd=0.001, lgd=0.40),
    DRCPosition("bond_2", "Microsoft",     8_000_000, 7_900_000, pd=0.001, lgd=0.40),
    DRCPosition("bond_3", "Ford Motor",    5_000_000, 4_700_000, pd=0.02,  lgd=0.45),
    DRCPosition("bond_4", "Tesla",         6_000_000, 5_500_000, pd=0.03,  lgd=0.50),
    DRCPosition("cds_1",  "Ford Motor",    3_000_000, 2_900_000, pd=0.02,  lgd=0.45, is_long=False),
    DRCPosition("bond_5", "Petrobras",     4_000_000, 3_600_000, pd=0.05,  lgd=0.55,
                systematic_factor=0.25),  # Higher correlation for EM
]

print(f"""
  DRC Model (MAR32):
    - Two-factor Gaussian copula (systematic + idiosyncratic)
    - 1-year horizon, 99.9% confidence
    - Long/short netting only within same obligor

  Portfolio:
  {'Position':<12} {'Obligor':<15} {'Notional':>12} {'PD':>8} {'LGD':>6} {'L/S':>6}
  {'-'*65}""")

for pos in drc_positions:
    direction = "Long" if pos.is_long else "Short"
    print(f"  {pos.position_id:<12} {pos.obligor:<15} ${pos.notional:>10,.0f} "
          f"{pos.pd:>7.2%} {pos.lgd:>5.0%} {direction:>6}")

# Run DRC simulation
config = FRTBIMAConfig(drc_num_simulations=50_000)
drc_result = calculate_ima_drc(drc_positions, config)

print(f"""
  Monte Carlo Simulation ({drc_result['num_simulations']:,} paths):
  {'-'*45}
    Obligors:                {drc_result['num_obligors']:>12}
    Mean loss:               ${drc_result['mean_loss']:>12,.0f}
    95th percentile:         ${drc_result['percentile_95']:>12,.0f}
    99th percentile:         ${drc_result['percentile_99']:>12,.0f}
    99.9th percentile (DRC): ${drc_result['drc_charge']:>12,.0f}
    Max loss:                ${drc_result['max_loss']:>12,.0f}

  Note: Ford Motor has offsetting long/short positions (bond_3 vs cds_1),
        which reduces net exposure upon default.
""")


# =============================================================================
# Example 5: Backtesting
# =============================================================================

print("=" * 70)
print("EXAMPLE 5: Backtesting Evaluation (MAR33)")
print("=" * 70)

print("""
  Basel Traffic Light Zones (250 trading days):

  Zone     Exceptions  Plus Factor  Action
  -------  ----------  -----------  ---------------
  Green    0-4         0.00         Model OK
  Yellow   5-9         0.40-0.85    Review model
  Red      10+         1.00         Model rejected
""")

# Test different exception scenarios
for exceptions in [2, 5, 8, 12]:
    bt = evaluate_backtesting(exceptions)
    print(f"  {exceptions} exceptions: Zone={bt['zone']:>6}, Plus factor={bt['plus_factor']:.2f}")


# =============================================================================
# Example 6: P&L Attribution Test
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 6: P&L Attribution Test (PLA)")
print("=" * 70)

desks = [
    DeskPLA("rates_desk",    spearman_correlation=0.92, kl_divergence=0.04),
    DeskPLA("credit_desk",   spearman_correlation=0.82, kl_divergence=0.08),
    DeskPLA("equity_desk",   spearman_correlation=0.75, kl_divergence=0.11),
    DeskPLA("fx_desk",       spearman_correlation=0.65, kl_divergence=0.14),
    DeskPLA("commodity_desk", spearman_correlation=0.55, kl_divergence=0.20),
]

pla_result = evaluate_pla(desks)

print(f"""
  PLA Thresholds (MAR33.37):
    Spearman correlation: >= 0.80 (green), >= 0.70 (amber), else red
    KL divergence:        <= 0.09 (green), <= 0.12 (amber), else red

  Results:
  {'Desk':<16} {'Spearman':>10} {'KL Div':>10} {'Zone':>8} {'IMA Eligible':>14}
  {'-'*62}""")

for d in pla_result['desks']:
    eligible = "Yes" if d['ima_eligible'] else "No -> SA"
    print(f"  {d['desk_id']:<16} {d['spearman_correlation']:>10.2f} {d['kl_divergence']:>10.3f} "
          f"{d['overall_zone']:>8} {eligible:>14}")

print(f"""
  Summary:
    IMA eligible desks: {pla_result['ima_eligible_desks']}
    SA fallback desks:  {pla_result['sa_fallback_desks']}
""")


# =============================================================================
# Example 7: Full FRTB-IMA Calculation
# =============================================================================

print("=" * 70)
print("EXAMPLE 7: Full FRTB-IMA Capital Calculation")
print("=" * 70)

# Complete risk factor set
risk_factors_complete = [
    ESRiskFactor("IR", "major",       es_10day=2_500_000, stressed_es_10day=4_000_000),
    ESRiskFactor("IR", "other",       es_10day=800_000,   stressed_es_10day=1_400_000),
    ESRiskFactor("CR", "IG_sovereign", es_10day=500_000,  stressed_es_10day=900_000),
    ESRiskFactor("CR", "IG_corporate", es_10day=1_000_000, stressed_es_10day=1_800_000),
    ESRiskFactor("CR", "HY",          es_10day=700_000,   stressed_es_10day=1_500_000),
    ESRiskFactor("EQ", "large_cap",   es_10day=1_500_000, stressed_es_10day=3_000_000),
    ESRiskFactor("FX", "major",       es_10day=600_000,   stressed_es_10day=1_000_000),
    ESRiskFactor("COM", "energy",     es_10day=400_000,   stressed_es_10day=900_000),
    # Non-modellable
    ESRiskFactor("CR", "other",       es_10day=250_000,
                 is_modellable=False, stressed_es_10day=600_000),
]

# DRC positions
drc_complete = [
    DRCPosition("p1", "Corp_A", 15_000_000, 14_500_000, pd=0.002, lgd=0.40),
    DRCPosition("p2", "Corp_B", 10_000_000,  9_500_000, pd=0.01,  lgd=0.45),
    DRCPosition("p3", "Corp_C",  8_000_000,  7_200_000, pd=0.04,  lgd=0.50),
    DRCPosition("p4", "Corp_D", 12_000_000, 11_000_000, pd=0.008, lgd=0.45),
    DRCPosition("p5", "Corp_B",  5_000_000,  4_800_000, pd=0.01,  lgd=0.45, is_long=False),
]

# PLA desks
pla_desks = [
    DeskPLA("rates",   spearman_correlation=0.90, kl_divergence=0.06),
    DeskPLA("credit",  spearman_correlation=0.85, kl_divergence=0.07),
    DeskPLA("equity",  spearman_correlation=0.78, kl_divergence=0.10),
]

config = FRTBIMAConfig(
    plus_factor=0.0,
    drc_num_simulations=50_000,
    backtesting_exceptions=2,
)

result = calculate_frtb_ima_capital(
    risk_factors_complete,
    drc_complete,
    config=config,
    desks=pla_desks,
)

print(f"""
  FRTB-IMA Capital Breakdown:
  {'='*50}

  Expected Shortfall (ES):
    Liquidity-adjusted ES:   ${result['es']['es_total']:>14,.0f}
    Modellable factors:      {result['es']['num_factors']:>14}

  Stressed ES (SES):
    SES:                     ${result['ses']['ses_total']:>14,.0f}

  IMCC Components:
    ES component:            ${result['imcc_detail']['es_component']:>14,.0f}
    SES component:           ${result['imcc_detail']['ses_component']:>14,.0f}
    NMRF add-on:             ${result['imcc_detail']['nmrf']:>14,.0f}
    Multiplier (m_c):        {result['imcc_detail']['multiplication_factor_mc']:>14.2f}
    IMCC Total:              ${result['imcc']:>14,.0f}

  Internal DRC:
    DRC Charge (99.9%):      ${result['drc_charge']:>14,.0f}

  Backtesting:
    Zone:                    {result['backtesting']['zone']:>14}
    Plus factor:             {result['backtesting']['plus_factor']:>14.2f}

  PLA:
    IMA eligible desks:      {result['pla']['ima_eligible_desks']:>14}
    SA fallback desks:       {result['pla']['sa_fallback_desks']:>14}

  {'='*50}
  TOTAL IMA CAPITAL:         ${result['total_capital']:>14,.0f}
  TOTAL IMA RWA:             ${result['total_rwa']:>14,.0f}
  {'='*50}
""")


# =============================================================================
# Example 8: Quick FRTB-IMA
# =============================================================================

print("=" * 70)
print("EXAMPLE 8: Quick FRTB-IMA (Simplified Inputs)")
print("=" * 70)

# Minimal inputs for quick estimate
quick_result = quick_frtb_ima(
    es_10day_total=5_000_000,
    stressed_es_10day_total=9_000_000,
    drc_positions=[
        {"obligor": "Corp_A", "notional": 20_000_000, "rating": "A", "lgd": 0.40},
        {"obligor": "Corp_B", "notional": 15_000_000, "rating": "BBB", "lgd": 0.45},
        {"obligor": "Corp_C", "notional": 10_000_000, "rating": "BB", "lgd": 0.50},
    ],
    plus_factor=0.0,
)

print(f"""
  Quick estimate from aggregate ES values:

    ES (10-day):             $5,000,000
    Stressed ES (10-day):    $9,000,000
    DRC positions:           3 obligors

  Result:
    IMCC:                    ${quick_result['imcc']:>14,.0f}
    DRC:                     ${quick_result['drc_charge']:>14,.0f}
    Total Capital:           ${quick_result['total_capital']:>14,.0f}
    Total RWA:               ${quick_result['total_rwa']:>14,.0f}
""")


# =============================================================================
# Example 9: Impact of Plus Factor
# =============================================================================

print("=" * 70)
print("EXAMPLE 9: Impact of Backtesting Plus Factor")
print("=" * 70)

print(f"""
  The plus factor from backtesting increases the multiplication factor:
    m_c = 1.5 * (1 + plus_factor)

  Impact on capital (using Example 7 portfolio):

  {'Exceptions':<12} {'Zone':<8} {'Plus Factor':>12} {'m_c':>8} {'IMCC':>14} {'Total':>14}
  {'-'*75}""")

for exceptions in [0, 3, 5, 7, 10]:
    bt = evaluate_backtesting(exceptions)
    test_config = FRTBIMAConfig(
        plus_factor=bt['plus_factor'],
        drc_num_simulations=30_000,
        backtesting_exceptions=exceptions,
    )
    test_result = calculate_frtb_ima_capital(
        risk_factors_complete, drc_complete, config=test_config,
    )
    m_c = 1.5 * (1 + bt['plus_factor'])
    print(f"  {exceptions:<12} {bt['zone']:<8} {bt['plus_factor']:>12.2f} {m_c:>8.2f} "
          f"${test_result['imcc']:>12,.0f} ${test_result['total_capital']:>12,.0f}")

print("""
  Note: More backtesting exceptions = higher plus factor = higher capital
""")


# =============================================================================
# Summary
# =============================================================================

print("=" * 70)
print("SUMMARY: FRTB-IMA Functions")
print("=" * 70)

print("""
  Dataclasses:
    ESRiskFactor(risk_class, sub_category, es_10day, ...)
    DRCPosition(position_id, obligor, notional, market_value, pd, lgd, ...)
    DeskPLA(desk_id, spearman_correlation, kl_divergence)
    FRTBIMAConfig(multiplication_factor, plus_factor, ...)

  Expected Shortfall:
    get_liquidity_horizon(risk_class, sub_category)
    calculate_liquidity_adjusted_es(risk_factors)
    calculate_stressed_es(risk_factors, es_full, es_reduced)
    calculate_nmrf_charge(risk_factors)

  Internal DRC:
    simulate_drc_portfolio(positions, num_simulations)
    calculate_ima_drc(positions, config)

  Backtesting & PLA:
    evaluate_backtesting(num_exceptions, num_observations)
    evaluate_pla(desks)

  Main Calculations:
    calculate_imcc(risk_factors, es, ses, ...)
    calculate_frtb_ima_capital(risk_factors, drc_positions, config, ...)

  Convenience:
    quick_frtb_ima(es_10day_total, stressed_es_10day_total, drc_positions)
    compare_ima_vs_sa(risk_factors, drc_ima, delta_sa, drc_sa, config)

  Key Formulas:
    IMA Capital = IMCC + DRC
    IMCC = max(ES, m_c * ES_avg) + max(SES, m_c * SES_avg) + NMRF
    m_c = 1.5 * (1 + plus_factor)
""")

print("=" * 70)
print("END OF EXAMPLES")
print("=" * 70)
