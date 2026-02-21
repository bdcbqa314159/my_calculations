# VaR and CVaR (Expected Shortfall) — How To Guide

This guide shows how to compute Value at Risk (VaR) and Conditional VaR (Expected Shortfall) using the `var.py` module.

## Quick Start

```bash
cd rwa_calc
./venv/bin/python -c "
from var import quick_var
import numpy as np

returns = np.random.normal(0.0003, 0.012, 252)
result = quick_var(returns, confidence=0.99, position_value=10_000_000)
print(f\"VaR: \${result['var_abs']:,.0f}\")
print(f\"ES:  \${result['es_abs']:,.0f}\")
"
```

## Step-by-Step Guide

### Step 1: Prepare Your Returns Data

```python
import numpy as np

# Option A: From price series
prices = [100, 101, 99.5, 102, 100.8]
returns = np.diff(prices) / prices[:-1]  # simple returns

# Option B: From log prices (preferred for longer horizons)
log_returns = np.diff(np.log(prices))

# Option C: From daily P&L
pnl = [10000, -5000, 15000, -8000]
position_value = 10_000_000
returns = np.array(pnl) / position_value
```

### Step 2: Calculate VaR and ES

```python
from var import quick_var

result = quick_var(
    returns,
    confidence=0.99,        # 99% confidence level
    horizon_days=1,         # 1-day holding period
    method="parametric",    # or "historical", "monte_carlo"
    position_value=10_000_000
)

print(f"VaR (99%, 1-day): {result['var_pct']:.4%}")
print(f"VaR (absolute):   ${result['var_abs']:,.0f}")
print(f"ES  (99%, 1-day): {result['es_pct']:.4%}")
print(f"ES  (absolute):   ${result['es_abs']:,.0f}")
```

### Step 3: Scale to Different Horizons

```python
# 1-day VaR
result_1d = quick_var(returns, confidence=0.99, horizon_days=1)

# 10-day VaR (Basel standard for market risk)
result_10d = quick_var(returns, confidence=0.99, horizon_days=10)

# Scaling formula: VaR_N = VaR_1 × √N
```

## Methods Available

### Parametric VaR (Variance-Covariance)

Assumes returns are normally distributed.

```python
from var import parametric_var, parametric_es

var_result = parametric_var(
    returns,
    confidence=0.99,
    horizon_days=1,
    distribution="normal",  # or "t" for fat tails
    df=5,                   # degrees of freedom for t-dist
    position_value=10_000_000
)

es_result = parametric_es(returns, confidence=0.99)
```

**Formula:** `VaR = -μ + σ × z_α`

**When to use:** Quick estimates, normal market conditions

### Historical VaR

Uses actual empirical distribution of returns.

```python
from var import historical_var, historical_es

var_result = historical_var(
    returns,
    confidence=0.99,
    horizon_days=1,
    position_value=10_000_000
)

es_result = historical_es(returns, confidence=0.99)
```

**When to use:** Fat-tailed distributions, no normality assumption needed

### Monte Carlo VaR

Simulates many paths and computes percentile.

```python
from var import monte_carlo_var

result = monte_carlo_var(
    mean_return=0.0003,      # daily mean
    volatility=0.012,        # daily volatility
    confidence=0.99,
    horizon_days=10,
    num_simulations=100_000,
    distribution="normal",   # or "t"
    position_value=10_000_000
)

print(f"VaR: ${result['var_abs']:,.0f}")
print(f"ES:  ${result['es_abs']:,.0f}")
```

**When to use:** Complex portfolios, options, path-dependent instruments

## Compare All Methods

```python
from var import compare_var_methods
import numpy as np

returns = np.random.normal(0.0003, 0.012, 504)

comparison = compare_var_methods(
    returns,
    confidence=0.99,
    horizon_days=10,
    position_value=10_000_000
)

print(f"{'Method':<15} {'VaR %':>10} {'ES %':>10}")
print("-" * 35)
for method, res in comparison["methods"].items():
    print(f"{method:<15} {res['var_pct']:>9.2%} {res['es_pct']:>9.2%}")
```

Output:
```
Method              VaR %       ES %
-----------------------------------
parametric          8.98%     10.31%
historical          8.02%      9.46%
monte_carlo         8.85%     10.22%
```

## Portfolio VaR

Calculate VaR with component and marginal decomposition.

```python
from var import portfolio_var
import numpy as np

# Returns matrix: rows=days, columns=assets
np.random.seed(42)
n_days = 252
n_assets = 3

# Correlated returns
cov = np.array([
    [0.04, 0.01, 0.005],
    [0.01, 0.02, 0.008],
    [0.005, 0.008, 0.015]
]) / 252

mean = np.array([0.10, 0.08, 0.06]) / 252
returns_matrix = np.random.multivariate_normal(mean, cov, n_days)

# Portfolio weights
weights = np.array([0.5, 0.3, 0.2])

result = portfolio_var(
    weights,
    returns_matrix,
    confidence=0.99,
    method="parametric",  # or "historical"
    position_value=10_000_000
)

print(f"Portfolio VaR: {result['portfolio_var_pct']:.2%} (${result['portfolio_var_abs']:,.0f})")
print(f"Portfolio ES:  {result['portfolio_es_pct']:.2%} (${result['portfolio_es_abs']:,.0f})")
print(f"\nComponent VaR breakdown:")
for i in range(n_assets):
    print(f"  Asset {i+1}: weight={weights[i]:.0%}, "
          f"standalone={result['standalone_var'][i]:.2%}, "
          f"component={result['component_var'][i]:.2%}, "
          f"contribution={result['pct_contribution'][i]:.1f}%")
print(f"\nDiversification benefit: {result['diversification_benefit']:.2%}")
```

