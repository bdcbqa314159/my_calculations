#!/usr/bin/env python3
"""
IRC Simple Usage — Issuer / Rating / Tenor / Notional

This example shows the simplest way to calculate IRC when you have
a list of positions defined by:
  - Issuer name
  - Rating (AAA, AA, A, BBB, BB, B, CCC)
  - Tenor (remaining maturity in years)
  - Notional (position size)

Usage:
    cd /Users/bernardocohen/repos/work/rwa_calc
    ./venv/bin/python examples/irc_simple_usage.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irc import quick_irc, IRCPosition, IRCConfig, calculate_irc, calculate_irc_by_issuer


# =====================================================================
# Method 1: Using quick_irc() with simple dicts (easiest)
# =====================================================================

print("=" * 60)
print("Method 1: quick_irc() with simple dicts")
print("=" * 60)

# Define positions as simple dicts with just the essentials
positions_simple = [
    {"issuer": "Apple",     "rating": "AA",  "tenor_years": 5.0, "notional": 20_000_000},
    {"issuer": "Microsoft", "rating": "AAA", "tenor_years": 7.0, "notional": 15_000_000},
    {"issuer": "Ford",      "rating": "BB",  "tenor_years": 3.0, "notional": 10_000_000},
    {"issuer": "Tesla",     "rating": "BBB", "tenor_years": 4.0, "notional": 12_000_000},
    {"issuer": "Netflix",   "rating": "BB",  "tenor_years": 5.0, "notional": 8_000_000},
    {"issuer": "AMC",       "rating": "CCC", "tenor_years": 2.0, "notional": 5_000_000},
]

result = quick_irc(positions_simple, num_simulations=50_000, correlation=0.50)

print(f"\nPortfolio: {len(positions_simple)} positions")
print(f"Total notional: ${sum(p['notional'] for p in positions_simple):,.0f}")
print(f"\nIRC (99.9%):    ${result['irc']:,.0f}")
print(f"IRC RWA:        ${result['rwa']:,.0f}")
print(f"Capital ratio:  {result['capital_ratio']*100:.2f}%")


# =====================================================================
# Method 2: Using quick_irc() with optional fields
# =====================================================================

print("\n" + "=" * 60)
print("Method 2: quick_irc() with optional fields")
print("=" * 60)

# You can add optional fields for more precision
positions_detailed = [
    {
        "issuer": "Apple",
        "rating": "AA",
        "tenor_years": 5.0,
        "notional": 20_000_000,
        "seniority": "senior_unsecured",      # optional: senior_secured, senior_unsecured, subordinated
        "sector": "tech",                      # optional: for sector correlation
        "liquidity_horizon_months": 3,         # optional: 3, 6, or 12
        "is_long": True,                       # optional: True=long, False=short
        "coupon_rate": 0.04,                   # optional: for duration calculation
    },
    {
        "issuer": "Ford",
        "rating": "BB",
        "tenor_years": 3.0,
        "notional": 10_000_000,
        "seniority": "senior_secured",         # lower LGD (25% vs 45%)
    },
    {
        "issuer": "Hedge Fund Short",
        "rating": "BBB",
        "tenor_years": 5.0,
        "notional": 8_000_000,
        "is_long": False,                      # SHORT position (via CDS)
    },
]

result2 = quick_irc(positions_detailed, num_simulations=50_000)

print(f"\nIRC (99.9%):    ${result2['irc']:,.0f}")


# =====================================================================
# Method 3: Using IRCPosition objects (full control)
# =====================================================================

print("\n" + "=" * 60)
print("Method 3: IRCPosition objects (full control)")
print("=" * 60)

positions_full = [
    IRCPosition(
        position_id="AAPL_5Y",
        issuer="Apple",
        notional=20_000_000,
        market_value=20_500_000,
        rating="AA",
        tenor_years=5.0,
        seniority="senior_unsecured",
        sector="tech",
        liquidity_horizon_months=3,
        is_long=True,
        coupon_rate=0.04,
    ),
    IRCPosition(
        position_id="MSFT_7Y",
        issuer="Microsoft",
        notional=15_000_000,
        market_value=15_200_000,
        rating="AAA",
        tenor_years=7.0,
    ),
    IRCPosition(
        position_id="F_3Y",
        issuer="Ford",
        notional=10_000_000,
        market_value=9_500_000,
        rating="BB",
        tenor_years=3.0,
        seniority="senior_secured",
    ),
]

config = IRCConfig(
    num_simulations=100_000,
    systematic_correlation=0.50,
)

result3 = calculate_irc(positions_full, config)

print(f"\nIRC (99.9%):    ${result3['irc']:,.0f}")
print(f"Mean loss:      ${result3['mean_loss']:,.0f}")
print(f"99% VaR:        ${result3['percentile_99']:,.0f}")


# =====================================================================
# Method 4: From a DataFrame or CSV-like structure
# =====================================================================

print("\n" + "=" * 60)
print("Method 4: From tabular data (DataFrame-like)")
print("=" * 60)

# Simulate data that might come from a CSV or DataFrame
portfolio_data = [
    # issuer,       rating, tenor, notional
    ("Goldman",     "A",    5.0,   25_000_000),
    ("JPMorgan",    "A",    7.0,   30_000_000),
    ("Citi",        "BBB",  4.0,   20_000_000),
    ("BofA",        "A",    6.0,   22_000_000),
    ("Wells Fargo", "BBB",  3.0,   18_000_000),
    ("Morgan Stanley", "A", 5.0,   15_000_000),
]

# Convert to the format quick_irc expects
positions_from_data = [
    {"issuer": issuer, "rating": rating, "tenor_years": tenor, "notional": notional}
    for issuer, rating, tenor, notional in portfolio_data
]

result4 = quick_irc(positions_from_data, num_simulations=50_000)

print(f"\nPortfolio: {len(positions_from_data)} bank bonds")
print(f"Total notional: ${sum(p['notional'] for p in positions_from_data):,.0f}")
print(f"\nIRC (99.9%):    ${result4['irc']:,.0f}")
print(f"IRC RWA:        ${result4['rwa']:,.0f}")


# =====================================================================
# Bonus: Get IRC breakdown by issuer
# =====================================================================

print("\n" + "=" * 60)
print("Bonus: IRC breakdown by issuer")
print("=" * 60)

# Convert simple dicts to IRCPosition objects for issuer analysis
irc_positions = [
    IRCPosition(
        position_id=f"pos_{i}",
        issuer=p["issuer"],
        notional=p["notional"],
        market_value=p["notional"],
        rating=p["rating"],
        tenor_years=p["tenor_years"],
    )
    for i, p in enumerate(positions_simple)
]

issuer_result = calculate_irc_by_issuer(irc_positions, IRCConfig(num_simulations=50_000))

print(f"\n{'Issuer':<12} {'Rating':>6} {'Notional':>14} {'Marginal IRC':>14} {'%':>7}")
print("-" * 58)
for c in issuer_result["issuer_contributions"]:
    print(f"{c['issuer']:<12} {c['rating']:>6} ${c['notional']:>12,.0f} "
          f"${c['marginal_irc']:>12,.0f} {c['pct_of_total']:>6.1f}%")

print(f"\nDiversification benefit: ${issuer_result['diversification_benefit']:,.0f}")
print(f"Portfolio IRC:           ${issuer_result['irc']:,.0f}")


# =====================================================================
# Method 5: From a Pandas DataFrame
# =====================================================================

print("\n" + "=" * 60)
print("Method 5: From a Pandas DataFrame")
print("=" * 60)

try:
    import pandas as pd

    # Create a DataFrame (could come from pd.read_csv(), pd.read_excel(), etc.)
    df = pd.DataFrame({
        "issuer": ["Apple", "Microsoft", "Ford", "Tesla", "Netflix", "AMC"],
        "rating": ["AA", "AAA", "BB", "BBB", "BB", "CCC"],
        "tenor_years": [5.0, 7.0, 3.0, 4.0, 5.0, 2.0],
        "notional": [20_000_000, 15_000_000, 10_000_000, 12_000_000, 8_000_000, 5_000_000],
    })

    print("\nInput DataFrame:")
    print(df.to_string(index=False))

    # Convert DataFrame to list of dicts (what quick_irc expects)
    positions_from_df = df.to_dict(orient="records")

    result5 = quick_irc(positions_from_df, num_simulations=50_000)

    print(f"\nIRC (99.9%):    ${result5['irc']:,.0f}")
    print(f"IRC RWA:        ${result5['rwa']:,.0f}")

    # You can also add the results back to the DataFrame
    # (for reporting or further analysis)

except ImportError:
    print("\n  pandas not installed - skipping DataFrame example")
    print("  Install with: pip install pandas")


# =====================================================================
# Method 6: DataFrame with optional columns
# =====================================================================

print("\n" + "=" * 60)
print("Method 6: DataFrame with all columns")
print("=" * 60)

try:
    import pandas as pd

    # Full DataFrame with all optional columns
    df_full = pd.DataFrame({
        "issuer": ["Goldman", "JPMorgan", "Citi", "BofA"],
        "rating": ["A", "A", "BBB", "A"],
        "tenor_years": [5.0, 7.0, 4.0, 6.0],
        "notional": [25_000_000, 30_000_000, 20_000_000, 22_000_000],
        "seniority": ["senior_unsecured", "senior_unsecured", "subordinated", "senior_secured"],
        "sector": ["financial", "financial", "financial", "financial"],
        "liquidity_horizon_months": [3, 3, 6, 3],
        "is_long": [True, True, True, False],  # BofA is a short position
        "coupon_rate": [0.045, 0.04, 0.055, 0.035],
    })

    print("\nInput DataFrame:")
    print(df_full.to_string(index=False))

    # Convert to list of dicts
    positions_from_df_full = df_full.to_dict(orient="records")

    result6 = quick_irc(positions_from_df_full, num_simulations=50_000)

    print(f"\nIRC (99.9%):    ${result6['irc']:,.0f}")
    print(f"IRC RWA:        ${result6['rwa']:,.0f}")

except ImportError:
    print("\n  pandas not installed - skipping DataFrame example")


# =====================================================================
# Method 7: Read from CSV file
# =====================================================================

print("\n" + "=" * 60)
print("Method 7: Read from CSV file")
print("=" * 60)

try:
    import pandas as pd
    import tempfile

    # Create a sample CSV file
    csv_content = """issuer,rating,tenor_years,notional
