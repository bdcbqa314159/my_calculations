#!/usr/bin/env python3
"""
IRC CSV Workflow — Complete Input/Output Guide

This example shows the full workflow from CSV input to IRC output,
with clear documentation of required columns, optional columns,
and output format.

Usage:
    cd /Users/bernardocohen/repos/work/rwa_calc
    ./venv/bin/python examples/irc_csv_workflow.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from irc import quick_irc, calculate_irc_by_issuer, irc_to_dataframe, IRCPosition, IRCConfig


# =============================================================================
# SECTION 1: CSV INPUT FORMAT
# =============================================================================

print("=" * 80)
print("IRC CSV WORKFLOW — INPUT/OUTPUT GUIDE")
print("=" * 80)

print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CSV INPUT FORMAT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  REQUIRED COLUMNS (must have these):                                         │
│  ─────────────────────────────────────                                       │
│    issuer        : str   - Obligor name (same name = same migration)         │
│    rating        : str   - Credit rating: AAA, AA, A, BBB, BB, B, CCC        │
│    tenor_years   : float - Remaining maturity in years                       │
│    notional      : float - Position size in dollars                          │
│                                                                              │
│  OPTIONAL COLUMNS (defaults applied if missing):                             │
│  ───────────────────────────────────────────────                             │
│    seniority     : str   - senior_secured (25% LGD)                          │
│                           senior_unsecured (45% LGD) [default]               │
│                           subordinated (75% LGD)                             │
│    lgd           : float - Custom LGD (0.0-1.0), OVERRIDES seniority         │
│    sector        : str   - Sector name for correlation (default: corporate) │
│    region        : str   - Region for matrix selection (US, EU, EM, etc.)   │
│    liquidity_horizon_months : int - 3, 6, or 12 (default: 3)                │
│    is_long       : bool  - True for long, False for short (default: True)   │
│    coupon_rate   : float - Annual coupon rate (default: 0.05)               │
│    market_value  : float - Current market value (default: notional)         │
│    position_id   : str   - Unique identifier (default: auto-generated)      │
│                                                                              │
│  LGD PRIORITY: lgd > seniority > default (0.45)                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
""")


# =============================================================================
# SECTION 2: SAMPLE CSV FILES
# =============================================================================

print("-" * 80)
print("SAMPLE CSV FILES")
print("-" * 80)

# Minimal CSV (required columns only)
minimal_csv = """issuer,rating,tenor_years,notional
Apple,AA,5.0,20000000
Microsoft,AAA,7.0,15000000
Ford,BB,3.0,10000000
Tesla,BBB,4.0,12000000
Netflix,BB,5.0,8000000
AMC,CCC,2.0,5000000"""

print("\n1. MINIMAL CSV (required columns only):")
print("-" * 40)
print(minimal_csv)

# Full CSV (all columns)
full_csv = """issuer,rating,tenor_years,notional,seniority,sector,region,liquidity_horizon_months,is_long,coupon_rate,market_value,position_id
Apple,AA,5.0,20000000,senior_unsecured,tech,US,3,True,0.04,20500000,AAPL_5Y
Microsoft,AAA,7.0,15000000,senior_unsecured,tech,US,3,True,0.035,15200000,MSFT_7Y
Deutsche Bank,A,5.0,12000000,senior_unsecured,financial,EU,3,True,0.045,11800000,DB_5Y
BNP Paribas,A,4.0,10000000,subordinated,financial,EU,6,True,0.055,9500000,BNP_4Y_SUB
Petrobras,BB,5.0,8000000,senior_secured,energy,EM,3,True,0.065,7600000,PETRO_5Y
Pemex,B,4.0,6000000,senior_unsecured,energy,EM,3,True,0.085,5400000,PEMEX_4Y
Ford CDS,BB,5.0,5000000,senior_unsecured,auto,US,3,False,0.0,5000000,FORD_CDS"""

print("\n2. FULL CSV (all columns):")
print("-" * 40)
print(full_csv)


# =============================================================================
# SECTION 3: LOADING AND PROCESSING
# =============================================================================

print("\n" + "-" * 80)
print("LOADING AND PROCESSING")
print("-" * 80)

