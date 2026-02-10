#!/usr/bin/env python3
"""
IRC — Full Incremental Risk Charge Calculation

The IRC captures default risk AND rating migration risk for trading book
credit positions over a 1-year horizon at 99.9% confidence.

Key regulatory requirements (Basel 2.5 Para 718(xcii)):
  - 1-year capital horizon
  - 99.9% confidence level (VaR-like tail measure)
  - Captures default AND rating migration (spread widening)
  - Liquidity horizons of 3 months minimum
  - Constant level of risk assumption with rebalancing

IRC Inputs:
  - Issuer: name/ID of the obligor
  - Rating: current external rating (AAA, AA, A, BBB, BB, B, CCC)
  - Tenor: remaining maturity in years
  - Notional: position size
  - Seniority: senior_secured, senior_unsecured, subordinated
  - Liquidity horizon: rebalancing frequency (3, 6, 12 months)
  - Direction: long or short

Monte Carlo Process:
  1. For each simulation (100,000+):
     a. Draw systematic factor X ~ N(0,1)
     b. For each issuer: Z_i = rho × X + sqrt(1-rho²) × epsilon_i
     c. Convert Z_i to uniform via Phi(Z_i)
     d. Use uniform + transition matrix → new rating
     e. If default: loss = LGD × notional
        If migration: loss = spread_change × PV01
  2. IRC = 99.9th percentile of loss distribution

Usage:
    cd /Users/bernardocohen/repos/work/rwa_calc
    ./venv/bin/python examples/irc_full_example.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irc import (
    IRCPosition, IRCConfig,
    calculate_irc, calculate_irc_by_issuer, quick_irc,
    TRANSITION_MATRIX, CREDIT_SPREADS, RATING_CATEGORIES,
)


print("=" * 72)
print("IRC (Incremental Risk Charge) — Monte Carlo Simulation")
print("=" * 72)


# =====================================================================
# 1. Define the portfolio
# =====================================================================
#
# Each position needs:
#   - issuer:        obligor name (same issuer = correlated migration)
#   - rating:        current rating (AAA to CCC)
#   - tenor_years:   remaining maturity
#   - notional:      position size
#   - seniority:     affects LGD (senior_secured=25%, unsecured=45%, sub=75%)
#   - liquidity_horizon_months:  rebalancing frequency (3, 6, 12)
#   - is_long:       True = long credit (lose on downgrade/default)

positions = [
    # --- Financial sector ---
    IRCPosition(
        position_id="FIN_1",
        issuer="Bank Alpha",
        notional=20_000_000,
        market_value=20_500_000,
        rating="A",
        tenor_years=5.0,
        seniority="senior_unsecured",
        sector="financial",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.04,
    ),
    IRCPosition(
        position_id="FIN_2",
        issuer="Bank Alpha",
        notional=10_000_000,
        market_value=9_800_000,
        rating="A",
        tenor_years=3.0,
        seniority="subordinated",
        sector="financial",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.055,
    ),
    IRCPosition(
        position_id="FIN_3",
        issuer="Insurance Beta",
        notional=15_000_000,
        market_value=15_200_000,
        rating="BBB",
        tenor_years=7.0,
        seniority="senior_unsecured",
        sector="financial",
        liquidity_horizon_months=6,
        is_long=True,
        coupon_rate=0.045,
    ),

    # --- Energy sector ---
    IRCPosition(
        position_id="ENGY_1",
        issuer="Oil Corp",
        notional=12_000_000,
        market_value=11_500_000,
        rating="BB",
        tenor_years=4.0,
        seniority="senior_unsecured",
        sector="energy",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.065,
    ),
    IRCPosition(
        position_id="ENGY_2",
        issuer="Gas Ltd",
        notional=8_000_000,
        market_value=7_600_000,
        rating="B",
        tenor_years=3.0,
        seniority="senior_unsecured",
        sector="energy",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.085,
    ),

    # --- Short position (hedge) ---
    IRCPosition(
        position_id="HEDGE_1",
        issuer="Oil Corp",
        notional=5_000_000,
        market_value=4_900_000,
        rating="BB",
        tenor_years=5.0,
        seniority="senior_unsecured",
        sector="energy",
        liquidity_horizon_months=3,
        is_long=False,  # short via CDS
        coupon_rate=0.0,
    ),

    # --- Industrial ---
    IRCPosition(
        position_id="IND_1",
        issuer="Mfg Corp",
        notional=18_000_000,
        market_value=18_200_000,
        rating="BBB",
        tenor_years=6.0,
        seniority="senior_unsecured",
        sector="industrial",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.05,
    ),

    # --- High-yield ---
    IRCPosition(
        position_id="HY_1",
        issuer="Distressed Inc",
        notional=5_000_000,
        market_value=4_200_000,
        rating="CCC",
        tenor_years=2.0,
        seniority="senior_unsecured",
        sector="retail",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.12,
    ),
]

print(f"\n  Portfolio:")
print(f"    Positions:   {len(positions)}")
print(f"    Issuers:     {len(set(p.issuer for p in positions))}")
print(f"    Notional:    ${sum(abs(p.notional) for p in positions):,.0f}")

print("\n  Position breakdown:")
print(f"    {'ID':<10} {'Issuer':<18} {'Rating':>6} {'Tenor':>5} {'Notional':>14} {'Long':>5}")
print("    " + "-" * 65)
for p in positions:
    print(f"    {p.position_id:<10} {p.issuer:<18} {p.rating:>6} {p.tenor_years:>5.1f} "
          f"${p.notional:>12,.0f} {'Y' if p.is_long else 'N':>5}")


# =====================================================================
# 2. Configure and run simulation
# =====================================================================

config = IRCConfig(
    num_simulations=100_000,
    confidence_level=0.999,
    horizon_years=1.0,
    systematic_correlation=0.50,
    sector_correlation=0.25,
    seed=42,
)

print(f"\n" + "-" * 72)
print("Running Monte Carlo Simulation...")
print("-" * 72)
print(f"  Simulations:     {config.num_simulations:,}")
print(f"  Confidence:      {config.confidence_level*100:.1f}%")
print(f"  Horizon:         {config.horizon_years} year")
print(f"  Sys. correlation:{config.systematic_correlation:.0%}")

result = calculate_irc(positions, config)


# =====================================================================
# 3. Results
# =====================================================================

print(f"\n" + "-" * 72)
print("IRC Results")
print("-" * 72)

print(f"\n  Loss Distribution:")
print(f"    Mean:                ${result['mean_loss']:>14,.0f}")
print(f"    Median:              ${result['median_loss']:>14,.0f}")
print(f"    95th percentile:     ${result['percentile_95']:>14,.0f}")
print(f"    99th percentile:     ${result['percentile_99']:>14,.0f}")
print(f"    99.9th percentile:   ${result['percentile_999']:>14,.0f}")
print(f"    Expected Shortfall:  ${result['expected_shortfall_999']:>14,.0f}")
print(f"    Maximum:             ${result['max_loss']:>14,.0f}")

print(f"\n  Capital Requirement:")
print(f"    IRC (99.9%):         ${result['irc']:>14,.0f}")
print(f"    IRC RWA:             ${result['rwa']:>14,.0f}")
print(f"    Capital ratio:       {result['capital_ratio']*100:>13.2f}%")


# =====================================================================
# 4. IRC by Issuer (risk contribution)
# =====================================================================

print(f"\n" + "-" * 72)
print("IRC by Issuer (Risk Contribution)")
print("-" * 72)

issuer_result = calculate_irc_by_issuer(positions, config)

print(f"\n  {'Issuer':<18} {'Rating':>6} {'Notional':>14} {'Standalone':>12} "
      f"{'Marginal':>12} {'%':>6}")
print("  " + "-" * 74)
for c in issuer_result["issuer_contributions"]:
    print(f"  {c['issuer']:<18} {c['rating']:>6} ${c['notional']:>12,.0f} "
          f"${c['standalone_irc']:>10,.0f} ${c['marginal_irc']:>10,.0f} "
          f"{c['pct_of_total']:>5.1f}%")

print(f"\n  Sum of standalone:     ${sum(c['standalone_irc'] for c in issuer_result['issuer_contributions']):>14,.0f}")
print(f"  Diversification:       ${issuer_result['diversification_benefit']:>14,.0f}")
print(f"  Portfolio IRC:         ${issuer_result['irc']:>14,.0f}")


# =====================================================================
# 5. Scenario Analysis: Correlation sensitivity
# =====================================================================

print(f"\n" + "-" * 72)
print("Correlation Sensitivity Analysis")
print("-" * 72)

print(f"\n  {'Correlation':>12} {'IRC':>14} {'vs Base':>10}")
print("  " + "-" * 40)
base_irc = result["irc"]

for rho in [0.20, 0.35, 0.50, 0.65, 0.80]:
    test_config = IRCConfig(
        num_simulations=50_000,  # fewer for speed
        systematic_correlation=rho,
        seed=42,
    )
    test_result = calculate_irc(positions, test_config)
    change = (test_result["irc"] / base_irc - 1) * 100
    marker = "←base" if rho == 0.50 else ""
    print(f"  {rho:>12.0%} ${test_result['irc']:>12,.0f} {change:>+9.1f}% {marker}")


# =====================================================================
# 6. Rating Migration Probabilities
# =====================================================================

print(f"\n" + "-" * 72)
print("Rating Transition Matrix (1-year)")
print("-" * 72)

print(f"\n  {'From':<6} → {'Upgrade':>8} {'Stable':>8} {'Down':>8} {'Default':>8}")
print("  " + "-" * 45)
for rating in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
    probs = TRANSITION_MATRIX[rating]
    idx = RATING_CATEGORIES.index(rating)
    upgrade = sum(probs[r] for r in RATING_CATEGORIES[:idx])
    stable = probs[rating]
    downgrade = sum(probs[r] for r in RATING_CATEGORIES[idx+1:-1])
    default = probs["D"]
    print(f"  {rating:<6}   {upgrade*100:>7.2f}% {stable*100:>7.2f}% "
          f"{downgrade*100:>7.2f}% {default*100:>7.3f}%")


# =====================================================================
# 7. Credit Spread Term Structure
# =====================================================================

print(f"\n" + "-" * 72)
print("Credit Spread Term Structure (bps)")
print("-" * 72)

print(f"\n  {'Rating':<6} {'1Y':>6} {'3Y':>6} {'5Y':>6} {'7Y':>6} {'10Y':>6}")
print("  " + "-" * 40)
for rating in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
    spreads = CREDIT_SPREADS[rating]
    print(f"  {rating:<6} {spreads[1]:>6} {spreads[3]:>6} {spreads[5]:>6} "
          f"{spreads[7]:>6} {spreads[10]:>6}")


# =====================================================================
# 8. Summary
# =====================================================================

print(f"\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)
print(f"\n  Portfolio notional:    ${result['total_notional']:>14,.0f}")
print(f"  Number of issuers:     {result['num_issuers']:>14}")
print(f"  IRC charge:            ${result['irc']:>14,.0f}")
print(f"  IRC / notional:        {result['capital_ratio']*100:>13.2f}%")
print(f"  IRC RWA:               ${result['rwa']:>14,.0f}")
print(f"\n  Top risk contributors:")
for i, c in enumerate(issuer_result["issuer_contributions"][:3]):
    print(f"    {i+1}. {c['issuer']} ({c['rating']}): ${c['marginal_irc']:,.0f} "
          f"({c['pct_of_total']:.1f}%)")
