"""
VaR and CVaR (Expected Shortfall) Module

Implements Value at Risk and Conditional Value at Risk calculations:
- Parametric VaR (variance-covariance)
- Historical VaR
- Monte Carlo VaR
- Expected Shortfall (CVaR) for all methods
- Component VaR / Marginal VaR
- VaR scaling (1-day to N-day)
- Backtesting framework

Usage:
    from var import parametric_var, historical_var, monte_carlo_var, expected_shortfall

    # From returns
    var_99 = parametric_var(returns, confidence=0.99)
    es_99 = expected_shortfall(returns, confidence=0.99)

    # From portfolio
    result = portfolio_var(weights, returns_matrix, confidence=0.99)
"""

import math
from dataclasses import dataclass
from typing import Union, Optional
from enum import Enum

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from scipy import stats
    from scipy.stats import norm, t as t_dist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# =============================================================================
# Configuration
# =============================================================================

class VaRMethod(Enum):
    """VaR calculation methods."""
    PARAMETRIC = "parametric"
    HISTORICAL = "historical"
    MONTE_CARLO = "monte_carlo"


@dataclass
class VaRConfig:
    """Configuration for VaR calculations."""
    confidence: float = 0.99          # Confidence level (0.95, 0.99, 0.999)
    horizon_days: int = 1             # Holding period in days
    scaling_method: str = "sqrt"      # "sqrt" or "linear"
    distribution: str = "normal"      # "normal" or "t" (Student's t)
    df: int = 5                       # Degrees of freedom for t-distribution
    num_simulations: int = 10_000     # For Monte Carlo
    seed: int = 42                    # Random seed


# =============================================================================
# Helper Functions
# =============================================================================

def _check_numpy():
    if not HAS_NUMPY:
        raise ImportError("NumPy required for VaR calculations: pip install numpy")


def _check_scipy():
    if not HAS_SCIPY:
        raise ImportError("SciPy required for VaR calculations: pip install scipy")


def _to_array(data) -> "np.ndarray":
    """Convert input to numpy array."""
    _check_numpy()
    if isinstance(data, np.ndarray):
        return data
    return np.array(data)


def scale_var(var_1day: float, horizon_days: int, method: str = "sqrt") -> float:
    """
    Scale 1-day VaR to N-day VaR.

    Parameters
    ----------
    var_1day : float
        1-day VaR.
    horizon_days : int
        Target holding period in days.
    method : str
        "sqrt" for square-root-of-time (assumes i.i.d. returns)
        "linear" for linear scaling (conservative)

    Returns
    -------
    float
        N-day VaR.
    """
    if method == "sqrt":
        return var_1day * math.sqrt(horizon_days)
    elif method == "linear":
        return var_1day * horizon_days
    else:
        raise ValueError(f"Unknown scaling method: {method}")


def get_z_score(confidence: float, distribution: str = "normal", df: int = 5) -> float:
    """
    Get z-score (or t-score) for a given confidence level.

    Parameters
    ----------
    confidence : float
        Confidence level (e.g., 0.99).
    distribution : str
        "normal" or "t".
    df : int
        Degrees of freedom for t-distribution.

    Returns
    -------
    float
        Critical value.
    """
    _check_scipy()
    if distribution == "normal":
        return norm.ppf(confidence)
    elif distribution == "t":
        return t_dist.ppf(confidence, df)
    else:
        raise ValueError(f"Unknown distribution: {distribution}")


# =============================================================================
# Parametric VaR (Variance-Covariance)
# =============================================================================