# Save sample CSV to temp file and load it
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    f.write(full_csv)
    csv_path = f.name

# Load CSV
df = pd.read_csv(csv_path)

print("\nLoaded DataFrame:")
print(df.to_string(index=False))

print(f"\nShape: {df.shape[0]} rows × {df.shape[1]} columns")


# =============================================================================
# SECTION 4: RUNNING IRC CALCULATION
# =============================================================================

print("\n" + "-" * 80)
print("IRC CALCULATION")
print("-" * 80)

# Convert DataFrame to list of dicts (what quick_irc expects)
positions = df.to_dict(orient="records")

print("\nMethod 1: Single matrix for all positions")
print("-" * 40)

result = quick_irc(positions, num_simulations=50_000, transition_matrix="global")

print(f"""
INPUT:
  Positions:     {len(positions)}
  Total notional: ${sum(p['notional'] for p in positions):,.0f}
  Issuers:       {len(set(p['issuer'] for p in positions))}

OUTPUT:
  IRC (99.9%):           ${result['irc']:>14,.0f}
  IRC RWA:               ${result['rwa']:>14,.0f}
  Capital ratio:         {result['capital_ratio']*100:>13.2f}%

  Loss Distribution:
    Mean loss:           ${result['mean_loss']:>14,.0f}
    Median loss:         ${result['median_loss']:>14,.0f}
    95th percentile:     ${result['percentile_95']:>14,.0f}
    99th percentile:     ${result['percentile_99']:>14,.0f}
    99.9th percentile:   ${result['percentile_999']:>14,.0f}
    Expected Shortfall:  ${result['expected_shortfall_999']:>14,.0f}
    Max loss:            ${result['max_loss']:>14,.0f}
""")


print("\nMethod 2: Multi-matrix by region/sector")
print("-" * 40)

result_multi = quick_irc(
    positions,
    num_simulations=50_000,
    matrix_by_region={"US": "global", "EU": "europe", "EM": "emerging_markets"},
    matrix_by_sector={"financial": "financials"},
)

print(f"""
  IRC (multi-matrix):    ${result_multi['irc']:>14,.0f}
  Matrices used:         {result_multi.get('matrices_used', ['global'])}
""")


# =============================================================================
# SECTION 5: IRC BY ISSUER (DETAILED BREAKDOWN)
# =============================================================================

print("-" * 80)
print("IRC BY ISSUER (DETAILED BREAKDOWN)")
print("-" * 80)

# Need IRCPosition objects for issuer breakdown
irc_positions = [
    IRCPosition(
        position_id=p.get("position_id", f"pos_{i}"),
        issuer=p["issuer"],
        notional=p["notional"],
        market_value=p.get("market_value", p["notional"]),
        rating=p["rating"],
        tenor_years=p["tenor_years"],
        seniority=p.get("seniority", "senior_unsecured"),
        sector=p.get("sector", "corporate"),
        liquidity_horizon_months=p.get("liquidity_horizon_months", 3),
        is_long=p.get("is_long", True),
        coupon_rate=p.get("coupon_rate", 0.05),
    )
    for i, p in enumerate(positions)
]

config = IRCConfig(num_simulations=50_000)
issuer_result = calculate_irc_by_issuer(irc_positions, config)

print("\nIssuer Contributions:")
print(f"{'Issuer':<15} {'Rating':>6} {'Notional':>14} {'Standalone':>12} {'Marginal':>12} {'%':>7}")
print("-" * 72)
for c in issuer_result["issuer_contributions"]:
    print(f"{c['issuer']:<15} {c['rating']:>6} ${c['notional']:>12,.0f} "
          f"${c['standalone_irc']:>10,.0f} ${c['marginal_irc']:>10,.0f} {c['pct_of_total']:>6.1f}%")

print(f"""
Summary:
  Sum of standalone:     ${sum(c['standalone_irc'] for c in issuer_result['issuer_contributions']):>14,.0f}
  Diversification:       ${issuer_result['diversification_benefit']:>14,.0f}
  Portfolio IRC:         ${issuer_result['irc']:>14,.0f}
""")


# =============================================================================
# SECTION 6: OUTPUT TO CSV
# =============================================================================

