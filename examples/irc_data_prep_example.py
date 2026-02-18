#!/usr/bin/env python3
"""
IRC Data Preparation Example — From Raw CSV to IRC Results

This example demonstrates the complete workflow:
  1. Load raw portfolio data (messy column names, dates, multiple currencies)
  2. Prepare data using irc_data_prep (TTM calculation, FX conversion, rating normalization)
  3. Run IRC calculation
  4. Export results

Usage:
    cd rwa_calc
    ./venv/bin/python examples/irc_data_prep_example.py

Notes:
    See the HOW TO WORK WITH IT section at the bottom for detailed guidance.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from irc_data_prep import prepare_irc_data, validate_irc_data, load_and_prepare
from irc import quick_irc, irc_to_csv


# =============================================================================
# CONFIGURATION
# =============================================================================

# As-of date for TTM calculation
AS_OF_DATE = "2024-01-15"

# Reference currency for notional conversion
REFERENCE_CCY = "USD"

# FX rates TO reference currency (1 unit of foreign = X units of reference)
FX_RATES = {
    "USD": 1.0,
    "EUR": 1.08,      # 1 EUR = 1.08 USD
    "GBP": 1.27,      # 1 GBP = 1.27 USD
    "JPY": 0.0067,    # 1 JPY = 0.0067 USD
    "CHF": 1.12,
    "KRW": 0.00075,   # 1 KRW = 0.00075 USD
    "HKD": 0.13,      # 1 HKD = 0.13 USD
    "BRL": 0.20,      # 1 BRL = 0.20 USD
}

# Region mapping for multi-matrix IRC
REGION_MATRIX_MAP = {
    "US": "global",
    "EU": "europe",
    "ASIA": "global",
    "EM": "emerging_markets",
}

# Sector matrix overrides
SECTOR_MATRIX_MAP = {
    "financial": "financials",
}

# IRC simulation settings
NUM_SIMULATIONS = 50_000


# =============================================================================
# STEP 1: LOAD RAW DATA
# =============================================================================

print("=" * 70)
print("IRC DATA PREPARATION EXAMPLE")
print("=" * 70)

print("\n" + "-" * 70)
print("STEP 1: Load Raw Data")
print("-" * 70)

# Load the sample CSV
csv_path = os.path.join(os.path.dirname(__file__), "sample_raw_portfolio.csv")
raw_df = pd.read_csv(csv_path)

print(f"\nLoaded {len(raw_df)} positions from: {os.path.basename(csv_path)}")
print("\nRaw data preview (first 5 rows):")
print(raw_df.head().to_string(index=False))

print(f"\nColumns in raw data: {list(raw_df.columns)}")
print(f"Currencies: {raw_df['Currency'].unique().tolist()}")
print(f"Ratings: {raw_df['Credit Rating'].dropna().unique().tolist()}")


# =============================================================================
# STEP 2: VALIDATE DATA (optional)
# =============================================================================

print("\n" + "-" * 70)
print("STEP 2: Validate Data")
print("-" * 70)

validation = validate_irc_data(raw_df)
print(f"\nValidation result: {'PASS' if validation['valid'] else 'FAIL'}")
if validation['errors']:
    print(f"Errors: {validation['errors']}")
if validation['warnings']:
    print(f"Warnings: {validation['warnings']}")


# =============================================================================
# STEP 3: PREPARE DATA
# =============================================================================

print("\n" + "-" * 70)
print("STEP 3: Prepare Data")
print("-" * 70)

print(f"\nConfiguration:")
print(f"  As-of date:      {AS_OF_DATE}")
print(f"  Reference CCY:   {REFERENCE_CCY}")
print(f"  FX rates:        {len(FX_RATES)} currencies")

# Prepare the data
clean_df = prepare_irc_data(
    raw_df,
    as_of_date=AS_OF_DATE,
    reference_ccy=REFERENCE_CCY,
    fx_rates=FX_RATES,
)

print(f"\nPrepared data preview:")
print(clean_df[['issuer', 'rating', 'tenor_years', 'notional', 'original_ccy', 'sector', 'region']].head(10).to_string(index=False))

# Summary statistics
print(f"\nSummary:")
print(f"  Positions:       {len(clean_df)}")
print(f"  Issuers:         {clean_df['issuer'].nunique()}")
print(f"  Total notional:  ${clean_df['notional'].sum():,.0f} {REFERENCE_CCY}")
print(f"  Avg tenor:       {clean_df['tenor_years'].mean():.1f} years")
print(f"  Rating dist:     {clean_df['rating'].value_counts().to_dict()}")


# =============================================================================
# STEP 4: RUN IRC CALCULATION
# =============================================================================

print("\n" + "-" * 70)
print("STEP 4: Run IRC Calculation")
print("-" * 70)

print(f"\nRunning {NUM_SIMULATIONS:,} Monte Carlo simulations...")
print(f"Using multi-matrix approach (by region and sector)")

# Convert to list of dicts for IRC
positions = clean_df.to_dict(orient="records")

# Run IRC with region/sector matrix mapping
result = quick_irc(
    positions,
    num_simulations=NUM_SIMULATIONS,
    matrix_by_region=REGION_MATRIX_MAP,
    matrix_by_sector=SECTOR_MATRIX_MAP,
)

print(f"\nIRC Results:")
print(f"  IRC (99.9%):           ${result['irc']:>14,.0f}")
print(f"  IRC RWA:               ${result['rwa']:>14,.0f}")
print(f"  Capital ratio:         {result['capital_ratio']*100:>13.2f}%")

print(f"\nLoss Distribution:")
print(f"  Mean loss:             ${result['mean_loss']:>14,.0f}")
print(f"  95th percentile:       ${result['percentile_95']:>14,.0f}")
print(f"  99th percentile:       ${result['percentile_99']:>14,.0f}")
print(f"  99.9th percentile:     ${result['percentile_999']:>14,.0f}")
print(f"  Expected Shortfall:    ${result['expected_shortfall_999']:>14,.0f}")

if result.get('matrices_used'):
    print(f"\nMatrices used: {result['matrices_used']}")


# =============================================================================
# STEP 5: EXPORT RESULTS (optional)
# =============================================================================

print("\n" + "-" * 70)
print("STEP 5: Export Results")
print("-" * 70)

# Save prepared data
prepared_path = "/tmp/irc_prepared_portfolio.csv"
clean_df.to_csv(prepared_path, index=False)
print(f"\nPrepared data saved to: {prepared_path}")

# Save IRC summary
summary_path = "/tmp/irc_summary.csv"
summary_df = pd.DataFrame([{
    "as_of_date": AS_OF_DATE,
    "reference_ccy": REFERENCE_CCY,
    "num_positions": len(clean_df),
    "num_issuers": clean_df['issuer'].nunique(),
    "total_notional": clean_df['notional'].sum(),
    "irc_999": result['irc'],
    "irc_rwa": result['rwa'],
    "capital_ratio": result['capital_ratio'],
    "mean_loss": result['mean_loss'],
    "percentile_99": result['percentile_99'],
    "percentile_999": result['percentile_999'],
    "expected_shortfall_999": result['expected_shortfall_999'],
    "num_simulations": NUM_SIMULATIONS,
}])
summary_df.to_csv(summary_path, index=False)
print(f"IRC summary saved to: {summary_path}")


# =============================================================================
# HOW TO WORK WITH IT
# =============================================================================

print("\n" + "=" * 70)
print("HOW TO WORK WITH IT")
print("=" * 70)

print("""
1. INPUT CSV FORMAT
   ─────────────────
   Your CSV can have flexible column names. These are auto-detected:

   REQUIRED (at least one of):
   ├─ Issuer:     "Issuer", "Issuer Name", "Obligor", "Company", "Counterparty"
   ├─ Notional:   "Notional", "Notional Amount", "Exposure", "Principal"
   ├─ Tenor:      "tenor_years", "Maturity" (if numeric)
   │              OR "Maturity Date" (if date, needs as_of_date)
   └─ Rating/PD:  "Rating", "Credit Rating" (accepts AA+, BBB-, etc.)
                  OR "PD", "Prob Default" (accepts 0.02 or "2%")

   OPTIONAL:
   ├─ Currency:   "CCY", "Currency" (for FX conversion)
   ├─ Sector:     "Sector", "Industry" (for matrix selection)
   ├─ Region:     "Region", "Country" (for matrix selection)
   ├─ Seniority:  "Seniority", "Rank" (Senior, Sub, Secured)
   └─ LGD:        "LGD" (0.0-1.0, overrides seniority)


