# Minimal Inputs Reference Guide

Quick reference for the minimum inputs required by each analysis module.

## Quick Start Examples

### IRC (Incremental Risk Charge)

```python
from irc import quick_irc

result = quick_irc([
    {"issuer": "Corp_A", "notional": 10_000_000, "tenor_years": 5, "rating": "BBB"},
])
print(f"IRC: ${result['irc']:,.0f}")
```

### VaR / ES (Value at Risk / Expected Shortfall)

```python
from var import quick_var
import numpy as np

returns = np.random.normal(0.0003, 0.012, 252)  # 1 year daily returns
result = quick_var(returns, confidence=0.99, position_value=10_000_000)
print(f"VaR: ${result['var_abs']:,.0f}")
print(f"ES:  ${result['es_abs']:,.0f}")
```

### FRTB-IMA (Internal Models Approach)

```python
from frtb_ima import quick_frtb_ima

result = quick_frtb_ima(
    es_10day_total=5_000_000,
    stressed_es_10day_total=9_000_000,
)
print(f"IMA Capital: ${result['total_capital']:,.0f}")
```

### CDS RWA

```python
from cds_rwa import quick_cds_rwa

result = quick_cds_rwa(notional=10_000_000, pd=0.01, maturity=5)
print(f"CDS RWA: ${result['total_rwa']:,.0f}")
```

### Repo RWA

```python
from repo_rwa import quick_repo_rwa

result = quick_repo_rwa(cash_amount=10_000_000, maturity=0.25)
print(f"Repo RWA: ${result['total_rwa']:,.0f}")
```

### TRS RWA (Total Return Swap)

```python
from trs_rwa import quick_trs_rwa

result = quick_trs_rwa(notional=10_000_000, pd=0.01, maturity=3)
print(f"TRS RWA: ${result['total_rwa']:,.0f}")
```

### Loan RWA

```python
from loan_rwa import quick_loan_rwa

result = quick_loan_rwa(total_commitment=10_000_000, pd=0.02, maturity=5)
print(f"Loan RWA: ${result['total_rwa']:,.0f}")
```

### Operational Risk (SMA)

```python
from operational_risk import calculate_sma_capital

result = calculate_sma_capital(bi=500_000_000)
print(f"OpRisk Capital: ${result['sma_capital']:,.0f}")
```

### Portfolio (Unified)

```python
from portfolio import Portfolio

port = Portfolio("My Portfolio", reference_ccy="USD")
port.add("Corp_A", notional=10_000_000, rating="BBB", tenor_years=5)
port.add("Corp_B", notional=8_000_000, rating="A", tenor_years=3)

summary = port.risk_summary()
print(f"IRC: ${summary['irc']['irc']:,.0f}")
print(f"VaR: ${summary['var']['var_abs']:,.0f}")
```

---

## Minimal Inputs by Module

### IRC (Incremental Risk Charge)

**Module:** `irc.py`
**Purpose:** Credit migration and default risk (Basel 2.5, 1-year 99.9%)

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `issuer` | Yes | str | - |
| `notional` | Yes | float | - |
| `tenor_years` | Yes | float | - |
| `rating` | One of | str | - |
| `pd` | these | float | - |
| `lgd` | No | float | 0.45 (senior), 0.75 (sub) |
| `seniority` | No | str | "senior_unsecured" |
| `sector` | No | str | "corporate" |
| `region` | No | str | "global" |
| `num_simulations` | No | int | 100,000 |

```python
# Minimum
quick_irc([{"issuer": "X", "notional": 1e6, "tenor_years": 5, "rating": "BBB"}])

# With PD instead of rating
quick_irc([{"issuer": "X", "notional": 1e6, "tenor_years": 5, "pd": 0.02}])
```

---

### VaR (Value at Risk)

**Module:** `var.py`
**Purpose:** Market risk potential loss at confidence level

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `returns` | Yes | array | - |
| `confidence` | No | float | 0.99 |
| `horizon_days` | No | int | 1 |
| `method` | No | str | "parametric" |
| `position_value` | No | float | None (returns %) |

```python
# Minimum (returns as percentage)
quick_var(returns)

# With position value (returns absolute $)
quick_var(returns, position_value=10_000_000)

# 10-day VaR
quick_var(returns, horizon_days=10)
```

**Methods:** `"parametric"`, `"historical"`, `"monte_carlo"`

---

### ES / CVaR (Expected Shortfall)

