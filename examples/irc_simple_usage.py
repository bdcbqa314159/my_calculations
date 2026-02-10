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
  - num_simulations: 50,000-100,000 recommended
  - correlation:     0.50 typical (0.20-0.80 range)
""")