2. PREPARING DATA
   ───────────────
   from irc_data_prep import prepare_irc_data

   clean_df = prepare_irc_data(
       raw_df,
       as_of_date="2024-01-15",        # For TTM calculation
       reference_ccy="USD",            # Convert all notionals to USD
       fx_rates={"EUR": 1.08, ...},    # FX rates to reference
   )


3. RUNNING IRC
   ────────────
   from irc import quick_irc

   result = quick_irc(
       clean_df.to_dict(orient="records"),
       num_simulations=50_000,
       matrix_by_region={"US": "global", "EU": "europe", "EM": "emerging_markets"},
       matrix_by_sector={"financial": "financials"},
   )


4. RATING PRIORITY
   ────────────────
   If both rating and PD provided, rating wins.
   Granular ratings (AA+, BBB-) are auto-normalized to base (AA, BBB).


5. AVAILABLE TRANSITION MATRICES
   ──────────────────────────────
   global         - S&P Global/US Corporate (default)
   europe         - European corporates
   emerging_markets - EM (higher default rates)
   financials     - Financial institutions
   sovereign      - Government bonds
   recession      - Stressed scenario
   benign         - Low-default environment


6. ONE-LINER (from CSV to IRC)
   ────────────────────────────
   from irc_data_prep import load_and_prepare
   from irc import quick_irc

   result = quick_irc(
       load_and_prepare("portfolio.csv", as_of_date="2024-01-15", reference_ccy="USD")
       .to_dict(orient="records")
   )
   print(f"IRC: ${result['irc']:,.0f}")
""")

print("=" * 70)
print("END OF EXAMPLE")
print("=" * 70)
