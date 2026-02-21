# FRTB Internal Models Approach (IMA) — How To Guide

This guide shows how to calculate FRTB-IMA capital using the `frtb_ima.py` module.

## Quick Start

```bash
cd rwa_calc
./venv/bin/python -c "
from frtb_ima import quick_frtb_ima

result = quick_frtb_ima(
    es_10day_total=5_000_000,
    stressed_es_10day_total=9_000_000,
    drc_positions=[
        {'obligor': 'Corp_A', 'notional': 20_000_000, 'rating': 'A'},
        {'obligor': 'Corp_B', 'notional': 15_000_000, 'rating': 'BBB'},
    ],
)
print(f\"IMA Capital: \${result['total_capital']:,.0f}\")
print(f\"IMA RWA:     \${result['total_rwa']:,.0f}\")
"
```

## Overview

FRTB-IMA (MAR30-33) is the Basel III/IV successor to Basel 2.5's VaR+sVaR+IRC framework:

| Basel 2.5 | FRTB-IMA | Key Change |
|-----------|----------|------------|
| VaR (99%, 10-day) | ES (97.5%, liquidity-adjusted) | Expected Shortfall replaces VaR |
| Stressed VaR | Stressed ES | Same concept, ES-based |
| IRC | Internal DRC | Defaults only (migration in ES) |

**Capital Formula:**
```
IMA Capital = IMCC + DRC

IMCC = max(ES, m_c × ES_avg) + max(SES, m_c × SES_avg) + NMRF

m_c = 1.5 × (1 + plus_factor)
```

## Step-by-Step Guide

### Step 1: Define Risk Factors

```python
from frtb_ima import ESRiskFactor

risk_factors = [
    ESRiskFactor(
        risk_class="IR",           # IR, EQ, FX, CR, COM
        sub_category="major",      # Determines liquidity horizon
        es_10day=2_500_000,        # 10-day ES for this factor
        stressed_es_10day=4_000_000,  # Stressed period ES
        is_modellable=True,        # False = NMRF add-on
    ),
    ESRiskFactor("CR", "IG_corporate", es_10day=1_000_000, stressed_es_10day=1_800_000),
    ESRiskFactor("EQ", "large_cap",    es_10day=1_500_000, stressed_es_10day=3_000_000),
    ESRiskFactor("FX", "major",        es_10day=600_000,   stressed_es_10day=1_000_000),
]
```

### Step 2: Define DRC Positions

```python
from frtb_ima import DRCPosition

drc_positions = [
    DRCPosition(
        position_id="bond_1",
        obligor="Corp_A",
        notional=10_000_000,
        market_value=9_800_000,
        pd=0.004,              # Probability of default
        lgd=0.45,              # Loss given default
        systematic_factor=0.20,  # Correlation to systematic factor
        is_long=True,          # False for short positions
    ),
    DRCPosition("bond_2", "Corp_B", 8_000_000, 7_600_000, pd=0.02, lgd=0.45),
    DRCPosition("cds_1",  "Corp_B", 4_000_000, 3_900_000, pd=0.02, lgd=0.45, is_long=False),
]
```

### Step 3: Configure and Calculate

```python
from frtb_ima import FRTBIMAConfig, calculate_frtb_ima_capital

config = FRTBIMAConfig(
    plus_factor=0.0,           # From backtesting (0.0-1.0)
    drc_num_simulations=50_000,
    backtesting_exceptions=3,
)

result = calculate_frtb_ima_capital(
    risk_factors,
    drc_positions,
    config=config,
)

print(f"IMCC:        ${result['imcc']:,.0f}")
print(f"DRC:         ${result['drc_charge']:,.0f}")
print(f"Total:       ${result['total_capital']:,.0f}")
print(f"RWA:         ${result['total_rwa']:,.0f}")
```

## Liquidity Horizons (MAR31.13)

Risk factors are mapped to liquidity horizons based on their category:

| Horizon | Risk Class | Sub-Category |
|---------|------------|--------------|
| 10 days | IR | major |
| 20 days | IR | other |
| 20 days | CR | IG_sovereign |
| 40 days | EQ | large_cap |
| 40 days | FX | major |
| 40 days | CR | IG_corporate |
| 60 days | EQ | small_cap |
| 60 days | FX | other |
| 60 days | COM | energy, precious_metals |
| 60 days | CR | HY |
| 120 days | EQ | other |
| 120 days | COM | other |
| 120 days | CR | other |

```python
from frtb_ima import get_liquidity_horizon

lh = get_liquidity_horizon("CR", "HY")  # Returns 60
lh = get_liquidity_horizon("EQ", "large_cap")  # Returns 40
lh = get_liquidity_horizon("XX", "unknown")  # Returns 120 (default)
```

## Expected Shortfall Calculation

### Liquidity-Adjusted ES (MAR31.12)

```python
from frtb_ima import calculate_liquidity_adjusted_es

result = calculate_liquidity_adjusted_es(risk_factors)

print(f"ES Total: ${result['es_total']:,.0f}")
print(f"Factors:  {result['num_factors']}")

# Breakdown by liquidity bucket
for lh, info in result['es_by_bucket'].items():
    print(f"  {lh}d: ES_10d=${info['es_10day_sum']:,.0f}, scale={info['scale_factor']:.3f}")
```

**Formula:**
```
ES = sqrt( Σ [ ES_j(T=10) × sqrt((LH_j - LH_{j-1}) / 10) ]² )
```

### Stressed ES (MAR31.16-18)

```python
from frtb_ima import calculate_stressed_es

ses_result = calculate_stressed_es(
    risk_factors,
    es_full_current=es_result['es_total'],
    es_reduced_current=es_reduced,  # ES on reduced factor set
)

print(f"SES: ${ses_result['ses_total']:,.0f}")
print(f"Ratio: {ses_result['ratio']:.3f}")
```

**Formula:**
```
SES = ES_reduced_stressed × (ES_full_current / ES_reduced_current)
```

### NMRF Charge (MAR31.24-31)

Non-modellable risk factors are aggregated with zero diversification:

```python
from frtb_ima import calculate_nmrf_charge

# Add non-modellable factors
nmrf_factors = [
    ESRiskFactor("CR", "other", es_10day=200_000,
                 is_modellable=False, stressed_es_10day=500_000),
]

nmrf = calculate_nmrf_charge(nmrf_factors)
print(f"NMRF: ${nmrf['nmrf_total']:,.0f}")
```

## Internal DRC Model (MAR32)

### Monte Carlo Simulation

```python
from frtb_ima import simulate_drc_portfolio, calculate_ima_drc

# Run simulation
losses = simulate_drc_portfolio(drc_positions, num_simulations=50_000)

# Or use the wrapper
drc_result = calculate_ima_drc(drc_positions, config)

print(f"Mean loss:   ${drc_result['mean_loss']:,.0f}")
print(f"99th pctl:   ${drc_result['percentile_99']:,.0f}")
print(f"99.9th pctl: ${drc_result['drc_charge']:,.0f}")
```

**Key Features:**
- Two-factor Gaussian copula (systematic + idiosyncratic)
- 1-year horizon, 99.9% confidence
- Long/short netting only within same obligor
- Captures defaults only (migration risk is in ES)

### Netting Example

```python
# Same obligor, offsetting positions
positions = [
    DRCPosition("bond", "Corp_A", 10_000_000, 9_800_000, pd=0.02, lgd=0.45, is_long=True),
    DRCPosition("cds",  "Corp_A",  6_000_000, 5_900_000, pd=0.02, lgd=0.45, is_long=False),
]
# Net exposure if Corp_A defaults: (10M - 6M) × 45% = $1.8M
```

## Backtesting (MAR33)

