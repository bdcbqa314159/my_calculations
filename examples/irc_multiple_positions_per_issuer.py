#!/usr/bin/env python3
"""
IRC — Multiple Positions per Issuer

This example demonstrates how IRC handles multiple positions for the same issuer.

Key behavior:
  - Same issuer = same rating migration (they move together)
  - Each position calculates its own P&L based on its tenor/notional
  - Positions are NOT aggregated — each contributes separately to the loss

Why this matters:
  - A 10-year bond loses MORE than a 2-year bond on a downgrade
    (longer duration = higher spread sensitivity)
  - Different seniorities have different LGDs on default
  - Long vs short positions can offset within the same issuer

Usage:
    cd /Users/bernardocohen/repos/work/rwa_calc
    ./venv/bin/python examples/irc_multiple_positions_per_issuer.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from irc import quick_irc, IRCPosition, IRCConfig, calculate_irc


print("=" * 70)
print("IRC: Multiple Positions per Issuer")
print("=" * 70)


# =====================================================================
# Example 1: Same issuer, different tenors
# =====================================================================

print("\n" + "-" * 70)
print("Example 1: Same issuer, different tenors")
print("-" * 70)
print("""
All 3 positions are Apple bonds with rating AA.
When Apple migrates (e.g., AA → BBB), ALL positions move together.
But the 10Y bond loses more than the 2Y bond (higher duration).
""")

positions_tenors = [
    {"issuer": "Apple", "rating": "AA", "tenor_years": 2.0, "notional": 10_000_000},
    {"issuer": "Apple", "rating": "AA", "tenor_years": 5.0, "notional": 10_000_000},
    {"issuer": "Apple", "rating": "AA", "tenor_years": 10.0, "notional": 10_000_000},
]

result = quick_irc(positions_tenors, num_simulations=50_000)

print(f"  Position 1: Apple 2Y, $10M")
print(f"  Position 2: Apple 5Y, $10M")
print(f"  Position 3: Apple 10Y, $10M")
print(f"\n  Total notional: $30M (but NOT aggregated)")
print(f"  IRC: ${result['irc']:,.0f}")

# Compare to single aggregated position
single = quick_irc(
    [{"issuer": "Apple", "rating": "AA", "tenor_years": 5.0, "notional": 30_000_000}],
    num_simulations=50_000
)
print(f"\n  vs. Single 5Y $30M position: ${single['irc']:,.0f}")
print(f"  → Different because tenor mix affects duration/spread sensitivity")


# =====================================================================
# Example 2: Same issuer, different seniorities
# =====================================================================

print("\n" + "-" * 70)
print("Example 2: Same issuer, different seniorities")
print("-" * 70)
print("""
Senior secured (25% LGD) vs subordinated (75% LGD).
On default, the subordinated bond loses 3x more.
""")

positions_seniority = [
    {"issuer": "Ford", "rating": "BB", "tenor_years": 5.0, "notional": 10_000_000,
     "seniority": "senior_secured"},
    {"issuer": "Ford", "rating": "BB", "tenor_years": 5.0, "notional": 10_000_000,
     "seniority": "subordinated"},
]

result = quick_irc(positions_seniority, num_simulations=50_000)

print(f"  Position 1: Ford 5Y Senior Secured, $10M (LGD=25%)")
print(f"  Position 2: Ford 5Y Subordinated, $10M (LGD=75%)")
print(f"\n  IRC: ${result['irc']:,.0f}")

# Compare each alone
secured_only = quick_irc(
    [{"issuer": "Ford", "rating": "BB", "tenor_years": 5.0, "notional": 10_000_000,
      "seniority": "senior_secured"}],
    num_simulations=50_000
)
sub_only = quick_irc(
    [{"issuer": "Ford", "rating": "BB", "tenor_years": 5.0, "notional": 10_000_000,
      "seniority": "subordinated"}],
    num_simulations=50_000
)
print(f"\n  Senior secured alone: ${secured_only['irc']:,.0f}")
print(f"  Subordinated alone:   ${sub_only['irc']:,.0f}")
print(f"  → Sub is ~3x more risky due to higher LGD")


# =====================================================================
# Example 3: Long + Short on same issuer (hedge)
# =====================================================================

print("\n" + "-" * 70)
print("Example 3: Long bond + Short CDS on same issuer (hedge)")
print("-" * 70)
print("""
Long $10M bond + short $8M CDS on same issuer.
When issuer defaults or downgrades:
  - Long position loses
  - Short position gains (partially offsets)