Output:
```
Portfolio VaR: 1.94% ($194,118)
Portfolio ES:  2.22% ($221,510)

Component VaR breakdown:
  Asset 1: weight=50%, standalone=3.05%, component=1.35%, contribution=71.8%
  Asset 2: weight=30%, standalone=2.07%, component=0.38%, contribution=20.2%
  Asset 3: weight=20%, standalone=1.69%, component=0.15%, contribution=8.0%

Diversification benefit: 0.54%
```

## Backtesting

Test VaR model accuracy against realized returns.

```python
from var import backtest_var, parametric_var
import numpy as np

# Generate returns and rolling VaR estimates
np.random.seed(42)
returns = np.random.normal(0.0003, 0.012, 500)

window = 60
var_estimates = []
for i in range(window, len(returns)):
    hist_returns = returns[i-window:i]
    var_result = parametric_var(hist_returns, confidence=0.99)
    var_estimates.append(var_result["var_pct"])

realized_returns = returns[window:]

# Backtest
bt = backtest_var(realized_returns, var_estimates, confidence=0.99)

print(f"Observations:        {bt['n_observations']}")
print(f"Exceptions:          {bt['n_exceptions']}")
print(f"Exception rate:      {bt['exception_rate_pct']:.2f}%")
print(f"Expected exceptions: {bt['expected_exceptions']:.1f}")
print(f"Zone:                {bt['zone']}")
print(f"Plus factor:         {bt['plus_factor']:.2f}")
print(f"Kupiec p-value:      {bt['kupiec_p_value']:.4f}")
```

Output:
```
Observations:        440
Exceptions:          3
Exception rate:      0.68%
Expected exceptions: 4.4
Zone:                green
Plus factor:         0.00
Kupiec p-value:      0.4656
```

### Traffic Light Zones (Basel)

| Zone | Exceptions | Plus Factor | Action |
|------|------------|-------------|--------|
| Green | 0-4 | 0.00 | Model OK |
| Yellow | 5-9 | 0.40-0.85 | Review model |
| Red | 10+ | 1.00 | Model rejected |

## VaR Scaling

Scale VaR to different holding periods.

```python
from var import scale_var

var_1day = 100_000

# Square-root-of-time scaling (assumes i.i.d. returns)
var_10day = scale_var(var_1day, horizon_days=10, method="sqrt")
print(f"10-day VaR: ${var_10day:,.0f}")  # $316,228

# Linear scaling (conservative)
var_10day_linear = scale_var(var_1day, horizon_days=10, method="linear")
print(f"10-day VaR (linear): ${var_10day_linear:,.0f}")  # $1,000,000
```

## Key Formulas

### Parametric VaR
```
VaR_α = -μ + σ × z_α

where:
  μ = mean return
  σ = standard deviation
  z_α = inverse normal CDF at confidence α
```

### Expected Shortfall (CVaR)
```
ES_α = E[Loss | Loss > VaR_α]

For normal distribution:
  ES_α = μ + σ × φ(z_α) / (1-α)

where:
  φ = standard normal PDF
```

### Scaling
```
VaR_N = VaR_1 × √N  (square-root-of-time rule)
```

### Component VaR
```
Component VaR_i = w_i × Marginal VaR_i

Marginal VaR_i = (Σw)_i × z / σ_p
```

## Common Confidence Levels

| Confidence | Use Case | Z-score |
|------------|----------|---------|
| 95% | Internal risk limits | 1.645 |
| 99% | Basel market risk | 2.326 |
| 99.5% | Solvency II | 2.576 |
| 99.9% | IRC, extreme events | 3.090 |

## Function Reference

| Function | Description |
|----------|-------------|
| `quick_var(returns, confidence, horizon_days)` | One-liner for VaR + ES |
| `parametric_var(returns, confidence)` | Variance-covariance VaR |
| `parametric_es(returns, confidence)` | Parametric Expected Shortfall |
| `historical_var(returns, confidence)` | Non-parametric VaR |
| `historical_es(returns, confidence)` | Historical Expected Shortfall |
| `monte_carlo_var(mean, vol, confidence)` | Simulated VaR and ES |
| `portfolio_var(weights, returns_matrix)` | Portfolio VaR with decomposition |
| `backtest_var(returns, var_estimates)` | Backtesting with Kupiec test |
| `compare_var_methods(returns, confidence)` | Compare all methods |
| `scale_var(var_1day, horizon_days)` | Scale to N-day VaR |

## Tips

1. **Minimum observations**: Use at least 252 daily returns (1 year) for reliable estimates

2. **Fat tails**: If returns are fat-tailed, use:
   - Historical VaR (no distribution assumption)
   - Student's t distribution: `parametric_var(returns, distribution="t", df=5)`

3. **Horizon scaling**: Square-root scaling assumes i.i.d. returns; for autocorrelated returns, use actual multi-day returns

4. **ES vs VaR**: ES is more conservative and captures tail risk better; preferred by FRTB

5. **Backtesting**: Always backtest your VaR model; too few exceptions = model too conservative, too many = model inadequate