def parametric_var(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    distribution: str = "normal",
    df: int = 5,
    position_value: float = None,
) -> dict:
    """
    Calculate parametric (variance-covariance) VaR.

    Assumes returns are normally distributed (or t-distributed).
    VaR = -μ + σ × z_α

    Parameters
    ----------
    returns : array-like
        Historical returns (as decimals, e.g., 0.01 for 1%).
    confidence : float
        Confidence level (0.95, 0.99, 0.999).
    horizon_days : int
        Holding period in days.
    distribution : str
        "normal" or "t" for Student's t.
    df : int
        Degrees of freedom for t-distribution.
    position_value : float, optional
        Position value to convert to absolute VaR.

    Returns
    -------
    dict
        VaR results including var_pct, var_abs, volatility, etc.
    """
    _check_numpy()
    _check_scipy()

    returns = _to_array(returns)
    returns = returns[~np.isnan(returns)]  # Remove NaN

    if len(returns) < 2:
        raise ValueError("Need at least 2 returns for VaR calculation")

    # Calculate statistics
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    # Get critical value
    z = get_z_score(confidence, distribution, df)

    # 1-day VaR (as positive number representing potential loss)
    var_1day_pct = -mean_return + z * std_return

    # Scale to horizon
    var_pct = scale_var(var_1day_pct, horizon_days, "sqrt")

    # Absolute VaR
    var_abs = var_pct * position_value if position_value else None

    return {
        "method": "parametric",
        "confidence": confidence,
        "horizon_days": horizon_days,
        "distribution": distribution,
        "var_pct": var_pct,
        "var_1day_pct": var_1day_pct,
        "var_abs": var_abs,
        "mean_return": mean_return,
        "volatility": std_return,
        "annualized_volatility": std_return * math.sqrt(252),
        "z_score": z,
        "num_observations": len(returns),
    }


def parametric_es(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    distribution: str = "normal",
    df: int = 5,
    position_value: float = None,
) -> dict:
    """
    Calculate parametric Expected Shortfall (CVaR).

    For normal distribution: ES = μ + σ × φ(z) / (1 - α)
    where φ is the PDF and z = Φ^{-1}(α)

    Parameters
    ----------
    returns : array-like
        Historical returns.
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    distribution : str
        "normal" or "t".
    df : int
        Degrees of freedom for t.
    position_value : float, optional
        Position value.

    Returns
    -------
    dict
        ES results.
    """
    _check_numpy()
    _check_scipy()

    returns = _to_array(returns)
    returns = returns[~np.isnan(returns)]

    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1)

    alpha = 1 - confidence  # tail probability

    if distribution == "normal":
        z = norm.ppf(confidence)
        # ES for normal: E[X | X > VaR] = μ + σ × φ(z) / α
        es_1day_pct = -mean_return + std_return * norm.pdf(z) / alpha
    elif distribution == "t":
        z = t_dist.ppf(confidence, df)
        # ES for t-distribution
        es_1day_pct = -mean_return + std_return * (
            t_dist.pdf(z, df) * (df + z**2) / ((df - 1) * alpha)
        )
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    es_pct = scale_var(es_1day_pct, horizon_days, "sqrt")
    es_abs = es_pct * position_value if position_value else None

    return {
        "method": "parametric",
        "confidence": confidence,
        "horizon_days": horizon_days,
        "distribution": distribution,
        "es_pct": es_pct,
        "es_1day_pct": es_1day_pct,
        "es_abs": es_abs,
        "mean_return": mean_return,
        "volatility": std_return,
        "num_observations": len(returns),
    }


# =============================================================================
# Historical VaR
# =============================================================================

def historical_var(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    position_value: float = None,
) -> dict:
    """
    Calculate historical (non-parametric) VaR.

    Uses the empirical distribution of returns.

    Parameters
    ----------
    returns : array-like
        Historical returns.
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period (scaled using sqrt if > 1).
    position_value : float, optional
        Position value.

    Returns
    -------
    dict
        Historical VaR results.
    """
    _check_numpy()

    returns = _to_array(returns)
    returns = returns[~np.isnan(returns)]

    if len(returns) < 10:
        raise ValueError("Need at least 10 returns for historical VaR")

    # Sort returns (losses are negative returns)
    sorted_returns = np.sort(returns)

    # Find the percentile (VaR is the loss at the confidence level)
    var_index = int((1 - confidence) * len(sorted_returns))
    var_1day_pct = -sorted_returns[var_index]

    # Scale to horizon
    var_pct = scale_var(var_1day_pct, horizon_days, "sqrt")
    var_abs = var_pct * position_value if position_value else None

    # Additional percentiles
    percentiles = {}
    for p in [0.90, 0.95, 0.99, 0.999]:
        idx = int((1 - p) * len(sorted_returns))
        percentiles[f"var_{int(p*100)}"] = -sorted_returns[idx]

    return {
        "method": "historical",
        "confidence": confidence,
        "horizon_days": horizon_days,
        "var_pct": var_pct,
        "var_1day_pct": var_1day_pct,
        "var_abs": var_abs,
        "mean_return": float(np.mean(returns)),
        "volatility": float(np.std(returns, ddof=1)),
        "min_return": float(np.min(returns)),
        "max_return": float(np.max(returns)),
        "percentiles": percentiles,
        "num_observations": len(returns),
    }