Apple,AA,5.0,20000000
Microsoft,AAA,7.0,15000000
Ford,BB,3.0,10000000
Tesla,BBB,4.0,12000000
Netflix,BB,5.0,8000000
"""

    # Write to temp file (in real usage, you'd have an actual CSV file)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    # Read CSV into DataFrame
    df_csv = pd.read_csv(csv_path)

    print(f"\nLoaded from CSV:")
    print(df_csv.to_string(index=False))

    # Calculate IRC
    result7 = quick_irc(df_csv.to_dict(orient="records"), num_simulations=50_000)

    print(f"\nIRC (99.9%):    ${result7['irc']:,.0f}")
    print(f"IRC RWA:        ${result7['rwa']:,.0f}")

    # Clean up temp file
    os.unlink(csv_path)

    # Show how to save results back to CSV
    print("\n  To save results, add columns to your DataFrame:")
    print("    df['irc'] = result['irc']")
    print("    df['irc_rwa'] = result['rwa']")
    print("    df.to_csv('portfolio_with_irc.csv', index=False)")

except ImportError:
    print("\n  pandas not installed - skipping CSV example")


# =====================================================================
# Method 8: Export IRC by Issuer to DataFrame/CSV
# =====================================================================

print("\n" + "=" * 60)
print("Method 8: Export IRC by Issuer to DataFrame/CSV")
print("=" * 60)

try:
    import pandas as pd
    from irc import irc_to_dataframe, irc_to_csv

    # Use the issuer breakdown result from earlier (or recalculate)
    issuer_result = calculate_irc_by_issuer(irc_positions, IRCConfig(num_simulations=50_000))

    # Convert to DataFrame
    df_irc = irc_to_dataframe(issuer_result)

    print("\nFull DataFrame with summary rows:")
    print(df_irc.to_string(index=False))

    # Without summary rows (just issuers)
    df_issuers_only = irc_to_dataframe(issuer_result, include_summary=False)

    print("\n\nIssuers only (no summary rows):")
    print(df_issuers_only.to_string(index=False))

    # Save directly to CSV
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = f.name

    irc_to_csv(issuer_result, csv_path)

    print(f"\n\nSaved to CSV: {csv_path}")
    print("\nCSV contents:")
    with open(csv_path) as f:
        print(f.read())

    # Clean up
    import os
    os.unlink(csv_path)

except ImportError:
    print("\n  pandas not installed - skipping DataFrame/CSV export example")


# =====================================================================
# Method 9: Different Transition Matrices by Region/Sector
# =====================================================================

print("\n" + "=" * 60)
print("Method 9: Different Transition Matrices")
print("=" * 60)

from irc import list_transition_matrices, get_transition_matrix

print("\nAvailable matrices:", list_transition_matrices())

print("""
Matrices vary by region, sector, and economic conditions:
  - global/us_corporate: S&P historical average (default)
  - europe:              European corporates (lower defaults)
  - emerging_markets/em: EM corporates (higher defaults)
  - financials:          Banks/insurers
  - sovereign:           Sovereign ratings
  - recession/stressed:  Downturn scenario (2008-style)
  - benign:              Low-default environment
