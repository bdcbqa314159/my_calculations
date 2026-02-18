# IRC Calculator — How To Guide

This guide shows how to run IRC calculations from raw CSV portfolio data.

## Quick Start

```bash
cd rwa_calc
./venv/bin/python run_irc.py -i examples/sample_mixed_portfolio.csv -d 2024-01-15 -c EUR --fx-rates examples/fx_rates_eur.json
```

## Input Files

### 1. Portfolio CSV

Your CSV can have flexible column names. These are auto-detected:

| Field | Accepted Column Names |
|-------|----------------------|
| **Issuer** | Issuer, Issuer Name, Obligor, Company, Counterparty |
| **Notional** | Notional, Notional Amount, Exposure, Principal |
| **Rating** | Rating, Credit Rating, SP Rating (accepts AA+, BBB-, etc.) |
| **PD** | PD, Prob Default (accepts 0.02 or "2%") |
| **Maturity** | Maturity Date, Expiry, End Date |
| **Tenor** | tenor_years, Maturity (if numeric) |
| **Currency** | CCY, Currency |
| **Sector** | Sector, Industry |
| **Region** | Region, Country |
| **Seniority** | Seniority, Rank (Senior, Subordinated, Secured) |

**Example** (`sample_mixed_portfolio.csv`):
```csv
Issuer,Rating,PD,Maturity Date,Notional,Currency,Sector,Region,Seniority
TotalEnergies,A,,2027-06-15,15000000,EUR,energy,EU,Senior
BNP Paribas,,0.25%,2028-03-20,20000000,EUR,financial,EU,Subordinated
Apple Inc,AA-,,2028-09-30,25000000,USD,tech,US,Senior
Toyota Motor,A,,2028-02-28,2000000000,JPY,auto,ASIA,Senior
```

**Notes:**
- Either **Rating** OR **PD** is required (not both)
- Either **Maturity Date** OR **tenor_years** is required
- Granular ratings (AA+, BBB-) are normalized internally to base ratings (AA, BBB)
- PD can be decimal (0.0025) or percentage string ("0.25%")

### 2. FX Rates JSON

Two formats are supported:

#### Simple Format (default)
Rates expressed as "1 foreign = X reference":

```json
{
    "USD": 0.92,
    "GBP": 1.17,
    "JPY": 0.0062
}
```
Meaning: 1 USD = 0.92 EUR, 1 GBP = 1.17 EUR, etc. (when reference is EUR)

#### Market Convention Format
Standard FX pair quotes:

```json
{
    "EURUSD": 1.08,
    "GBPUSD": 1.27,
    "USDJPY": 150.0
}
```
Meaning: 1 EUR = 1.08 USD, 1 GBP = 1.27 USD, 1 USD = 150 JPY

## Command Line Options

```
./venv/bin/python run_irc.py [options]

Required:
  -i, --input FILE       Input CSV portfolio file
  -d, --as-of DATE       As-of date for TTM calculation (YYYY-MM-DD)

Optional:
  -c, --currency CCY     Reference currency (default: USD)
  -o, --output FILE      Output CSV for results
  --fx-rates FILE        JSON file with FX rates
  --fx-format FORMAT     FX rate format: "to_reference" or "market"
  -n, --simulations N    Number of MC simulations (default: 50000)
  --no-issuer-breakdown  Skip issuer contribution calculation
  -q, --quiet            Minimal output (just IRC number)
```

## Examples

### Basic Run (USD reference, default FX rates)
```bash
./venv/bin/python run_irc.py \
  -i examples/sample_mixed_portfolio.csv \
  -d 2024-01-15
```

### EUR Reference with Custom FX Rates
```bash
./venv/bin/python run_irc.py \
  -i examples/sample_mixed_portfolio.csv \
  -d 2024-01-15 \
  -c EUR \
  --fx-rates examples/fx_rates_eur.json
```

### Market Convention FX Rates
```bash
./venv/bin/python run_irc.py \
  -i examples/sample_mixed_portfolio.csv \
  -d 2024-01-15 \
  -c USD \
  --fx-rates examples/fx_rates_market.json \
  --fx-format market
```

### Export Results to CSV
```bash
./venv/bin/python run_irc.py \
  -i examples/sample_mixed_portfolio.csv \
  -d 2024-01-15 \
  -c EUR \
  --fx-rates examples/fx_rates_eur.json \
  -o /tmp/irc_results.csv
```

### Quick Check (Just the IRC Number)
```bash
./venv/bin/python run_irc.py \
  -i examples/sample_mixed_portfolio.csv \
  -d 2024-01-15 \
  -q
```

## Output

The tool outputs:
- Portfolio summary (positions, issuers, total notional, rating distribution)
- IRC results (99.9% VaR, RWA, capital ratio)
- Loss distribution (mean, 95th, 99th, 99.9th percentiles, ES)
- Issuer contributions (marginal IRC, diversification benefit)

Example output:
```
----------------------------------------------------------------------
IRC RESULTS
----------------------------------------------------------------------
  IRC (99.9%):           $    20,453,732
  IRC RWA:               $   255,671,653
  Capital ratio:                 12.39%

  Loss Distribution:
    Mean loss:           $     1,900,055
    95th percentile:     $     8,656,404
    99th percentile:     $    14,111,083
    99.9th percentile:   $    20,453,732
    Expected Shortfall:  $    21,829,426
```

## What Happens Internally

1. **Column Mapping** — Flexible column names are mapped to standard fields
2. **Rating Normalization** — Granular ratings (AA+, A-) → base ratings (AA, A)
3. **PD to Rating** — If PD provided instead of rating, converted via `get_rating_from_pd()`
4. **TTM Calculation** — Maturity dates → tenor in years (using as-of date)
5. **FX Conversion** — All notionals converted to reference currency
6. **Multi-Matrix IRC** — Different transition matrices by region/sector
7. **Monte Carlo** — 50,000 simulations (configurable)
8. **Issuer Breakdown** — Marginal contribution per issuer

## Transition Matrices

The IRC uses different matrices based on region and sector:

| Region | Matrix |
|--------|--------|
| US | global |
| EU | europe |
| ASIA | global |
| EM, LATAM | emerging_markets |

| Sector | Matrix |
|--------|--------|
| financial, bank, insurance | financials |
| sovereign, government | sovereign |
| others | (by region) |

## Files in This Directory

| File | Description |
|------|-------------|
| `sample_mixed_portfolio.csv` | Example portfolio (10 positions, 4 currencies) |
| `sample_raw_portfolio.csv` | Larger example (25 positions, 7 currencies) |
| `fx_rates_eur.json` | FX rates with EUR as reference (simple format) |
| `fx_rates_market.json` | FX rates in market convention |
| `irc_data_prep_example.py` | Python example showing the full workflow |