def historical_es(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    position_value: float = None,
) -> dict:
    """
    Calculate historical Expected Shortfall (CVaR).

    ES = average of returns beyond the VaR threshold.

    Parameters
    ----------
    returns : array-like
        Historical returns.
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    position_value : float, optional
        Position value.

    Returns
    -------
    dict
        Historical ES results.
    """
    _check_numpy()

    returns = _to_array(returns)
    returns = returns[~np.isnan(returns)]

    sorted_returns = np.sort(returns)
    var_index = int((1 - confidence) * len(sorted_returns))

    # VaR threshold
    var_threshold = sorted_returns[var_index]

    # ES is the average of returns worse than VaR
    tail_returns = sorted_returns[:var_index + 1]
    es_1day_pct = -np.mean(tail_returns)

    es_pct = scale_var(es_1day_pct, horizon_days, "sqrt")
    es_abs = es_pct * position_value if position_value else None

    return {
        "method": "historical",
        "confidence": confidence,
        "horizon_days": horizon_days,
        "es_pct": es_pct,
        "es_1day_pct": es_1day_pct,
        "es_abs": es_abs,
        "var_pct": -var_threshold,
        "tail_observations": len(tail_returns),
        "num_observations": len(returns),
    }


# =============================================================================
# Monte Carlo VaR
# =============================================================================

def monte_carlo_var(
    mean_return: float,
    volatility: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
    num_simulations: int = 10_000,
    distribution: str = "normal",
    df: int = 5,
    position_value: float = None,
    seed: int = 42,
) -> dict:
    """
    Calculate Monte Carlo VaR.

    Simulates returns and computes VaR from the simulated distribution.

    Parameters
    ----------
    mean_return : float
        Expected daily return.
    volatility : float
        Daily volatility (standard deviation).
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    num_simulations : int
        Number of Monte Carlo paths.
    distribution : str
        "normal" or "t".
    df : int
        Degrees of freedom for t.
    position_value : float, optional
        Position value.
    seed : int
        Random seed.

    Returns
    -------
    dict
        Monte Carlo VaR results.
    """
    _check_numpy()

    rng = np.random.default_rng(seed)

    # Simulate returns over the horizon
    if distribution == "normal":
        simulated_returns = rng.normal(
            mean_return * horizon_days,
            volatility * math.sqrt(horizon_days),
            num_simulations
        )
    elif distribution == "t":
        _check_scipy()
        # Scale t-distribution to have correct variance
        simulated_returns = (
            mean_return * horizon_days +
            volatility * math.sqrt(horizon_days) *
            rng.standard_t(df, num_simulations) * math.sqrt((df - 2) / df)
        )
    else:
        raise ValueError(f"Unknown distribution: {distribution}")

    # Sort and find VaR
    sorted_returns = np.sort(simulated_returns)
    var_index = int((1 - confidence) * num_simulations)
    var_pct = -sorted_returns[var_index]

    # ES
    tail_returns = sorted_returns[:var_index + 1]
    es_pct = -np.mean(tail_returns)

    var_abs = var_pct * position_value if position_value else None
    es_abs = es_pct * position_value if position_value else None

    return {
        "method": "monte_carlo",
        "confidence": confidence,
        "horizon_days": horizon_days,
        "distribution": distribution,
        "var_pct": var_pct,
        "var_abs": var_abs,
        "es_pct": es_pct,
        "es_abs": es_abs,
        "mean_return": mean_return,
        "volatility": volatility,
        "num_simulations": num_simulations,
        "simulated_mean": float(np.mean(simulated_returns)),
        "simulated_std": float(np.std(simulated_returns)),
    }


