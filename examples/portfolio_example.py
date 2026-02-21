#!/usr/bin/env python3
"""
Unified Portfolio Example

Demonstrates how to use the Portfolio class for multiple risk calculations.

Usage:
    cd rwa_calc
    ./venv/bin/python examples/portfolio_example.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portfolio import Portfolio


# =============================================================================
# Example 1: Create Portfolio and Add Positions Manually
# =============================================================================

print("=" * 70)
print("EXAMPLE 1: Manual Position Entry")
print("=" * 70)

# Create portfolio
port = Portfolio(
    name="Corporate Bond Portfolio",
    reference_ccy="USD",
    as_of_date="2024-01-15"
)

# Add positions one by one
port.add("Apple Inc", notional=20_000_000, rating="AA", tenor_years=5.0,
         sector="tech", region="US")
port.add("Microsoft Corp", notional=15_000_000, rating="AAA", tenor_years=7.0,
         sector="tech", region="US")
port.add("Ford Motor", notional=10_000_000, rating="BB", tenor_years=3.0,
         sector="auto", region="US")
port.add("BMW AG", notional=12_000_000, rating="A", tenor_years=4.0,
         sector="auto", region="EU")
port.add("Deutsche Bank", notional=18_000_000, rating="BBB", tenor_years=5.0,
         sector="financial", region="EU")
port.add("Petrobras", notional=8_000_000, rating="BB", tenor_years=3.5,
         sector="energy", region="EM")
port.add("Toyota Motor", notional=15_000_000, rating="A", tenor_years=6.0,
         sector="auto", region="ASIA")

# Show portfolio
port.show()


# =============================================================================
# Example 2: Calculate IRC
# =============================================================================

print("=" * 70)
print("EXAMPLE 2: IRC Calculation")
print("=" * 70)

irc_result = port.irc(num_simulations=50_000)

print(f"""
  IRC Results (99.9%, 1-year horizon):

    IRC:               ${irc_result['irc']:>14,.0f}
    IRC RWA:           ${irc_result['rwa']:>14,.0f}
    Capital ratio:     {irc_result['capital_ratio']*100:>13.2f}%

  Loss Distribution:
    Mean loss:         ${irc_result['mean_loss']:>14,.0f}
    95th percentile:   ${irc_result['percentile_95']:>14,.0f}
    99th percentile:   ${irc_result['percentile_99']:>14,.0f}
    99.9th percentile: ${irc_result['percentile_999']:>14,.0f}
    Expected Shortfall:${irc_result['expected_shortfall_999']:>14,.0f}