**Module:** `var.py`
**Purpose:** Average loss beyond VaR (tail risk)

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `returns` | Yes | array | - |
| `confidence` | No | float | 0.99 |
| `horizon_days` | No | int | 1 |

```python
from var import parametric_es

# ES is also included in quick_var output
result = quick_var(returns)
print(result['es_pct'], result['es_abs'])

# Standalone ES
es = parametric_es(returns, confidence=0.975)
```

---

### FRTB-IMA (Internal Models Approach)

**Module:** `frtb_ima.py`
**Purpose:** Basel III/IV market risk capital (ES-based)

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `es_10day_total` | Yes | float | - |
| `stressed_es_10day_total` | Yes | float | - |
| `drc_positions` | No | list | None |
| `plus_factor` | No | float | 0.0 |

```python
# Minimum (no DRC)
quick_frtb_ima(es_10day_total=5e6, stressed_es_10day_total=9e6)

# With DRC positions
quick_frtb_ima(
    es_10day_total=5e6,
    stressed_es_10day_total=9e6,
    drc_positions=[
        {"obligor": "Corp_A", "notional": 10e6, "rating": "BBB"},
    ]
)
```

**Full calculation requires:**
- `ESRiskFactor` objects (risk_class, sub_category, es_10day)
- `DRCPosition` objects (obligor, notional, market_value, pd)

---

### FRTB-SA (Standardized Approach)

**Module:** `market_risk.py`
**Purpose:** Basel III/IV market risk - standardized

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `delta_positions` | Yes | dict | - |
| `vega_positions` | No | dict | {} |
| `curvature_positions` | No | dict | {} |
| `drc_positions` | No | list | [] |

```python
from market_risk import calculate_frtb_sa

result = calculate_frtb_sa(
    delta_positions={
        "EQ": [{"bucket": "large_cap", "sensitivity": 1_000_000, "risk_weight": 20}],
    }
)
```

---

### CDS RWA

**Module:** `cds_rwa.py`
**Purpose:** Credit default swap capital charges

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `notional` | Yes | float | - |
| `pd` | Yes | float | - |
| `maturity` | Yes | float | - |
| `is_protection_buyer` | No | bool | True |
| `spread_bps` | No | float | 100 |
| `counterparty_rating` | No | str | "A" |
| `approach` | No | str | "sa" |
| `book` | No | str | "banking" |

```python
# Minimum
quick_cds_rwa(notional=10e6, pd=0.01, maturity=5)

# Protection seller
quick_cds_rwa(notional=10e6, pd=0.01, maturity=5, is_protection_buyer=False)

# IRB approach
quick_cds_rwa(notional=10e6, pd=0.01, maturity=5, approach="irb")
```

---

### Repo RWA

**Module:** `repo_rwa.py`
**Purpose:** Repurchase agreement capital charges

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `cash_amount` | Yes | float | - |
| `maturity` | Yes | float | - |
| `securities_value` | No | float | cash × 1.02 |
| `is_repo` | No | bool | True |
| `security_type` | No | str | "sovereign_debt" |
| `security_rating` | No | str | "AAA" |
| `counterparty_rating` | No | str | "A" |
| `approach` | No | str | "sa" |

```python
# Minimum
quick_repo_rwa(cash_amount=10e6, maturity=0.25)

# Reverse repo with equity collateral
quick_repo_rwa(
    cash_amount=10e6,
    maturity=0.5,
    is_repo=False,
    security_type="equity",
)
```

---

### TRS RWA (Total Return Swap)

**Module:** `trs_rwa.py`
**Purpose:** Total return swap capital charges

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `notional` | Yes | float | - |
| `pd` | Yes | float | - |
| `maturity` | Yes | float | - |
| `is_total_return_receiver` | No | bool | True |
| `underlying_type` | No | str | "equity" |
| `counterparty_rating` | No | str | "A" |
| `approach` | No | str | "sa" |
| `book` | No | str | "banking" |

```python
# Minimum
quick_trs_rwa(notional=10e6, pd=0.01, maturity=3)

# Total return payer on credit
quick_trs_rwa(
    notional=10e6,
    pd=0.01,
    maturity=3,
    is_total_return_receiver=False,
    underlying_type="credit",
)
```

---

### Loan RWA

**Module:** `loan_rwa.py`
**Purpose:** Traditional lending capital charges

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `total_commitment` | Yes | float | - |
| `pd` | Yes | float | - |
| `maturity` | Yes | float | - |
| `drawn` | No | float | total_commitment |
| `approach` | No | str | "sa" |
| `is_revolving` | No | bool | False |
| `borrower_sector` | No | str | "corporate" |