""")

# Compare IRC under different scenarios
test_positions = [
    {"issuer": "Corp A", "rating": "BBB", "tenor_years": 5.0, "notional": 20_000_000},
    {"issuer": "Corp B", "rating": "BB", "tenor_years": 3.0, "notional": 15_000_000},
]

print(f"{'Matrix':<20} {'IRC':>14} {'B Default Rate':>16}")
print("-" * 55)

for matrix_name in ["global", "europe", "emerging_markets", "recession", "benign"]:
    result = quick_irc(test_positions, num_simulations=30_000, transition_matrix=matrix_name)
    matrix = get_transition_matrix(matrix_name)
    b_default = matrix["B"]["D"] * 100
    print(f"{matrix_name:<20} ${result['irc']:>12,.0f} {b_default:>15.2f}%")

# Custom matrix example
print("\nCustom matrix example:")
custom_matrix = {
    "AAA": {"AAA": 0.90, "AA": 0.08, "A": 0.015, "BBB": 0.003, "BB": 0.001, "B": 0.0005, "CCC": 0.0004, "D": 0.0001},
    "AA":  {"AAA": 0.01, "AA": 0.90, "A": 0.07, "BBB": 0.015, "BB": 0.003, "B": 0.001, "CCC": 0.0005, "D": 0.0005},
    "A":   {"AAA": 0.002, "AA": 0.03, "A": 0.90, "BBB": 0.05, "BB": 0.012, "B": 0.004, "CCC": 0.001, "D": 0.001},
    "BBB": {"AAA": 0.001, "AA": 0.005, "A": 0.06, "BBB": 0.85, "BB": 0.06, "B": 0.015, "CCC": 0.005, "D": 0.004},
    "BB":  {"AAA": 0.001, "AA": 0.002, "A": 0.008, "BBB": 0.08, "BB": 0.80, "B": 0.08, "CCC": 0.02, "D": 0.009},
    "B":   {"AAA": 0.0, "AA": 0.001, "A": 0.003, "BBB": 0.005, "BB": 0.07, "B": 0.82, "CCC": 0.05, "D": 0.051},
    "CCC": {"AAA": 0.002, "AA": 0.0, "A": 0.002, "BBB": 0.015, "BB": 0.025, "B": 0.12, "CCC": 0.64, "D": 0.196},
    "D":   {"AAA": 0.0, "AA": 0.0, "A": 0.0, "BBB": 0.0, "BB": 0.0, "B": 0.0, "CCC": 0.0, "D": 1.0},
}
result_custom = quick_irc(test_positions, num_simulations=30_000, transition_matrix=custom_matrix)
print(f"  IRC with custom matrix: ${result_custom['irc']:,.0f}")


# =====================================================================
# Method 10: Multi-Matrix IRC (Mixed Regions/Sectors)
# =====================================================================

print("\n" + "=" * 60)
print("Method 10: Multi-Matrix IRC (Mixed Regions/Sectors)")
print("=" * 60)

print("""
When your portfolio has positions from different regions or sectors,
you can apply different transition matrices to each group.

