#!/usr/bin/env python3
"""
VaR and CVaR (Expected Shortfall) Example

Demonstrates how to calculate VaR and ES using different methods.

Usage:
    cd rwa_calc
    ./venv/bin/python examples/var_example.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from var import (
    quick_var,
    parametric_var,
    parametric_es,
    historical_var,
    historical_es,
    monte_carlo_var,
    portfolio_var,
    backtest_var,
    compare_var_methods,
    scale_var,
)


# =============================================================================
# Configuration
# =============================================================================

POSITION_VALUE = 10_000_000  # $10M portfolio
CONFIDENCE = 0.99            # 99% confidence level
HORIZON_DAYS = 10            # 10-day holding period (Basel)
NUM_DAYS = 504               # 2 years of daily data


# =============================================================================
# Step 1: Generate Sample Returns
# =============================================================================

print("=" * 70)
print("VaR AND CVaR EXAMPLE")
print("=" * 70)

print("\n" + "-" * 70)
print("STEP 1: Prepare Returns Data")
print("-" * 70)

# Simulate daily returns (~20% annual volatility, ~8% annual return)
np.random.seed(42)
daily_vol = 0.20 / np.sqrt(252)   # ~1.26% daily
daily_mean = 0.08 / 252           # ~0.03% daily

returns = np.random.normal(daily_mean, daily_vol, NUM_DAYS)

print(f"""
  Data: {NUM_DAYS} daily returns (2 years)

  Statistics:
    Mean daily return:    {np.mean(returns)*100:>8.4f}%
    Daily volatility:     {np.std(returns)*100:>8.4f}%
    Annual volatility:    {np.std(returns)*np.sqrt(252)*100:>8.2f}%
    Min return:           {np.min(returns)*100:>8.4f}%
    Max return:           {np.max(returns)*100:>8.4f}%
""")


# =============================================================================
# Step 2: Quick VaR Calculation
# =============================================================================

print("-" * 70)
print("STEP 2: Quick VaR Calculation")
print("-" * 70)

result = quick_var(
    returns,
    confidence=CONFIDENCE,
    horizon_days=HORIZON_DAYS,
    method="parametric",
    position_value=POSITION_VALUE
)

print(f"""
  Configuration:
    Confidence level:     {CONFIDENCE:.0%}
    Holding period:       {HORIZON_DAYS} days
    Position value:       ${POSITION_VALUE:,.0f}

  Results:
    VaR ({CONFIDENCE:.0%}, {HORIZON_DAYS}-day):    {result['var_pct']:.4%}  (${result['var_abs']:,.0f})
    ES  ({CONFIDENCE:.0%}, {HORIZON_DAYS}-day):    {result['es_pct']:.4%}  (${result['es_abs']:,.0f})
""")


# =============================================================================
# Step 3: Compare All Methods
# =============================================================================

print("-" * 70)
print("STEP 3: Compare VaR Methods")
print("-" * 70)

comparison = compare_var_methods(
    returns,
    confidence=CONFIDENCE,
    horizon_days=HORIZON_DAYS,
    position_value=POSITION_VALUE
)

print(f"""
  {'Method':<15} {'VaR %':>10} {'VaR $':>14} {'ES %':>10} {'ES $':>14}
  {'-'*65}""")

for method, res in comparison["methods"].items():
    var_abs = res.get('var_abs') or 0
    es_abs = res.get('es_abs') or 0
    print(f"  {method:<15} {res['var_pct']*100:>9.4f}% ${var_abs:>12,.0f} "
          f"{res['es_pct']*100:>9.4f}% ${es_abs:>12,.0f}")

print(f"""
  VaR range: {comparison['var_range'][0]*100:.2f}% - {comparison['var_range'][1]*100:.2f}%
  ES range:  {comparison['es_range'][0]*100:.2f}% - {comparison['es_range'][1]*100:.2f}%