```python
# Minimum (fully drawn)
quick_loan_rwa(total_commitment=10e6, pd=0.02, maturity=5)

# Partially drawn revolver
quick_loan_rwa(
    total_commitment=10e6,
    drawn=6e6,
    pd=0.02,
    maturity=3,
    is_revolving=True,
)
```

---

### SA-CCR (Counterparty Credit Risk)

**Module:** `counterparty_risk.py`
**Purpose:** Standardized approach for counterparty exposure

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `trades` | Yes | list | - |
| `collateral_held` | No | float | 0 |
| `collateral_posted` | No | float | 0 |
| `is_margined` | No | bool | False |

**Trade fields:**
| Field | Required | Default |
|-------|----------|---------|
| `notional` | Yes | - |
| `asset_class` | Yes | - |
| `maturity` | Yes | - |
| `mtm` | Yes | - |
| `delta` | No | 1.0 |

```python
from counterparty_risk import calculate_sa_ccr_ead

trades = [
    {"notional": 10e6, "asset_class": "IR", "maturity": 5, "mtm": 500_000},
    {"notional": 5e6, "asset_class": "FX", "maturity": 1, "mtm": -100_000},
]
ead = calculate_sa_ccr_ead(trades)
```

**Asset classes:** `"IR"`, `"FX"`, `"CR"`, `"EQ"`, `"COM"`

---

### Operational Risk (SMA)

**Module:** `operational_risk.py`
**Purpose:** Standardized Measurement Approach for OpRisk

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `bi` | Yes* | float | - |
| `average_annual_loss` | No | float | 0 (ILM=1) |

*Or provide detailed components:

| Component | Type | Description |
|-----------|------|-------------|
| `ildc` | float | Interest, Lease, Dividend Component |
| `sc` | float | Services Component |
| `fc` | float | Financial Component |

```python
from operational_risk import calculate_sma_capital

# Minimum (just BI)
result = calculate_sma_capital(bi=500_000_000)

# With loss history (ILM > 1)
result = calculate_sma_capital(bi=500_000_000, average_annual_loss=50_000_000)
```

---

### LCR (Liquidity Coverage Ratio)

**Module:** `liquidity.py`
**Purpose:** 30-day liquidity stress ratio

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `hqla_assets` | Yes | list | - |
| `liabilities` | Yes | list | - |
| `receivables` | Yes | list | - |
| `inflow_cap_rate` | No | float | 0.75 |

```python
from liquidity import calculate_lcr

result = calculate_lcr(
    hqla_assets=[
        {"type": "level1", "amount": 100_000_000},
        {"type": "level2a", "amount": 50_000_000},
    ],
    liabilities=[
        {"type": "retail_stable", "amount": 200_000_000},
        {"type": "wholesale_operational", "amount": 100_000_000},
    ],
    receivables=[
        {"type": "retail", "amount": 20_000_000},
    ],
)
```

---

### NSFR (Net Stable Funding Ratio)

**Module:** `liquidity.py`
**Purpose:** 1-year funding stability ratio

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `asf_items` | Yes | list | - |
| `rsf_items` | Yes | list | - |

```python
from liquidity import calculate_nsfr

result = calculate_nsfr(
    asf_items=[
        {"type": "tier1_capital", "amount": 50_000_000},
        {"type": "retail_deposits_stable", "amount": 200_000_000},
    ],
    rsf_items=[
        {"type": "cash", "amount": 10_000_000},
        {"type": "corporate_loans_1yr", "amount": 150_000_000},
    ],
)
```

---

### IRRBB (Interest Rate Risk Banking Book)

**Module:** `irrbb.py`
**Purpose:** EVE and NII sensitivity to rate changes

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `assets` | Yes | float | - |
| `liabilities` | Yes | float | - |
| `assets_by_bucket` | Yes | dict | - |
| `liabilities_by_bucket` | Yes | dict | - |
| `tier1_capital` | Yes | float | - |
| `currency` | No | str | "USD" |

```python
from irrbb import calculate_full_irrbb_analysis

result = calculate_full_irrbb_analysis(
    assets=1_000_000_000,
    liabilities=900_000_000,
    assets_by_bucket={"0-3m": 100e6, "3-6m": 150e6, "6-12m": 200e6, "1-2y": 250e6, "2-5y": 200e6, ">5y": 100e6},
    liabilities_by_bucket={"0-3m": 200e6, "3-6m": 200e6, "6-12m": 150e6, "1-2y": 150e6, "2-5y": 100e6, ">5y": 100e6},
    tier1_capital=80_000_000,
)
```