# =============================================================================
# Portfolio VaR
# =============================================================================

def portfolio_var(
    weights: Union[list, "np.ndarray"],
    returns_matrix: "np.ndarray",
    confidence: float = 0.99,
    horizon_days: int = 1,
    method: str = "parametric",
    position_value: float = None,
) -> dict:
    """
    Calculate portfolio VaR with component and marginal VaR.

    Parameters
    ----------
    weights : array-like
        Portfolio weights (should sum to 1).
    returns_matrix : np.ndarray
        Matrix of asset returns (n_observations x n_assets).
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    method : str
        "parametric" or "historical".
    position_value : float, optional
        Total portfolio value.

    Returns
    -------
    dict
        Portfolio VaR with component breakdown.
    """
    _check_numpy()
    _check_scipy()

    weights = _to_array(weights)
    returns_matrix = _to_array(returns_matrix)

    n_assets = len(weights)
    if returns_matrix.shape[1] != n_assets:
        raise ValueError(f"Returns matrix has {returns_matrix.shape[1]} assets, but {n_assets} weights provided")

    # Portfolio returns
    portfolio_returns = returns_matrix @ weights

    # Calculate portfolio VaR
    if method == "parametric":
        var_result = parametric_var(portfolio_returns, confidence, horizon_days, position_value=position_value)
        es_result = parametric_es(portfolio_returns, confidence, horizon_days, position_value=position_value)
    else:
        var_result = historical_var(portfolio_returns, confidence, horizon_days, position_value=position_value)
        es_result = historical_es(portfolio_returns, confidence, horizon_days, position_value=position_value)

    # Covariance matrix
    cov_matrix = np.cov(returns_matrix, rowvar=False)

    # Portfolio variance
    portfolio_variance = weights @ cov_matrix @ weights
    portfolio_std = math.sqrt(portfolio_variance)

    # Marginal VaR: ∂VaR/∂w_i = (Σw)_i × z / σ_p × VaR
    z = get_z_score(confidence)
    marginal_var = (cov_matrix @ weights) * z / portfolio_std

    # Component VaR: w_i × Marginal VaR_i
    component_var = weights * marginal_var

    # Percentage contribution
    total_component = np.sum(component_var)
    pct_contribution = component_var / total_component * 100 if total_component > 0 else np.zeros(n_assets)

    # Individual asset VaRs (standalone)
    standalone_var = []
    for i in range(n_assets):
        asset_returns = returns_matrix[:, i]
        if method == "parametric":
            av = parametric_var(asset_returns, confidence, horizon_days)
        else:
            av = historical_var(asset_returns, confidence, horizon_days)
        standalone_var.append(av["var_pct"])

    return {
        "method": method,
        "confidence": confidence,
        "horizon_days": horizon_days,
        "portfolio_var_pct": var_result["var_pct"],
        "portfolio_var_abs": var_result["var_abs"],
        "portfolio_es_pct": es_result["es_pct"],
        "portfolio_es_abs": es_result["es_abs"],
        "portfolio_volatility": portfolio_std,
        "marginal_var": marginal_var.tolist(),
        "component_var": component_var.tolist(),
        "pct_contribution": pct_contribution.tolist(),
        "standalone_var": standalone_var,
        "diversification_benefit": sum(w * sv for w, sv in zip(weights, standalone_var)) - var_result["var_pct"],
        "weights": weights.tolist(),
        "n_assets": n_assets,
        "n_observations": len(portfolio_returns),
    }


# =============================================================================
# Backtesting
# =============================================================================