print("-" * 80)
print("OUTPUT TO CSV")
print("-" * 80)

# Convert result to DataFrame
df_output = irc_to_dataframe(issuer_result)

print("\nOutput DataFrame:")
print(df_output.to_string(index=False))

# Save to CSV
output_path = "/tmp/irc_output.csv"
df_output.to_csv(output_path, index=False)
print(f"\nSaved to: {output_path}")

print("\nCSV Output Contents:")
print("-" * 40)
with open(output_path) as f:
    print(f.read())


# =============================================================================
# SECTION 7: COMPLETE OUTPUT DICTIONARY
# =============================================================================

print("-" * 80)
print("COMPLETE OUTPUT DICTIONARY")
print("-" * 80)

print("""
The quick_irc() function returns a dictionary with these fields:

{
  # Core results
  "approach": "IRC (Monte Carlo)",     # or "IRC (Multi-Matrix Monte Carlo)"
  "irc": 5234567.0,                    # IRC capital charge (99.9th percentile)
  "rwa": 65432087.5,                   # RWA = IRC × 12.5
  "capital_ratio": 0.0687,             # IRC / total notional

  # Loss distribution statistics
  "mean_loss": 234567.0,               # Average loss across simulations
  "median_loss": 0.0,                  # 50th percentile (often 0)
  "percentile_95": 1234567.0,          # 95th percentile
  "percentile_99": 3456789.0,          # 99th percentile
  "percentile_999": 5234567.0,         # 99.9th percentile (= IRC)
  "expected_shortfall_999": 7654321.0, # Average loss beyond 99.9%
  "max_loss": 12345678.0,              # Maximum simulated loss
  "min_loss": 0.0,                     # Minimum simulated loss

  # Portfolio info
  "num_simulations": 50000,
  "num_positions": 7,
  "num_issuers": 7,
  "total_notional": 76000000,

  # Config used
  "config": {
    "confidence_level": 0.999,
    "horizon_years": 1.0,
    "systematic_correlation": 0.5
  },

  # Multi-matrix only
  "matrices_used": ["global", "europe", "financials"]  # if multi-matrix
}
""")


# =============================================================================
# SECTION 8: QUICK REFERENCE
# =============================================================================

print("-" * 80)
print("QUICK REFERENCE")
print("-" * 80)

print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                            QUICK REFERENCE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LOAD CSV AND RUN IRC:                                                       │
│  ─────────────────────                                                       │
│    import pandas as pd                                                       │
│    from irc import quick_irc, irc_to_dataframe                              │
│                                                                              │
│    df = pd.read_csv("portfolio.csv")                                        │
│    result = quick_irc(df.to_dict(orient="records"))                         │
│    print(f"IRC: ${result['irc']:,.0f}")                                     │
│                                                                              │
│  WITH MULTI-MATRIX:                                                          │
│  ──────────────────                                                          │
│    result = quick_irc(                                                       │
│        df.to_dict(orient="records"),                                        │
│        matrix_by_region={"US": "global", "EU": "europe", "EM": "em"},       │
│        matrix_by_sector={"financial": "financials"},                        │
│    )                                                                         │
│                                                                              │
│  EXPORT RESULTS:                                                             │
│  ───────────────                                                             │
│    from irc import calculate_irc_by_issuer, irc_to_csv                      │
│    issuer_result = calculate_irc_by_issuer(positions, config)               │
│    irc_to_csv(issuer_result, "irc_output.csv")                              │
│                                                                              │
│  AVAILABLE MATRICES:                                                         │
│  ───────────────────                                                         │
│    global, europe, em, financials, sovereign, recession, benign             │
│                                                                              │
│  LGD OPTIONS (priority: lgd > seniority > default):                          │
│  ──────────────────────────────────────────────────                          │
│    lgd column:       0.0-1.0 (custom, highest priority)                     │
│    seniority column: senior_secured=25%, senior_unsecured=45%,              │
│                      subordinated=75%                                        │
│    default:          45% (if neither provided)                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
""")

# Cleanup
os.unlink(csv_path)
os.unlink(output_path)

print("\n" + "=" * 80)
print("END OF GUIDE")
print("=" * 80)
