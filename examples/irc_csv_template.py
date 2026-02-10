#!/usr/bin/env python3
"""
IRC CSV Processing Template — Multi-Region Portfolio

This template shows how to:
  1. Load a portfolio from CSV
  2. Run IRC with region-specific transition matrices
  3. Export results to CSV

Usage:
    cd rwa_calc
    ./venv/bin/python examples/irc_csv_template.py

    # With your own CSV:
    ./venv/bin/python examples/irc_csv_template.py --input my_portfolio.csv --output my_results.csv
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from irc import quick_irc, calculate_irc_by_issuer, irc_to_csv, IRCPosition, IRCConfig


# =============================================================================
# STEP 1: CSV INPUT FORMAT
# =============================================================================
#
# Your CSV should have these columns:
#
# REQUIRED:
#   issuer        - Obligor name (positions with same issuer migrate together)
#   rating        - Credit rating: AAA, AA, A, BBB, BB, B, CCC
#   tenor_years   - Remaining maturity in years
#   notional      - Position size in dollars
#
# OPTIONAL (defaults applied if missing):
#   region        - US, EU, EM, ASIA, etc. (default: US)
#   sector        - financial, energy, tech, etc. (default: corporate)
#   seniority     - senior_secured, senior_unsecured, subordinated (default: senior_unsecured)
#   lgd           - Custom LGD 0.0-1.0, overrides seniority (default: from seniority)
#   is_long       - True/False (default: True)
#   liquidity_horizon_months - 3, 6, or 12 (default: 3)
#   position_id   - Unique ID (default: auto-generated)
#
# =============================================================================


# =============================================================================
# STEP 2: REGION-TO-MATRIX MAPPING
# =============================================================================
#
# Different regions use different transition matrices to reflect
# regional default/migration patterns.

REGION_MATRIX_MAP = {
    "US": "global",              # US uses global matrix
    "EU": "europe",              # Europe-specific matrix
    "EM": "emerging_markets",    # Emerging markets (higher default rates)
    "ASIA": "global",            # Asia uses global (or customize)
    "LATAM": "emerging_markets", # Latin America uses EM matrix
}

# Sector overrides (applied after region)
SECTOR_MATRIX_MAP = {
    "financial": "financials",   # Banks/insurance have different dynamics
    "sovereign": "sovereign",    # Government bonds
}


# =============================================================================
# STEP 3: SAMPLE CSV DATA (for demo)
# =============================================================================

SAMPLE_CSV = """issuer,rating,tenor_years,notional,region,sector,seniority,is_long
Apple Inc,AA,5.0,20000000,US,tech,senior_unsecured,True
Microsoft Corp,AAA,7.0,15000000,US,tech,senior_unsecured,True
JPMorgan Chase,A,4.0,18000000,US,financial,senior_unsecured,True
Deutsche Bank,A,5.0,12000000,EU,financial,senior_unsecured,True
BNP Paribas,A,4.0,10000000,EU,financial,subordinated,True
Petrobras,BB,5.0,8000000,EM,energy,senior_secured,True
Vale SA,BBB,4.0,7000000,EM,industrial,senior_unsecured,True
Tencent,A,3.0,10000000,ASIA,tech,senior_unsecured,True
Samsung,AA,5.0,12000000,ASIA,tech,senior_unsecured,True
Pemex,B,4.0,6000000,LATAM,energy,senior_unsecured,True
Ford Motor,BB,5.0,5000000,US,auto,senior_unsecured,False
"""


def load_portfolio(csv_path: str = None) -> pd.DataFrame:
    """
    Load portfolio from CSV file or use sample data.

    Args:
        csv_path: Path to CSV file. If None, uses sample data.

    Returns:
        DataFrame with portfolio positions.
    """
    if csv_path and os.path.exists(csv_path):
        print(f"Loading portfolio from: {csv_path}")
        df = pd.read_csv(csv_path)
    else:
        print("Using sample portfolio data")
        from io import StringIO
        df = pd.read_csv(StringIO(SAMPLE_CSV))

    # Apply defaults for missing columns
    defaults = {
        "region": "US",
        "sector": "corporate",
        "seniority": "senior_unsecured",
        "is_long": True,
        "liquidity_horizon_months": 3,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Convert is_long to boolean if needed
    if df["is_long"].dtype == object:
        df["is_long"] = df["is_long"].map({"True": True, "False": False, True: True, False: False})

    # Replace NaN with None for optional fields (lgd, position_id, etc.)
    # This ensures proper handling downstream
    df = df.where(pd.notna(df), None)

    return df


def run_irc(df: pd.DataFrame, num_simulations: int = 50_000) -> dict:
    """
    Run IRC calculation with multi-region matrix mapping.

    Args:
        df: Portfolio DataFrame
        num_simulations: Number of Monte Carlo simulations

    Returns:
        IRC result dictionary
    """
    # Convert DataFrame to list of dicts and clean NaN values
    positions = df.to_dict(orient="records")

    # Clean NaN/None values from each position dict
    import math
    def clean_position(pos):
        cleaned = {}
        for k, v in pos.items():
            # Skip None values and NaN floats
            if v is None:
                continue
            try:
                if isinstance(v, float) and math.isnan(v):
                    continue
            except (TypeError, ValueError):
                pass
            cleaned[k] = v
        return cleaned

    positions = [clean_position(p) for p in positions]

    # Run IRC with region and sector matrix mappings
    result = quick_irc(
        positions,
        num_simulations=num_simulations,
        matrix_by_region=REGION_MATRIX_MAP,
        matrix_by_sector=SECTOR_MATRIX_MAP,
    )

    return result


def run_irc_by_issuer(df: pd.DataFrame, num_simulations: int = 50_000) -> dict:
    """
    Run IRC with per-issuer breakdown.

    Args:
        df: Portfolio DataFrame
        num_simulations: Number of Monte Carlo simulations

    Returns:
        IRC result with issuer contributions
    """
    import math

    def safe_get(row, key, default=None):
        """Get value from row, returning default if NaN or missing."""
        val = row.get(key)
        if val is None:
            return default
        try:
            if isinstance(val, float) and math.isnan(val):
                return default
        except (TypeError, ValueError):
            pass
        return val

    # Build IRCPosition objects
    positions = []
    for i, row in df.iterrows():
        pos = IRCPosition(
            position_id=safe_get(row, "position_id", f"pos_{i}"),
            issuer=row["issuer"],
            notional=row["notional"],
            market_value=safe_get(row, "market_value", row["notional"]),
            rating=row["rating"],
            tenor_years=row["tenor_years"],
            seniority=safe_get(row, "seniority", "senior_unsecured"),
            sector=safe_get(row, "sector", "corporate"),
            liquidity_horizon_months=int(safe_get(row, "liquidity_horizon_months", 3)),
            is_long=safe_get(row, "is_long", True),
            coupon_rate=safe_get(row, "coupon_rate", 0.05),
            lgd=safe_get(row, "lgd", None),
        )
        positions.append(pos)

    config = IRCConfig(
        num_simulations=num_simulations,
        transition_matrix="global",  # base matrix (overridden by region/sector)
    )

    return calculate_irc_by_issuer(positions, config)


def print_results(df: pd.DataFrame, result: dict, issuer_result: dict = None):
    """Print formatted results."""

    print("\n" + "=" * 70)
    print("IRC CALCULATION RESULTS")
    print("=" * 70)

    # Portfolio summary
    print("\n  PORTFOLIO SUMMARY")
    print("  " + "-" * 50)
    print(f"    Positions:       {len(df)}")
    print(f"    Issuers:         {df['issuer'].nunique()}")
    print(f"    Regions:         {', '.join(df['region'].unique())}")
    print(f"    Total notional:  ${df['notional'].sum():,.0f}")
    print(f"    Long notional:   ${df[df['is_long'] == True]['notional'].sum():,.0f}")
    print(f"    Short notional:  ${df[df['is_long'] == False]['notional'].sum():,.0f}")

    # By region breakdown
    print("\n  BY REGION")
    print("  " + "-" * 50)
    for region in df["region"].unique():
        region_df = df[df["region"] == region]
        matrix = REGION_MATRIX_MAP.get(region, "global")
        print(f"    {region:<8} {len(region_df):>3} positions  "
              f"${region_df['notional'].sum():>14,.0f}  matrix: {matrix}")

    # IRC results
    print("\n  IRC RESULTS")
    print("  " + "-" * 50)
    print(f"    IRC (99.9%):           ${result['irc']:>14,.0f}")
    print(f"    IRC RWA:               ${result['rwa']:>14,.0f}")
    print(f"    Capital ratio:         {result['capital_ratio']*100:>13.2f}%")

    print("\n  LOSS DISTRIBUTION")
    print("  " + "-" * 50)
    print(f"    Mean loss:             ${result['mean_loss']:>14,.0f}")
    print(f"    95th percentile:       ${result['percentile_95']:>14,.0f}")
    print(f"    99th percentile:       ${result['percentile_99']:>14,.0f}")
    print(f"    99.9th percentile:     ${result['percentile_999']:>14,.0f}")
    print(f"    Expected Shortfall:    ${result['expected_shortfall_999']:>14,.0f}")

    if result.get("matrices_used"):
        print(f"\n    Matrices used:         {result['matrices_used']}")

    # Issuer contributions
    if issuer_result:
        print("\n  ISSUER CONTRIBUTIONS")
        print("  " + "-" * 50)
        print(f"  {'Issuer':<20} {'Rating':>6} {'Notional':>14} {'Marginal IRC':>14} {'%':>7}")
        print("  " + "-" * 65)

        for c in issuer_result["issuer_contributions"]:
            print(f"  {c['issuer']:<20} {c['rating']:>6} ${c['notional']:>12,.0f} "
                  f"${c['marginal_irc']:>12,.0f} {c['pct_of_total']:>6.1f}%")

        print("  " + "-" * 65)
        print(f"  {'Diversification benefit:':<43} ${issuer_result['diversification_benefit']:>12,.0f}")
        print(f"  {'Portfolio IRC:':<43} ${issuer_result['irc']:>12,.0f}")


def main():
    parser = argparse.ArgumentParser(description="IRC CSV Processing Template")
    parser.add_argument("--input", "-i", help="Input CSV file path")
    parser.add_argument("--output", "-o", help="Output CSV file path for results")
    parser.add_argument("--simulations", "-n", type=int, default=50_000,
                        help="Number of Monte Carlo simulations (default: 50000)")
    args = parser.parse_args()

    # Step 1: Load portfolio
    print("\n" + "=" * 70)
    print("STEP 1: LOADING PORTFOLIO")
    print("=" * 70)
    df = load_portfolio(args.input)
    print(f"\nLoaded {len(df)} positions:\n")
    print(df.to_string(index=False))

    # Step 2: Run IRC
    print("\n" + "=" * 70)
    print("STEP 2: RUNNING IRC CALCULATION")
    print("=" * 70)
    print(f"\nRunning {args.simulations:,} Monte Carlo simulations...")
    print("Using multi-matrix approach (region + sector mappings)")

    result = run_irc(df, num_simulations=args.simulations)
    issuer_result = run_irc_by_issuer(df, num_simulations=args.simulations)

    # Step 3: Print results
    print_results(df, result, issuer_result)

    # Step 4: Export to CSV (optional)
    if args.output:
        print("\n" + "=" * 70)
        print("STEP 3: EXPORTING RESULTS")
        print("=" * 70)
        irc_to_csv(issuer_result, args.output)
        print(f"\nResults exported to: {args.output}")

        # Show output file contents
        print("\nOutput CSV contents:")
        print("-" * 50)
        with open(args.output) as f:
            print(f.read())

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)

    return result, issuer_result


if __name__ == "__main__":
    main()