```python
from frtb_ima import evaluate_backtesting

bt = evaluate_backtesting(num_exceptions=5, num_observations=250)

print(f"Zone: {bt['zone']}")           # green/yellow/red
print(f"Plus factor: {bt['plus_factor']}")
print(f"Exception rate: {bt['exception_rate_pct']:.2f}%")
```

### Traffic Light Zones

| Zone | Exceptions | Plus Factor | Action |
|------|------------|-------------|--------|
| Green | 0-4 | 0.00 | Model OK |
| Yellow | 5 | 0.40 | Review model |
| Yellow | 6 | 0.50 | Review model |
| Yellow | 7 | 0.65 | Review model |
| Yellow | 8 | 0.75 | Review model |
| Yellow | 9 | 0.85 | Review model |
| Red | 10+ | 1.00 | Model rejected |

### Impact on Capital

```python
# Plus factor increases the multiplication factor
m_c = 1.5 * (1 + plus_factor)

# Examples:
# plus_factor=0.00 → m_c=1.50
# plus_factor=0.40 → m_c=2.10
# plus_factor=1.00 → m_c=3.00
```

## P&L Attribution Test (MAR33)

```python
from frtb_ima import DeskPLA, evaluate_pla

desks = [
    DeskPLA("rates_desk",  spearman_correlation=0.92, kl_divergence=0.05),
    DeskPLA("credit_desk", spearman_correlation=0.78, kl_divergence=0.11),
    DeskPLA("fx_desk",     spearman_correlation=0.60, kl_divergence=0.15),
]

pla = evaluate_pla(desks)

for d in pla['desks']:
    status = "IMA" if d['ima_eligible'] else "SA fallback"
    print(f"{d['desk_id']}: {d['overall_zone']} → {status}")
```

### PLA Thresholds

| Metric | Green | Amber | Red |
|--------|-------|-------|-----|
| Spearman correlation | ≥ 0.80 | ≥ 0.70 | < 0.70 |
| KL divergence | ≤ 0.09 | ≤ 0.12 | > 0.12 |

- Desk must pass **both** metrics to achieve a zone
- **Red** desks fall back to FRTB-SA

## IMA vs SA Comparison

```python
from frtb_ima import compare_ima_vs_sa

comparison = compare_ima_vs_sa(
    risk_factors=risk_factors,
    drc_positions_ima=drc_positions,
    delta_positions_sa={
        "EQ": [{"bucket": "large_cap", "sensitivity": 1_500_000, "risk_weight": 20}],
        "FX": [{"bucket": "USD_EUR", "sensitivity": 700_000, "risk_weight": 15}],
    },
    drc_positions_sa=[
        {"obligor": "Corp_A", "notional": 10_000_000, "rating": "BBB"},
    ],
    config=config,
)

print(f"IMA Capital: ${comparison['ima_capital']:,.0f}")
print(f"SA Capital:  ${comparison['sa_capital']:,.0f}")
print(f"IMA/SA Ratio: {comparison['ima_to_sa_ratio']:.2f}")
```

## Complete Example