""")


# =============================================================================
# Example 3: IRC by Issuer
# =============================================================================

print("=" * 70)
print("EXAMPLE 3: IRC Issuer Breakdown")
print("=" * 70)

issuer_result = port.irc_by_issuer(num_simulations=50_000)

print(f"\n  {'Issuer':<20} {'Rating':>6} {'Notional':>12} {'Standalone':>12} {'Marginal':>12}")
print(f"  {'-'*65}")

for c in issuer_result["issuer_contributions"]:
    print(f"  {c['issuer'][:20]:<20} {c['rating']:>6} ${c['notional']:>10,.0f} "
          f"${c['standalone_irc']:>10,.0f} ${c['marginal_irc']:>10,.0f}")

print(f"  {'-'*65}")
print(f"  Sum of standalone:                          ${sum(c['standalone_irc'] for c in issuer_result['issuer_contributions']):>12,.0f}")
print(f"  Diversification benefit:                    ${issuer_result['diversification_benefit']:>12,.0f}")
print(f"  Portfolio IRC:                              ${issuer_result['irc']:>12,.0f}")


# =============================================================================
# Example 4: Calculate VaR
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 4: VaR Calculation")
print("=" * 70)

# 1-day VaR
var_1d = port.var(confidence=0.99, horizon_days=1)
print(f"\n  99% 1-day VaR:  ${var_1d.get('var_abs', 0):>12,.0f}")
print(f"  99% 1-day ES:   ${var_1d.get('es_abs', 0):>12,.0f}")

# 10-day VaR (Basel standard)
var_10d = port.var(confidence=0.99, horizon_days=10)
print(f"\n  99% 10-day VaR: ${var_10d.get('var_abs', 0):>12,.0f}")
print(f"  99% 10-day ES:  ${var_10d.get('es_abs', 0):>12,.0f}")

# Different confidence levels
print(f"\n  VaR at different confidence levels (10-day):")
for conf in [0.95, 0.99, 0.999]:
    result = port.var(confidence=conf, horizon_days=10)
    print(f"    {conf:.1%}: ${result.get('var_abs', 0):>12,.0f}")


# =============================================================================
# Example 5: Full Risk Summary
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 5: Full Risk Summary")
print("=" * 70)

port.print_risk_summary(
    var_confidence=0.99,
    var_horizon=10,
    irc_simulations=50_000
)


# =============================================================================
# Example 6: Load from CSV
# =============================================================================

print("=" * 70)
print("EXAMPLE 6: Load Portfolio from CSV")
print("=" * 70)

# Create new portfolio from CSV
csv_port = Portfolio(
    name="CSV Portfolio",
    reference_ccy="EUR",
    as_of_date="2024-01-15"
)

# Load from sample CSV
csv_path = os.path.join(os.path.dirname(__file__), "sample_mixed_portfolio.csv")
if os.path.exists(csv_path):
    csv_port.add_from_csv(
        csv_path,
        fx_rates={"USD": 0.92, "GBP": 1.17, "JPY": 0.0062}
    )
    csv_port.show()

    # Quick risk summary
    irc = csv_port.irc(num_simulations=30_000)
    var = csv_port.var(confidence=0.99, horizon_days=10)

    print(f"  IRC (99.9%):     €{irc['irc']:>12,.0f}")
    print(f"  VaR (99%, 10d):  €{var.get('var_abs', 0):>12,.0f}")
else:
    print(f"  CSV file not found: {csv_path}")
    print("  Skipping CSV example...")


# =============================================================================
# Example 7: Method Chaining
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 7: Method Chaining")
print("=" * 70)

# Build portfolio with method chaining
result = (
    Portfolio("Quick Portfolio", reference_ccy="USD")
    .add("Company A", notional=10_000_000, rating="A", tenor_years=5.0)
    .add("Company B", notional=8_000_000, rating="BBB", tenor_years=3.0)
    .add("Company C", notional=12_000_000, rating="BB", tenor_years=4.0)
    .irc(num_simulations=30_000)
)

print(f"\n  Quick IRC calculation: ${result['irc']:,.0f}")


# =============================================================================
# Example 8: Export to DataFrame
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 8: Export to DataFrame")
print("=" * 70)

df = port.to_dataframe()
print(f"\n  DataFrame shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")
print(f"\n  Preview:")
print(df[['issuer', 'rating', 'notional', 'tenor_years', 'sector']].to_string(index=False))


# =============================================================================
# Example 9: Compare IRC and VaR
# =============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 9: Compare Risk Measures")
print("=" * 70)

# Get all risk measures
summary = port.risk_summary(
    var_confidence=0.99,
    var_horizon=10,
    irc_simulations=50_000
)

print(f"""
  Portfolio: {summary['portfolio_name']}
  Total MV:  ${summary['total_market_value']:,.0f}

  Risk Comparison:
  ─────────────────────────────────────────────────
  Measure              Value           % of MV
  ─────────────────────────────────────────────────
  VaR (99%, 10-day)    ${summary['var']['var_abs']:>12,.0f}    {summary['var']['var_abs']/summary['total_market_value']*100:>6.2f}%
  ES (99%, 10-day)     ${summary['var']['es_abs']:>12,.0f}    {summary['var']['es_abs']/summary['total_market_value']*100:>6.2f}%
  IRC (99.9%, 1-year)  ${summary['irc']['irc']:>12,.0f}    {summary['irc']['irc']/summary['total_market_value']*100:>6.2f}%
  ─────────────────────────────────────────────────

  Interpretation:
    - VaR/ES measure short-term market risk (spread changes)
    - IRC measures credit migration and default risk over 1 year
    - IRC > VaR because it captures tail credit events
""")


# =============================================================================
# Summary
# =============================================================================

print("=" * 70)
print("SUMMARY: Portfolio Methods")
print("=" * 70)

print("""
  Creating Portfolio:
    port = Portfolio("Name", reference_ccy="USD")

  Adding Positions:
    port.add("Issuer", notional=10e6, rating="A", tenor_years=5.0)
    port.add_from_csv("file.csv")
    port.add_from_df(dataframe)

  Viewing:
    port.show()
    port.to_dataframe()

  Risk Calculations:
    port.irc()                    # Incremental Risk Charge
    port.irc_by_issuer()          # IRC with issuer breakdown
    port.var(confidence=0.99)     # Value at Risk
    port.es(confidence=0.99)      # Expected Shortfall
    port.risk_summary()           # All measures
    port.print_risk_summary()     # Formatted output

  Properties:
    port.total_notional
    port.total_market_value
    port.num_issuers
    len(port)
""")

print("=" * 70)
print("END OF EXAMPLES")
print("=" * 70)