""")

positions_hedge = [
    {"issuer": "Tesla", "rating": "BBB", "tenor_years": 5.0, "notional": 10_000_000,
     "is_long": True},
    {"issuer": "Tesla", "rating": "BBB", "tenor_years": 5.0, "notional": 8_000_000,
     "is_long": False},  # CDS protection = short credit
]

result_hedge = quick_irc(positions_hedge, num_simulations=50_000)

print(f"  Long:  Tesla 5Y bond, $10M")
print(f"  Short: Tesla 5Y CDS,  $8M")
print(f"  Net:   $2M long")
print(f"\n  IRC (hedged): ${result_hedge['irc']:,.0f}")

# Compare to unhedged
unhedged = quick_irc(
    [{"issuer": "Tesla", "rating": "BBB", "tenor_years": 5.0, "notional": 10_000_000}],
    num_simulations=50_000
)
print(f"  IRC (unhedged $10M): ${unhedged['irc']:,.0f}")
print(f"  → Hedge reduces IRC by {(1 - result_hedge['irc']/unhedged['irc'])*100:.0f}%")


# =====================================================================
# Example 4: Multiple issuers with multiple positions each
# =====================================================================

print("\n" + "-" * 70)
print("Example 4: Realistic portfolio with multiple positions per issuer")
print("-" * 70)

portfolio = [
    # Apple: 3 bonds
    {"issuer": "Apple", "rating": "AA", "tenor_years": 3.0, "notional": 15_000_000},
    {"issuer": "Apple", "rating": "AA", "tenor_years": 5.0, "notional": 20_000_000},
    {"issuer": "Apple", "rating": "AA", "tenor_years": 7.0, "notional": 10_000_000},

    # Microsoft: 2 bonds
    {"issuer": "Microsoft", "rating": "AAA", "tenor_years": 5.0, "notional": 25_000_000},
    {"issuer": "Microsoft", "rating": "AAA", "tenor_years": 10.0, "notional": 15_000_000},

    # Ford: bond + CDS hedge
    {"issuer": "Ford", "rating": "BB", "tenor_years": 4.0, "notional": 12_000_000, "is_long": True},
    {"issuer": "Ford", "rating": "BB", "tenor_years": 5.0, "notional": 6_000_000, "is_long": False},

    # Single positions
    {"issuer": "Netflix", "rating": "BB", "tenor_years": 5.0, "notional": 8_000_000},
    {"issuer": "AMC", "rating": "CCC", "tenor_years": 2.0, "notional": 3_000_000},
]

result_portfolio = quick_irc(portfolio, num_simulations=50_000)

print(f"\n  Portfolio breakdown:")
print(f"    Apple:     3 positions, $45M total")
print(f"    Microsoft: 2 positions, $40M total")
print(f"    Ford:      2 positions, $18M gross ($6M net long)")
print(f"    Netflix:   1 position,  $8M")
print(f"    AMC:       1 position,  $3M")
print(f"\n  Total: 9 positions, 5 issuers")
print(f"  IRC: ${result_portfolio['irc']:,.0f}")


# =====================================================================
# Summary: How it works
# =====================================================================

print("\n" + "=" * 70)
print("SUMMARY: How multiple positions per issuer work")
print("=" * 70)
print("""
1. SAME ISSUER = SAME MIGRATION
   All positions for "Apple" migrate together. If Apple goes from
   AA → BBB, ALL Apple bonds experience the same rating change.

2. EACH POSITION HAS ITS OWN P&L
   - Different tenors → different durations → different spread sensitivity
   - Different seniorities → different LGDs on default
   - Long vs short → opposite P&L directions

3. POSITIONS ARE NOT AGGREGATED
   You should NOT pre-aggregate positions. Keep them separate:

   WRONG:
     {"issuer": "Apple", "notional": 45_000_000, "tenor_years": 5.0}

   RIGHT:
     {"issuer": "Apple", "notional": 15_000_000, "tenor_years": 3.0}
     {"issuer": "Apple", "notional": 20_000_000, "tenor_years": 5.0}
     {"issuer": "Apple", "notional": 10_000_000, "tenor_years": 7.0}

4. WHAT TO DO WITH YOUR DATA
   If you have a DataFrame with one row per position, just use it directly:

   df = pd.DataFrame(...)
   result = quick_irc(df.to_dict(orient="records"))

   The IRC model will automatically:
   - Group by issuer for migration
   - Calculate P&L per position
   - Sum losses across all positions
""")