Priority order: issuer > sector > region > default
""")

# Mixed portfolio
mixed_positions = [
    # US Tech
    {"issuer": "Apple", "rating": "AA", "tenor_years": 5, "notional": 20_000_000,
     "region": "US", "sector": "tech"},
    {"issuer": "Microsoft", "rating": "AAA", "tenor_years": 7, "notional": 15_000_000,
     "region": "US", "sector": "tech"},

    # EU Financials
    {"issuer": "Deutsche Bank", "rating": "A", "tenor_years": 5, "notional": 12_000_000,
     "region": "EU", "sector": "financial"},
    {"issuer": "BNP Paribas", "rating": "A", "tenor_years": 4, "notional": 10_000_000,
     "region": "EU", "sector": "financial"},

    # EM Energy
    {"issuer": "Petrobras", "rating": "BB", "tenor_years": 5, "notional": 8_000_000,
     "region": "EM", "sector": "energy"},
    {"issuer": "Pemex", "rating": "B", "tenor_years": 4, "notional": 6_000_000,
     "region": "EM", "sector": "energy"},
]

# Single matrix (baseline)
result_single = quick_irc(mixed_positions, num_simulations=30_000)
print(f"Single 'global' matrix:           ${result_single['irc']:,.0f}")

# By region
result_region = quick_irc(
    mixed_positions,
    num_simulations=30_000,
    matrix_by_region={
        "US": "global",
        "EU": "europe",
        "EM": "emerging_markets",
    }
)
print(f"By region (US/EU/EM):             ${result_region['irc']:,.0f}")

# By region + sector override
result_mixed = quick_irc(
    mixed_positions,
    num_simulations=30_000,
    matrix_by_region={
        "US": "global",
        "EU": "europe",
        "EM": "emerging_markets",
    },
    matrix_by_sector={
        "financial": "financials",  # EU banks use financials matrix
    },
)
print(f"By region + sector override:      ${result_mixed['irc']:,.0f}")

# With issuer-specific stress
result_stress = quick_irc(
    mixed_positions,
    num_simulations=30_000,
    matrix_by_region={
        "US": "global",
        "EU": "europe",
        "EM": "emerging_markets",
    },
    matrix_by_sector={
        "financial": "financials",
    },
    matrix_by_issuer={
        "Pemex": "recession",  # stress test specific issuer
    },
)
print(f"+ Pemex stressed (recession):     ${result_stress['irc']:,.0f}")

print(f"\nMatrices used: {result_mixed.get('matrices_used', [])}")

print("""
Resolution example:
  Apple (US, tech)           → region["US"]       → "global"
  Deutsche Bank (EU, financial) → sector["financial"] → "financials"
  Petrobras (EM, energy)     → region["EM"]       → "emerging_markets"
  Pemex (EM, energy)         → issuer["Pemex"]    → "recession"