""")


# =============================================================================
# Step 4: Different Confidence Levels
# =============================================================================

print("-" * 70)
print("STEP 4: VaR at Different Confidence Levels")
print("-" * 70)

print(f"\n  {'Confidence':<12} {'VaR (1-day)':>12} {'VaR (10-day)':>14} {'ES (1-day)':>12}")
print(f"  {'-'*55}")

for conf in [0.90, 0.95, 0.99, 0.999]:
    var_1d = parametric_var(returns, confidence=conf, horizon_days=1)
    var_10d = parametric_var(returns, confidence=conf, horizon_days=10)
    es_1d = parametric_es(returns, confidence=conf, horizon_days=1)

    print(f"  {conf:>10.1%}   {var_1d['var_pct']*100:>11.4f}%  {var_10d['var_pct']*100:>13.4f}%  "
          f"{es_1d['es_pct']*100:>11.4f}%")


# =============================================================================
# Step 5: Portfolio VaR
# =============================================================================

print("\n" + "-" * 70)
print("STEP 5: Portfolio VaR with Decomposition")
print("-" * 70)

# Generate correlated returns for 4 assets
n_assets = 4
asset_names = ["Equities", "Bonds", "Commodities", "FX"]

# Correlation matrix
corr = np.array([
    [1.00, 0.30, 0.20, 0.10],
    [0.30, 1.00, 0.15, 0.05],
    [0.20, 0.15, 1.00, 0.25],
    [0.10, 0.05, 0.25, 1.00]
])

# Volatilities (annual)
vols = np.array([0.20, 0.05, 0.25, 0.10])
daily_vols = vols / np.sqrt(252)

# Covariance matrix
cov = np.outer(daily_vols, daily_vols) * corr

# Expected returns (annual)
expected_returns = np.array([0.08, 0.04, 0.06, 0.03])
daily_returns = expected_returns / 252

# Simulate returns
returns_matrix = np.random.multivariate_normal(daily_returns, cov, NUM_DAYS)

# Portfolio weights
weights = np.array([0.40, 0.30, 0.20, 0.10])

port = portfolio_var(
    weights,
    returns_matrix,
    confidence=CONFIDENCE,
    method="parametric",
    position_value=POSITION_VALUE
)

print(f"""
  Portfolio Allocation:
    {'Asset':<15} {'Weight':>8} {'Ann. Vol':>10}
    {'-'*35}""")
for i, name in enumerate(asset_names):
    print(f"    {name:<15} {weights[i]:>7.0%} {vols[i]:>9.0%}")

print(f"""
  Portfolio Risk:
    Portfolio VaR:        {port['portfolio_var_pct']:.4%}  (${port['portfolio_var_abs']:,.0f})
    Portfolio ES:         {port['portfolio_es_pct']:.4%}  (${port['portfolio_es_abs']:,.0f})
    Portfolio Volatility: {port['portfolio_volatility']*np.sqrt(252):.2%} (annualized)

  Component VaR Breakdown:
    {'Asset':<15} {'Weight':>8} {'Standalone':>12} {'Component':>12} {'Contrib':>10}
    {'-'*60}""")

for i, name in enumerate(asset_names):
    print(f"    {name:<15} {weights[i]:>7.0%} {port['standalone_var'][i]*100:>11.4f}% "
          f"{port['component_var'][i]*100:>11.4f}% {port['pct_contribution'][i]:>9.1f}%")

print(f"""    {'-'*60}
    Diversification benefit: {port['diversification_benefit']*100:.4f}%
