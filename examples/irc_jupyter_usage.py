#!/usr/bin/env python3
"""
IRC Jupyter Notebook Usage — Interactive Portfolio Building

This example shows how to use IRC interactively in a Jupyter notebook.

Usage in Jupyter:
    # In a notebook cell, run each section interactively

Usage from command line:
    cd rwa_calc
    ./venv/bin/python examples/irc_jupyter_usage.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Cell 1: Import and create portfolio
# =============================================================================

from irc import IRCPortfolio

# Create portfolio with default settings
portfolio = IRCPortfolio(
    num_simulations=50_000,      # Monte Carlo simulations
    correlation=0.50,            # Systematic correlation
    transition_matrix="global",  # Default transition matrix
)

print("Portfolio created:", portfolio)


# =============================================================================
# Cell 2: Add positions interactively
# =============================================================================

# Add positions one by one
portfolio.add("Apple", "AA", 5.0, 20_000_000)
portfolio.add("Microsoft", "AAA", 7.0, 15_000_000)

# View current state
portfolio.show()


# =============================================================================
# Cell 3: Add more positions with options
# =============================================================================

# With seniority
portfolio.add("Ford", "BB", 3.0, 10_000_000, seniority="senior_secured")

# With custom LGD (overrides seniority)
portfolio.add("Tesla", "BBB", 4.0, 12_000_000, lgd=0.40)

# Short position (CDS protection)
portfolio.add("Ford", "BB", 5.0, 5_000_000, is_long=False)

# With region/sector for multi-matrix
portfolio.add("Petrobras", "BB", 5.0, 8_000_000,
              sector="energy", region="EM")

portfolio.show()


# =============================================================================
# Cell 4: Check portfolio summary
# =============================================================================

summary = portfolio.summary()
print("Portfolio Summary:")
print(f"  Positions: {summary['num_positions']}")
print(f"  Issuers:   {summary['num_issuers']}")
print(f"  Long:      ${summary['long_notional']:,.0f}")
print(f"  Short:     ${summary['short_notional']:,.0f}")
print(f"  Ratings:   {summary['ratings']}")


# =============================================================================
# Cell 5: Calculate IRC
# =============================================================================

result = portfolio.irc()

print(f"\nIRC Results:")
print(f"  IRC (99.9%): ${result['irc']:,.0f}")
print(f"  RWA:         ${result['rwa']:,.0f}")
print(f"  Capital %:   {result['capital_ratio']*100:.2f}%")


# =============================================================================
# Cell 6: IRC by Issuer breakdown
# =============================================================================

issuer_result = portfolio.irc_by_issuer()

print(f"\n{'Issuer':<12} {'Rating':>6} {'Notional':>14} {'Marginal IRC':>14} {'%':>7}")
print("-" * 58)
for c in issuer_result["issuer_contributions"]:
    print(f"{c['issuer']:<12} {c['rating']:>6} ${c['notional']:>12,.0f} "
          f"${c['marginal_irc']:>12,.0f} {c['pct_of_total']:>6.1f}%")

print(f"\nDiversification benefit: ${issuer_result['diversification_benefit']:,.0f}")


# =============================================================================
# Cell 7: Multi-matrix IRC (by region/sector)
# =============================================================================

result_multi = portfolio.irc(
    matrix_by_region={"EM": "emerging_markets"},
    matrix_by_sector={"energy": "recession"},  # stress energy sector
)

print(f"\nMulti-matrix IRC: ${result_multi['irc']:,.0f}")
print(f"Matrices used: {result_multi.get('matrices_used', ['global'])}")


# =============================================================================
# Cell 8: Export to DataFrame
# =============================================================================

df = portfolio.to_dataframe()
print("\nPositions DataFrame:")
print(df)

# Export IRC results to DataFrame
from irc import irc_to_dataframe
df_results = irc_to_dataframe(issuer_result)
print("\nIRC Results DataFrame:")
print(df_results)


# =============================================================================
# Cell 9: Method chaining (build in one statement)
# =============================================================================

p2 = (IRCPortfolio(num_simulations=30_000)
      .add("Bank A", "A", 5.0, 10_000_000, sector="financial", region="EU")
      .add("Bank B", "BBB", 4.0, 8_000_000, sector="financial", region="EU")
      .add("Oil Corp", "BB", 3.0, 6_000_000, sector="energy", region="EM")
      .add("Tech Inc", "AA", 6.0, 12_000_000, sector="tech", region="US"))

p2.show()
result2 = p2.irc(
    matrix_by_region={"US": "global", "EU": "europe", "EM": "emerging_markets"},
    matrix_by_sector={"financial": "financials"}
)
print(f"\nIRC: ${result2['irc']:,.0f}")


# =============================================================================
# Cell 10: Add from pandas DataFrame
# =============================================================================

import pandas as pd

# Load from DataFrame (e.g., from CSV)
df_input = pd.DataFrame([
    {"issuer": "Corp X", "rating": "BBB", "tenor_years": 5, "notional": 10_000_000},
    {"issuer": "Corp Y", "rating": "BB", "tenor_years": 3, "notional": 8_000_000, "lgd": 0.35},
    {"issuer": "Corp Z", "rating": "B", "tenor_years": 2, "notional": 5_000_000, "seniority": "subordinated"},
])

p3 = IRCPortfolio().add_from_dataframe(df_input)
p3.show()
print(f"\nIRC: ${p3.irc()['irc']:,.0f}")


# =============================================================================
# Quick Reference
# =============================================================================

print("\n" + "=" * 70)
print("QUICK REFERENCE")
print("=" * 70)
print("""
CREATE PORTFOLIO:
    portfolio = IRCPortfolio(num_simulations=50_000)

ADD POSITIONS:
    portfolio.add(issuer, rating, tenor_years, notional, ...)
    portfolio.add_from_dataframe(df)
    portfolio.add_many([{...}, {...}])

VIEW:
    portfolio.show()      # Display positions
    portfolio.summary()   # Get summary dict
    len(portfolio)        # Number of positions

CALCULATE:
    result = portfolio.irc()                    # Basic IRC
    result = portfolio.irc_by_issuer()          # With issuer breakdown
    result = portfolio.irc(matrix_by_region={...})  # Multi-matrix

MODIFY:
    portfolio.remove("pos_1")  # Remove by ID
    portfolio.clear()          # Remove all

EXPORT:
    df = portfolio.to_dataframe()     # Positions as DataFrame
    df = irc_to_dataframe(result)     # Results as DataFrame

OPTIONS FOR .add():
    issuer, rating, tenor_years, notional  (required)
    seniority: "senior_secured" / "senior_unsecured" / "subordinated"
    lgd: 0.0-1.0 (overrides seniority)
    is_long: True/False
    sector, region: for multi-matrix
""")
