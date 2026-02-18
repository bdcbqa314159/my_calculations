#!/usr/bin/env python3
"""
IRC Calculator — Command Line Tool

Calculate Incremental Risk Charge from a CSV portfolio file.

Usage:
    ./venv/bin/python run_irc.py --input portfolio.csv --as-of 2024-01-15

Examples:
    # Basic run
    ./venv/bin/python run_irc.py -i portfolio.csv -d 2024-01-15

    # With currency conversion and output file
    ./venv/bin/python run_irc.py -i portfolio.csv -d 2024-01-15 -c USD -o results.csv

    # With custom FX rates file
    ./venv/bin/python run_irc.py -i portfolio.csv -d 2024-01-15 -c USD --fx-rates fx_rates.json

Input CSV Template:
    See examples/sample_raw_portfolio.csv for a template.

    Required columns (flexible names accepted):
    - Issuer (or: "Issuer Name", "Obligor", "Company")
    - Notional (or: "Notional Amount", "Exposure", "Principal")
    - Rating OR PD (or: "Credit Rating", "Prob Default")
    - Maturity Date OR tenor_years (or: "Maturity", "Term")

    Optional columns:
    - Currency (for FX conversion)
    - Sector/Industry (for matrix selection)
    - Region/Country (for matrix selection)
    - Seniority (Senior, Subordinated, Secured)
    - LGD (0.0-1.0, overrides seniority)
"""

import argparse
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from irc_data_prep import prepare_irc_data, validate_irc_data
from irc import quick_irc, calculate_irc_by_issuer, irc_to_csv, IRCPosition, IRCConfig
from fx import FXRates, load_fx_rates_from_dict, get_default_fx_rates

# Region to matrix mapping
REGION_MATRIX_MAP = {
    "US": "global",
    "EU": "europe",
    "EM": "emerging_markets",
    "ASIA": "global",
    "LATAM": "emerging_markets",
}

# Sector to matrix mapping
SECTOR_MATRIX_MAP = {
    "financial": "financials",
    "financials": "financials",
    "bank": "financials",
    "insurance": "financials",
    "sovereign": "sovereign",
    "government": "sovereign",
}

# Currency symbols
CCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CHF": "Fr",
    "CAD": "C$",
    "AUD": "A$",
    "CNY": "¥",
    "HKD": "HK$",
    "SGD": "S$",
    "KRW": "₩",
    "INR": "₹",
    "BRL": "R$",
    "MXN": "Mex$",
    "ZAR": "R",
}


def get_ccy_symbol(ccy: str) -> str:
    """Get currency symbol for display."""
    return CCY_SYMBOLS.get(ccy.upper(), ccy)


def load_fx_rates(fx_file: str, reference_ccy: str, fx_format: str = "to_reference") -> FXRates:
    """
    Load FX rates from JSON file or use defaults.

    Parameters
    ----------
    fx_file : str
        Path to JSON file with FX rates.
    reference_ccy : str
        Reference currency (e.g., "USD", "EUR").
    fx_format : str
        How rates are expressed in the JSON:
        - "to_reference": 1 foreign = X reference (e.g., {"EUR": 1.08} means 1 EUR = 1.08 USD)
        - "market": standard market convention pairs (e.g., {"EURUSD": 1.08})

    Returns
    -------
    FXRates
        Initialized FX rate converter.
    """
    if fx_file and os.path.exists(fx_file):
        with open(fx_file) as f:
            rates_dict = json.load(f)

        if fx_format == "market":
            # Market convention pairs like {"EURUSD": 1.08, "USDJPY": 150}
            fx = FXRates()
            fx.set_rates(rates_dict)
            return fx
        else:
            # Simple format: {"EUR": 1.08, "GBP": 1.27}
            return load_fx_rates_from_dict(rates_dict, "to_reference", reference_ccy)

    return get_default_fx_rates(reference_ccy)


def print_header():
    """Print header."""
    print("=" * 70)
    print("IRC CALCULATOR")
    print("=" * 70)


def print_summary(df: pd.DataFrame, result: dict, reference_ccy: str):
    """Print results summary."""
    sym = get_ccy_symbol(reference_ccy)

    print("\n" + "-" * 70)
    print("PORTFOLIO SUMMARY")
    print("-" * 70)
    print(f"  Positions:       {len(df)}")
    print(f"  Issuers:         {df['issuer'].nunique()}")
    print(f"  Total notional:  {sym}{df['notional'].sum():>14,.0f} {reference_ccy}")
    print(f"  Avg tenor:       {df['tenor_years'].mean():>14.1f} years")

    # Rating distribution
    print(f"\n  Rating distribution:")
    for rating, count in df['rating'].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {rating:>4}: {count:>3} ({pct:>5.1f}%)")

    # Region distribution if available
    if 'region' in df.columns:
        print(f"\n  Region distribution:")
        for region, group in df.groupby('region'):
            notional = group['notional'].sum()
            print(f"    {region:>6}: {sym}{notional:>14,.0f} ({len(group)} positions)")

    print("\n" + "-" * 70)
    print("IRC RESULTS")
    print("-" * 70)
    print(f"  IRC (99.9%):           {sym}{result['irc']:>14,.0f}")
    print(f"  IRC RWA:               {sym}{result['rwa']:>14,.0f}")
    print(f"  Capital ratio:         {result['capital_ratio']*100:>13.2f}%")

    print(f"\n  Loss Distribution:")
    print(f"    Mean loss:           {sym}{result['mean_loss']:>14,.0f}")
    print(f"    95th percentile:     {sym}{result['percentile_95']:>14,.0f}")
    print(f"    99th percentile:     {sym}{result['percentile_99']:>14,.0f}")
    print(f"    99.9th percentile:   {sym}{result['percentile_999']:>14,.0f}")
    print(f"    Expected Shortfall:  {sym}{result['expected_shortfall_999']:>14,.0f}")

    if result.get('matrices_used'):
        print(f"\n  Matrices used: {result['matrices_used']}")