""")


# =============================================================================
# Step 6: VaR Scaling
# =============================================================================

print("-" * 70)
print("STEP 6: VaR Scaling (1-day to N-day)")
print("-" * 70)

var_1day = parametric_var(returns, confidence=0.99, horizon_days=1, position_value=POSITION_VALUE)
var_1day_value = var_1day['var_abs']

print(f"\n  1-day VaR (99%): ${var_1day_value:,.0f}")
print(f"\n  {'Horizon':<12} {'Sqrt Scaling':>14} {'Linear Scaling':>16}")
print(f"  {'-'*45}")

for days in [1, 5, 10, 20, 60, 252]:
    sqrt_scaled = scale_var(var_1day_value, days, method="sqrt")
    linear_scaled = scale_var(var_1day_value, days, method="linear")
    print(f"  {days:>3} days      ${sqrt_scaled:>12,.0f}   ${linear_scaled:>14,.0f}")


# =============================================================================
# Step 7: Backtesting
# =============================================================================

print("\n" + "-" * 70)
print("STEP 7: VaR Backtesting")
print("-" * 70)

# Generate rolling VaR estimates
window = 60
var_estimates = []

for i in range(window, len(returns)):
    hist_returns = returns[i-window:i]
    var_result = parametric_var(hist_returns, confidence=0.99)
    var_estimates.append(var_result["var_pct"])

realized_returns = returns[window:]

# Backtest
bt = backtest_var(realized_returns, var_estimates, confidence=0.99)

print(f"""
  Backtest Configuration:
    Rolling window:       {window} days
    Confidence level:     99%
    Test period:          {bt['n_observations']} days

  Results:
    Exceptions:           {bt['n_exceptions']}
    Exception rate:       {bt['exception_rate_pct']:.2f}%
    Expected exceptions:  {bt['expected_exceptions']:.1f}

  Basel Traffic Light:
    Zone:                 {bt['zone'].upper()}
    Plus factor:          {bt['plus_factor']:.2f}

  Statistical Test:
    Kupiec LR statistic:  {bt['kupiec_lr_statistic']:.4f}
    Kupiec p-value:       {bt['kupiec_p_value']:.4f}

  Interpretation:
    {"Model is adequate (p-value > 0.05)" if bt['kupiec_p_value'] > 0.05 else "Model may need review (p-value <= 0.05)"}
""")


# =============================================================================
# Step 8: Fat Tails (Student's t Distribution)
# =============================================================================

print("-" * 70)
print("STEP 8: Fat Tails (Student's t vs Normal)")
print("-" * 70)

# Generate fat-tailed returns
np.random.seed(123)
t_returns = np.random.standard_t(df=4, size=NUM_DAYS) * daily_vol + daily_mean

print(f"""
  Comparing Normal vs Student's t distribution:

  {'Distribution':<15} {'VaR (99%)':>12} {'ES (99%)':>12} {'Kurtosis':>10}
  {'-'*55}""")

# Normal assumption
var_normal = parametric_var(t_returns, confidence=0.99, distribution="normal")
es_normal = parametric_es(t_returns, confidence=0.99, distribution="normal")

# t-distribution (better for fat tails)
var_t = parametric_var(t_returns, confidence=0.99, distribution="t", df=4)
es_t = parametric_es(t_returns, confidence=0.99, distribution="t", df=4)

# Historical (no distribution assumption)
var_hist = historical_var(t_returns, confidence=0.99)
es_hist = historical_es(t_returns, confidence=0.99)

from scipy.stats import kurtosis
kurt = kurtosis(t_returns)

print(f"  {'Normal':<15} {var_normal['var_pct']*100:>11.4f}% {es_normal['es_pct']*100:>11.4f}%")
print(f"  {'Student t(4)':<15} {var_t['var_pct']*100:>11.4f}% {es_t['es_pct']*100:>11.4f}%")
print(f"  {'Historical':<15} {var_hist['var_pct']*100:>11.4f}% {es_hist['es_pct']*100:>11.4f}% {kurt:>9.2f}")

print(f"""
  Note: Excess kurtosis = {kurt:.2f} (normal = 0, t(4) = 6)
        Use t-distribution or historical VaR for fat-tailed returns.
""")


# =============================================================================
# Summary
# =============================================================================

print("=" * 70)
print("SUMMARY")
print("=" * 70)

print("""
  VaR Methods Available:
    - parametric_var()     Variance-covariance (normal or t)
    - historical_var()     Non-parametric (empirical distribution)
    - monte_carlo_var()    Simulation-based
    - portfolio_var()      Multi-asset with decomposition

  ES Methods Available:
    - parametric_es()      Analytical ES for normal/t
    - historical_es()      Average of tail losses

  Utilities:
    - quick_var()          One-liner for VaR + ES
    - compare_var_methods() Compare all methods
    - backtest_var()       Basel traffic light + Kupiec test
    - scale_var()          Scale to different horizons
""")

print("=" * 70)
print("END OF EXAMPLE")
print("=" * 70)