---

### Crypto Assets

**Module:** `crypto_assets.py`
**Purpose:** Crypto exposure capital treatment

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `exposures` | Yes | list | - |
| `tier1_capital` | Yes | float | - |

**Exposure fields:**
| Field | Required | Description |
|-------|----------|-------------|
| `amount` | Yes | Exposure value |
| `group` | Yes | "1a", "1b", "2a", "2b" |

```python
from crypto_assets import calculate_total_crypto_rwa

result = calculate_total_crypto_rwa(
    exposures=[
        {"amount": 1_000_000, "group": "1a"},  # Tokenized traditional asset
        {"amount": 500_000, "group": "2b"},    # Unbacked crypto
    ],
    tier1_capital=100_000_000,
)
```

**Groups:**
- `1a`: Tokenized traditional assets (same RW as underlying)
- `1b`: Stablecoins with stabilization mechanism
- `2a`: Crypto with hedging recognition
- `2b`: Unbacked crypto (1250% RW, 2% T1 limit)

---

### G-SIB / TLAC

**Module:** `gsib_tlac.py`
**Purpose:** Systemic importance and loss-absorbing capacity

| Input | Required | Type | Default |
|-------|----------|------|---------|
| `rwa` | Yes | float | - |
| `leverage_exposure` | Yes | float | - |
| `gsib_buffer` | No | float | 0 |

```python
from gsib_tlac import calculate_tlac_requirement

result = calculate_tlac_requirement(
    rwa=500_000_000_000,
    leverage_exposure=1_000_000_000_000,
    gsib_buffer=0.02,  # 2% G-SIB buffer
)
```

---

### Portfolio (Unified)

**Module:** `portfolio.py`
**Purpose:** Multi-risk calculation from single portfolio

| Method | Required Inputs | Optional |
|--------|-----------------|----------|
| `Portfolio()` | `name` | `reference_ccy`, `as_of_date` |
| `.add()` | `issuer`, `notional`, `tenor_years`, `rating OR pd` | `sector`, `region`, `seniority` |
| `.irc()` | - | `num_simulations` |
| `.var()` | - | `confidence`, `horizon_days`, `method` |
| `.risk_summary()` | - | all of above |

```python
from portfolio import Portfolio

# Build portfolio
port = Portfolio("Credit Portfolio", reference_ccy="USD")
port.add("Apple", notional=10e6, rating="AA", tenor_years=5)
port.add("Ford", notional=8e6, pd=0.02, tenor_years=3)

# Individual calculations
irc = port.irc()
var = port.var(confidence=0.99, horizon_days=10)

# Full summary
summary = port.risk_summary()
```

---

## Input Type Quick Reference

### Rating Strings
```
"AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
"BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
"B+", "B", "B-", "CCC", "CC", "C", "D"
```

### Asset Classes (SA-CCR)
```
"IR"   - Interest Rate
"FX"   - Foreign Exchange
"CR"   - Credit
"EQ"   - Equity
"COM"  - Commodity
```

### Risk Classes (FRTB)
```
"IR"   - Interest Rate (major, other)
"EQ"   - Equity (large_cap, small_cap, other)
"FX"   - FX (major, other)
"CR"   - Credit Spread (IG_sovereign, IG_corporate, HY, other)
"COM"  - Commodity (energy, precious_metals, other)
```

### Seniority
```
"senior_secured"
"senior_unsecured"
"subordinated"
```

### Approaches
```
"sa"   - Standardized Approach
"irb"  - Internal Ratings Based (Foundation or Advanced)
"firb" - Foundation IRB
"airb" - Advanced IRB
```

---

## Common Patterns

### Rating vs PD
All modules accept either rating or PD:
```python
# Using rating (converted to PD internally)
{"rating": "BBB"}

# Using explicit PD
{"pd": 0.004}
```

### Defaults Summary
Most modules apply sensible defaults:
- **LGD:** 45% (senior), 75% (subordinated)
- **Confidence:** 99% (VaR), 99.9% (IRC/DRC)
- **Horizon:** 1 day (VaR), 1 year (IRC)
- **Approach:** SA (standardized)
- **Sector:** "corporate"
- **Region:** "global" or "US"

### Scaling
```python
# Position value converts % to $
var = quick_var(returns, position_value=10_000_000)

# RWA to capital: ÷ 12.5 (or × 8%)
capital = rwa / 12.5
```