def print_issuer_breakdown(issuer_result: dict, reference_ccy: str):
    """Print issuer breakdown."""
    sym = get_ccy_symbol(reference_ccy)

    print("\n" + "-" * 70)
    print("ISSUER CONTRIBUTIONS")
    print("-" * 70)
    print(f"\n  {'Issuer':<20} {'Rating':>6} {'Notional':>12} {'Standalone':>12} {'Marginal':>12} {'%':>6}")
    print("  " + "-" * 75)

    for c in issuer_result["issuer_contributions"][:15]:  # Top 15
        print(f"  {c['issuer'][:20]:<20} {c['rating']:>6} {sym}{c['notional']:>10,.0f} "
              f"{sym}{c['standalone_irc']:>10,.0f} {sym}{c['marginal_irc']:>10,.0f} {c['pct_of_total']:>5.1f}%")

    if len(issuer_result["issuer_contributions"]) > 15:
        print(f"  ... and {len(issuer_result['issuer_contributions']) - 15} more issuers")

    # Calculate sum of standalone IRCs
    sum_standalone = sum(c['standalone_irc'] for c in issuer_result["issuer_contributions"])

    print("  " + "-" * 75)
    print(f"  {'Sum of standalone IRCs:':<52} {sym}{sum_standalone:>12,.0f}")
    print(f"  {'Diversification benefit:':<52} {sym}{issuer_result['diversification_benefit']:>12,.0f}")
    print(f"  {'Portfolio IRC:':<52} {sym}{issuer_result['irc']:>12,.0f}")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate IRC from a CSV portfolio file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i portfolio.csv -d 2024-01-15
  %(prog)s -i portfolio.csv -d 2024-01-15 -c USD -o results.csv
  %(prog)s -i portfolio.csv -d 2024-01-15 -c EUR --fx-rates fx_rates.json

Input CSV should have columns like:
  Issuer Name, Credit Rating, Maturity Date, Notional Amount, Currency, ...

See examples/sample_raw_portfolio.csv for a template.
        """
    )

    parser.add_argument("-i", "--input", required=True,
                        help="Input CSV file path")
    parser.add_argument("-d", "--as-of", required=True,
                        help="As-of date for TTM calculation (YYYY-MM-DD)")
    parser.add_argument("-c", "--currency", default="USD",
                        help="Reference currency for conversion (default: USD)")
    parser.add_argument("-o", "--output",
                        help="Output CSV file for results (optional)")
    parser.add_argument("--fx-rates",
                        help="JSON file with FX rates (optional)")
    parser.add_argument("--fx-format", choices=["to_reference", "market"],
                        default="to_reference",
                        help="FX rate format: 'to_reference' (1 foreign = X ref) or 'market' (EURUSD=1.08)")
    parser.add_argument("-n", "--simulations", type=int, default=100_000,
                        help="Number of MC simulations (default: 100000)")
    parser.add_argument("--no-issuer-breakdown", action="store_true",
                        help="Skip issuer breakdown calculation")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Minimal output (just IRC number)")

    args = parser.parse_args()

    # Check input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Load FX rates
    fx_rates = load_fx_rates(args.fx_rates, args.currency, args.fx_format)

    if not args.quiet:
        print_header()
        print(f"\nInput:      {args.input}")
        print(f"As-of:      {args.as_of}")
        print(f"Currency:   {args.currency}")
        print(f"Simulations:{args.simulations:,}")

    # Load and prepare data
    if not args.quiet:
        print("\n" + "-" * 70)
        print("LOADING DATA")
        print("-" * 70)

    raw_df = pd.read_csv(args.input)

    if not args.quiet:
        print(f"  Loaded {len(raw_df)} rows from CSV")

    # Prepare data
    try:
        clean_df = prepare_irc_data(
            raw_df,
            as_of_date=args.as_of,
            reference_ccy=args.currency,
            fx_rates=fx_rates,
        )
    except ValueError as e:
        print(f"Error preparing data: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"  Prepared {len(clean_df)} positions")

    # Run IRC
    if not args.quiet:
        print(f"\n  Running IRC simulation...")

    positions = clean_df.to_dict(orient="records")

    result = quick_irc(
        positions,
        num_simulations=args.simulations,
        matrix_by_region=REGION_MATRIX_MAP,
        matrix_by_sector=SECTOR_MATRIX_MAP,
    )

    # Quiet mode - just print IRC
    if args.quiet:
        print(f"{result['irc']:.0f}")
        return

    # Print summary
    print_summary(clean_df, result, args.currency)

    # Issuer breakdown
    if not args.no_issuer_breakdown:
        # Build IRCPosition objects for issuer breakdown
        irc_positions = []
        for i, p in enumerate(positions):
            irc_positions.append(IRCPosition(
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
                lgd=p.get("lgd"),
            ))

        config = IRCConfig(num_simulations=args.simulations)
        issuer_result = calculate_irc_by_issuer(irc_positions, config)
        print_issuer_breakdown(issuer_result, args.currency)

        # Export if requested
        if args.output:
            irc_to_csv(issuer_result, args.output)
            print(f"\n  Results saved to: {args.output}")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