""")


# =====================================================================
# Summary
# =====================================================================

print("\n" + "=" * 60)
print("SUMMARY: Required vs Optional Fields")
print("=" * 60)
print("""
REQUIRED (minimum for IRC calculation):
  - issuer:      Obligor name (same name = same migration)
  - rating:      AAA, AA, A, BBB, BB, B, or CCC
  - tenor_years: Remaining maturity in years
  - notional:    Position size in dollars

OPTIONAL (defaults applied if not provided):
  - seniority:   "senior_unsecured" (default)
                 Options: senior_secured (25% LGD),
                          senior_unsecured (45% LGD),
                          subordinated (75% LGD)
  - sector:      "corporate" (default) - for correlation
  - liquidity_horizon_months: 3 (default) - rebalancing frequency
  - is_long:     True (default) - False for CDS protection
  - coupon_rate: 0.05 (default) - for duration calculation
  - market_value: notional (default) - current market value

SIMULATION CONFIG:
  - num_simulations:   50,000-100,000 recommended
  - correlation:       0.50 typical (0.20-0.80 range)
  - transition_matrix: "global" (default)
                       Options: global, europe, em, financials,
                                sovereign, recession, benign
                       Or pass custom dict

MULTI-MATRIX (for mixed portfolios):
  - matrix_by_region:  {"US": "global", "EU": "europe", "EM": "em"}
  - matrix_by_sector:  {"financial": "financials", "sovereign": "sovereign"}
  - matrix_by_issuer:  {"Pemex": "recession"}  # highest priority
  Priority: issuer > sector > region > default
""")