class BacktestZone(Enum):
    """Basel traffic light zones."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


# Plus factor by number of exceptions (Basel)
BACKTESTING_PLUS_FACTORS = {
    0: 0.00, 1: 0.00, 2: 0.00, 3: 0.00, 4: 0.00,  # Green
    5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85,  # Yellow
}


def backtest_var(
    returns: Union[list, "np.ndarray"],
    var_estimates: Union[list, "np.ndarray"],
    confidence: float = 0.99,
) -> dict:
    """
    Backtest VaR estimates against realized returns.

    Parameters
    ----------
    returns : array-like
        Realized returns (same length as var_estimates).
    var_estimates : array-like
        VaR estimates for each period (positive numbers).
    confidence : float
        Confidence level used for VaR.

    Returns
    -------
    dict
        Backtesting results including exceptions, zone, and plus factor.
    """
    _check_numpy()
    _check_scipy()

    returns = _to_array(returns)
    var_estimates = _to_array(var_estimates)

    if len(returns) != len(var_estimates):
        raise ValueError("Returns and VaR estimates must have same length")

    n_obs = len(returns)

    # Count exceptions (losses exceeding VaR)
    exceptions = returns < -var_estimates
    n_exceptions = int(np.sum(exceptions))
    exception_rate = n_exceptions / n_obs

    # Expected exceptions
    expected_exceptions = (1 - confidence) * n_obs

    # Traffic light zone
    if n_exceptions <= 4:
        zone = BacktestZone.GREEN
    elif n_exceptions <= 9:
        zone = BacktestZone.YELLOW
    else:
        zone = BacktestZone.RED

    # Plus factor
    plus_factor = BACKTESTING_PLUS_FACTORS.get(n_exceptions, 1.0)

    # Kupiec POF test (proportion of failures)
    if n_exceptions > 0 and n_exceptions < n_obs:
        alpha = 1 - confidence
        lr_pof = 2 * (
            n_exceptions * math.log(exception_rate / alpha) +
            (n_obs - n_exceptions) * math.log((1 - exception_rate) / (1 - alpha))
        )
        p_value_pof = 1 - stats.chi2.cdf(lr_pof, 1)
    else:
        lr_pof = None
        p_value_pof = None

    # Exception dates/indices
    exception_indices = np.where(exceptions)[0].tolist()

    return {
        "n_observations": n_obs,
        "n_exceptions": n_exceptions,
        "exception_rate_pct": exception_rate * 100,
        "expected_exceptions": expected_exceptions,
        "zone": zone.value,
        "plus_factor": plus_factor,
        "kupiec_lr_statistic": lr_pof,
        "kupiec_p_value": p_value_pof,
        "exception_indices": exception_indices,
        "confidence": confidence,
    }


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_var(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    method: str = "parametric",
    position_value: float = None,
) -> dict:
    """
    Quick VaR and ES calculation.

    Parameters
    ----------
    returns : array-like
        Historical returns.
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    method : str
        "parametric", "historical", or "monte_carlo".
    position_value : float, optional
        Position value for absolute VaR.

    Returns
    -------
    dict
        Combined VaR and ES results.
    """
    _check_numpy()

    returns = _to_array(returns)

    if method == "parametric":
        var_result = parametric_var(returns, confidence, horizon_days, position_value=position_value)
        es_result = parametric_es(returns, confidence, horizon_days, position_value=position_value)
    elif method == "historical":
        var_result = historical_var(returns, confidence, horizon_days, position_value=position_value)
        es_result = historical_es(returns, confidence, horizon_days, position_value=position_value)
    elif method == "monte_carlo":
        mean_return = float(np.mean(returns))
        volatility = float(np.std(returns, ddof=1))
        result = monte_carlo_var(mean_return, volatility, confidence, horizon_days, position_value=position_value)
        return result
    else:
        raise ValueError(f"Unknown method: {method}")

    return {
        "method": method,
        "confidence": confidence,
        "horizon_days": horizon_days,
        "var_pct": var_result["var_pct"],
        "var_abs": var_result.get("var_abs"),
        "es_pct": es_result["es_pct"],
        "es_abs": es_result.get("es_abs"),
        "volatility": var_result["volatility"],
        "annualized_volatility": var_result["volatility"] * math.sqrt(252),
        "mean_return": var_result["mean_return"],
        "num_observations": var_result["num_observations"],
    }


def compare_var_methods(
    returns: Union[list, "np.ndarray"],
    confidence: float = 0.99,
    horizon_days: int = 1,
    position_value: float = None,
) -> dict:
    """
    Compare VaR across all methods.

    Parameters
    ----------
    returns : array-like
        Historical returns.
    confidence : float
        Confidence level.
    horizon_days : int
        Holding period.
    position_value : float, optional
        Position value.

    Returns
    -------
    dict
        Comparison of all methods.
    """
    returns = _to_array(returns)

    results = {}
    for method in ["parametric", "historical", "monte_carlo"]:
        results[method] = quick_var(returns, confidence, horizon_days, method, position_value)

    # Summary
    var_values = {m: r["var_pct"] for m, r in results.items()}
    es_values = {m: r["es_pct"] for m, r in results.items()}

    return {
        "confidence": confidence,
        "horizon_days": horizon_days,
        "position_value": position_value,
        "methods": results,
        "var_comparison": var_values,
        "es_comparison": es_values,
        "var_range": (min(var_values.values()), max(var_values.values())),
        "es_range": (min(es_values.values()), max(es_values.values())),
    }


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("VaR and CVaR (Expected Shortfall) Module Demo")
    print("=" * 70)

    # Generate sample returns (daily, ~20% annual volatility)
    np.random.seed(42)
    n_days = 252 * 2  # 2 years
    daily_vol = 0.20 / math.sqrt(252)  # ~1.26%
    daily_mean = 0.08 / 252  # ~8% annual return
    returns = np.random.normal(daily_mean, daily_vol, n_days)

    print(f"\nSample data: {n_days} daily returns")
    print(f"  Mean daily return:  {np.mean(returns)*100:.4f}%")
    print(f"  Daily volatility:   {np.std(returns)*100:.4f}%")
    print(f"  Annual volatility:  {np.std(returns)*math.sqrt(252)*100:.2f}%")

    # === Parametric VaR ===
    print("\n" + "-" * 70)
    print("PARAMETRIC VaR (99%, 1-day)")
    print("-" * 70)
    result = parametric_var(returns, confidence=0.99, position_value=10_000_000)
    print(f"  VaR (% of portfolio):  {result['var_pct']*100:.4f}%")
    print(f"  VaR (absolute):        ${result['var_abs']:,.0f}")
    print(f"  Z-score:               {result['z_score']:.4f}")

    # === Parametric ES ===
    print("\n" + "-" * 70)
    print("PARAMETRIC ES (99%, 1-day)")
    print("-" * 70)
    result = parametric_es(returns, confidence=0.99, position_value=10_000_000)
    print(f"  ES (% of portfolio):   {result['es_pct']*100:.4f}%")
    print(f"  ES (absolute):         ${result['es_abs']:,.0f}")

    # === Historical VaR ===
    print("\n" + "-" * 70)
    print("HISTORICAL VaR (99%, 1-day)")
    print("-" * 70)
    result = historical_var(returns, confidence=0.99, position_value=10_000_000)
    print(f"  VaR (% of portfolio):  {result['var_pct']*100:.4f}%")
    print(f"  VaR (absolute):        ${result['var_abs']:,.0f}")
    print(f"  Worst return:          {result['min_return']*100:.4f}%")

    # === Historical ES ===
    print("\n" + "-" * 70)
    print("HISTORICAL ES (99%, 1-day)")
    print("-" * 70)
    result = historical_es(returns, confidence=0.99, position_value=10_000_000)
    print(f"  ES (% of portfolio):   {result['es_pct']*100:.4f}%")
    print(f"  ES (absolute):         ${result['es_abs']:,.0f}")
    print(f"  Tail observations:     {result['tail_observations']}")

    # === Monte Carlo VaR ===
    print("\n" + "-" * 70)
    print("MONTE CARLO VaR (99%, 1-day, 100k simulations)")
    print("-" * 70)
    result = monte_carlo_var(
        mean_return=np.mean(returns),
        volatility=np.std(returns),
        confidence=0.99,
        num_simulations=100_000,
        position_value=10_000_000,
    )
    print(f"  VaR (% of portfolio):  {result['var_pct']*100:.4f}%")
    print(f"  VaR (absolute):        ${result['var_abs']:,.0f}")
    print(f"  ES (% of portfolio):   {result['es_pct']*100:.4f}%")
    print(f"  ES (absolute):         ${result['es_abs']:,.0f}")

    # === Method Comparison ===
    print("\n" + "-" * 70)
    print("METHOD COMPARISON (99%, 10-day)")
    print("-" * 70)
    comparison = compare_var_methods(returns, confidence=0.99, horizon_days=10, position_value=10_000_000)
    print(f"\n  {'Method':<15} {'VaR %':>10} {'VaR $':>14} {'ES %':>10} {'ES $':>14}")
    print("  " + "-" * 65)
    for method, res in comparison["methods"].items():
        var_abs = res.get('var_abs') or 0
        es_abs = res.get('es_abs') or 0
        print(f"  {method:<15} {res['var_pct']*100:>9.4f}% ${var_abs:>12,.0f} {res['es_pct']*100:>9.4f}% ${es_abs:>12,.0f}")

    # === Portfolio VaR ===
    print("\n" + "-" * 70)
    print("PORTFOLIO VaR (3 assets, 99%, 1-day)")
    print("-" * 70)

    # Generate correlated returns for 3 assets
    n_assets = 3
    cov = np.array([
        [0.04, 0.01, 0.005],
        [0.01, 0.02, 0.008],
        [0.005, 0.008, 0.015]
    ]) / 252  # Daily covariance

    mean = np.array([0.10, 0.08, 0.06]) / 252  # Daily means
    returns_matrix = np.random.multivariate_normal(mean, cov, n_days)

    weights = np.array([0.5, 0.3, 0.2])
    port_result = portfolio_var(weights, returns_matrix, confidence=0.99, position_value=10_000_000)

    print(f"\n  Portfolio weights: {weights.tolist()}")
    print(f"  Portfolio VaR:     {port_result['portfolio_var_pct']*100:.4f}%  (${port_result['portfolio_var_abs']:,.0f})")
    print(f"  Portfolio ES:      {port_result['portfolio_es_pct']*100:.4f}%  (${port_result['portfolio_es_abs']:,.0f})")
    print(f"\n  Component VaR breakdown:")
    print(f"  {'Asset':<10} {'Weight':>8} {'Standalone':>12} {'Component':>12} {'Contrib %':>10}")
    print("  " + "-" * 55)
    for i in range(n_assets):
        print(f"  Asset_{i+1:<5} {weights[i]:>7.1%} {port_result['standalone_var'][i]*100:>11.4f}% "
              f"{port_result['component_var'][i]*100:>11.4f}% {port_result['pct_contribution'][i]:>9.1f}%")
    print("  " + "-" * 55)
    print(f"  Diversification benefit: {port_result['diversification_benefit']*100:.4f}%")

    # === Backtesting ===
    print("\n" + "-" * 70)
    print("VAR BACKTESTING (250 days)")
    print("-" * 70)

    # Generate VaR estimates (using rolling window)
    window = 60
    var_estimates = []
    for i in range(window, n_days):
        hist_returns = returns[i-window:i]
        var_result = parametric_var(hist_returns, confidence=0.99)
        var_estimates.append(var_result["var_pct"])

    realized_returns = returns[window:]
    bt_result = backtest_var(realized_returns, var_estimates, confidence=0.99)

    print(f"\n  Observations:        {bt_result['n_observations']}")
    print(f"  Exceptions:          {bt_result['n_exceptions']}")
    print(f"  Exception rate:      {bt_result['exception_rate_pct']:.2f}%")
    print(f"  Expected exceptions: {bt_result['expected_exceptions']:.1f}")
    print(f"  Zone:                {bt_result['zone']}")
    print(f"  Plus factor:         {bt_result['plus_factor']:.2f}")
    if bt_result['kupiec_p_value']:
        print(f"  Kupiec p-value:      {bt_result['kupiec_p_value']:.4f}")

    print("\n" + "=" * 70)
    print("END OF DEMO")
    print("=" * 70)