```python
from frtb_ima import (
    ESRiskFactor, DRCPosition, DeskPLA, FRTBIMAConfig,
    calculate_frtb_ima_capital,
)

# Risk factors
risk_factors = [
    ESRiskFactor("IR", "major",       es_10day=2_500_000, stressed_es_10day=4_000_000),
    ESRiskFactor("CR", "IG_corporate", es_10day=1_000_000, stressed_es_10day=1_800_000),
    ESRiskFactor("EQ", "large_cap",   es_10day=1_500_000, stressed_es_10day=3_000_000),
    ESRiskFactor("FX", "major",       es_10day=600_000,   stressed_es_10day=1_000_000),
    # Non-modellable
    ESRiskFactor("CR", "other", es_10day=200_000,
                 is_modellable=False, stressed_es_10day=500_000),
]

# DRC positions
drc_positions = [
    DRCPosition("p1", "Corp_A", 15_000_000, 14_500_000, pd=0.002, lgd=0.40),
    DRCPosition("p2", "Corp_B", 10_000_000,  9_500_000, pd=0.01,  lgd=0.45),
    DRCPosition("p3", "Corp_C",  8_000_000,  7_200_000, pd=0.04,  lgd=0.50),
]

# PLA desks
desks = [
    DeskPLA("rates",  spearman_correlation=0.90, kl_divergence=0.06),
    DeskPLA("credit", spearman_correlation=0.85, kl_divergence=0.07),
]

# Config
config = FRTBIMAConfig(
    plus_factor=0.0,
    drc_num_simulations=50_000,
    backtesting_exceptions=2,
)

# Calculate
result = calculate_frtb_ima_capital(
    risk_factors, drc_positions, config=config, desks=desks,
)

print(f"""
FRTB-IMA Capital Summary
========================
ES (liquidity-adjusted):  ${result['es']['es_total']:>12,.0f}
SES (stressed):           ${result['ses']['ses_total']:>12,.0f}
NMRF add-on:              ${result['imcc_detail']['nmrf']:>12,.0f}
IMCC:                     ${result['imcc']:>12,.0f}
DRC (99.9%):              ${result['drc_charge']:>12,.0f}
------------------------
TOTAL CAPITAL:            ${result['total_capital']:>12,.0f}
TOTAL RWA:                ${result['total_rwa']:>12,.0f}

Backtesting: {result['backtesting']['zone']} (plus factor: {result['backtesting']['plus_factor']})
PLA: {result['pla']['ima_eligible_desks']} desks IMA-eligible
""")
```

## Function Reference

| Function | Description |
|----------|-------------|
| `get_liquidity_horizon(risk_class, sub_cat)` | Map to LH days |
| `calculate_liquidity_adjusted_es(factors)` | Compute ES with LH scaling |
| `calculate_stressed_es(factors, es_full, es_reduced)` | Compute SES |
| `calculate_nmrf_charge(factors)` | NMRF add-on (zero diversification) |
| `simulate_drc_portfolio(positions, n_sims)` | Monte Carlo DRC losses |
| `calculate_ima_drc(positions, config)` | DRC charge (99.9%) |
| `evaluate_backtesting(exceptions, observations)` | Traffic light + plus factor |
| `evaluate_pla(desks)` | PLA test per desk |
| `calculate_imcc(factors, es, ses, ...)` | IMCC = ES + SES + NMRF |
| `calculate_frtb_ima_capital(factors, drc, ...)` | Full IMA capital |
| `quick_frtb_ima(es, ses, drc_positions)` | Simplified one-liner |
| `compare_ima_vs_sa(...)` | Side-by-side comparison |

## Key Formulas

### IMCC
```
IMCC = max(ES_{t-1}, m_c × ES_avg_60) + max(SES_{t-1}, m_c × SES_avg_60) + NMRF
m_c = 1.5 × (1 + plus_factor)
```

### Liquidity-Adjusted ES
```
ES = sqrt( Σ_j [ ES_j(T=10) × sqrt((LH_j - LH_{j-1}) / 10) ]² )
```

### Stressed ES
```
SES = ES_reduced_stressed × (ES_full_current / ES_reduced_current)
```

### DRC (Two-Factor Copula)
```
Z_i = ρ_i × X + sqrt(1 - ρ_i²) × ε_i

Default if Z_i < Φ⁻¹(PD_i)
```

## Tips

1. **Liquidity horizons**: Longer horizons increase capital; ensure correct sub-category mapping

2. **NMRF factors**: Set `is_modellable=False` for factors failing data quality tests; they're summed without diversification

3. **DRC netting**: Only applies within the same obligor; different obligors have no offset

4. **Plus factor**: Monitor backtesting exceptions; 5+ exceptions significantly increase capital

5. **PLA**: Desks failing PLA fall back to SA; focus on improving Spearman correlation and KL divergence

6. **Simulations**: Use at least 50,000 for DRC; more simulations = more stable 99.9th percentile

7. **Stress period**: Select a 12-month period that maximizes losses for your portfolio composition
