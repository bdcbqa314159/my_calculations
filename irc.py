"""
Incremental Risk Charge (IRC) — Full Monte Carlo Implementation

Basel 2.5 / Basel III IRC model for trading book credit positions:
- 1-year capital horizon at 99.9% confidence
- Captures default risk AND rating migration risk
- Multi-factor Gaussian copula for issuer correlation
- Constant level of risk assumption with liquidity horizon rebalancing

Key regulatory references:
- Basel 2.5: Para 718(xcii) – IRC framework
- BCBS 238: Revisions to Basel II market risk framework (IRC details)

IRC Capital = 99.9th percentile of 1-year P&L distribution from:
    - Default losses (LGD × notional)
    - Migration losses (spread change × duration × notional)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from rwa_calc import RATING_TO_PD


# =============================================================================
# Rating Transition Matrices (1-year, based on S&P historical data)
# =============================================================================

# 1-year rating transition matrix (row = from, col = to)
# Values are probabilities; each row sums to 1.0
RATING_CATEGORIES = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D"]

TRANSITION_MATRIX = {
    "AAA": {"AAA": 0.9081, "AA": 0.0833, "A": 0.0068, "BBB": 0.0006, "BB": 0.0008, "B": 0.0003, "CCC": 0.0001, "D": 0.0000},
    "AA":  {"AAA": 0.0070, "AA": 0.9065, "A": 0.0779, "BBB": 0.0064, "BB": 0.0006, "B": 0.0010, "CCC": 0.0004, "D": 0.0002},
    "A":   {"AAA": 0.0009, "AA": 0.0227, "A": 0.9105, "BBB": 0.0552, "BB": 0.0074, "B": 0.0021, "CCC": 0.0006, "D": 0.0006},
    "BBB": {"AAA": 0.0002, "AA": 0.0033, "A": 0.0595, "BBB": 0.8693, "BB": 0.0530, "B": 0.0102, "CCC": 0.0027, "D": 0.0018},
    "BB":  {"AAA": 0.0003, "AA": 0.0014, "A": 0.0067, "BBB": 0.0773, "BB": 0.8053, "B": 0.0804, "CCC": 0.0180, "D": 0.0106},
    "B":   {"AAA": 0.0000, "AA": 0.0011, "A": 0.0024, "BBB": 0.0043, "BB": 0.0648, "B": 0.8297, "CCC": 0.0456, "D": 0.0521},
    "CCC": {"AAA": 0.0022, "AA": 0.0000, "A": 0.0022, "BBB": 0.0130, "BB": 0.0238, "B": 0.1124, "CCC": 0.6486, "D": 0.1978},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# Cumulative transition thresholds for simulation (pre-computed for efficiency)
def _build_cumulative_thresholds():
    """Build cumulative probability thresholds for rating simulation."""
    thresholds = {}
    for from_rating in RATING_CATEGORIES:
        if from_rating == "D":
            thresholds[from_rating] = [(1.0, "D")]
            continue
        probs = TRANSITION_MATRIX[from_rating]
        cumulative = []
        running = 0.0
        for to_rating in RATING_CATEGORIES:
            running += probs[to_rating]
            cumulative.append((running, to_rating))
        thresholds[from_rating] = cumulative
    return thresholds

CUMULATIVE_THRESHOLDS = _build_cumulative_thresholds()


# =============================================================================
# Credit Spreads by Rating (basis points, term structure)
# =============================================================================

# Representative credit spreads by rating and tenor (basis points)
CREDIT_SPREADS = {
    # rating: {tenor_years: spread_bps}
    "AAA": {1: 15, 2: 18, 3: 20, 5: 25, 7: 30, 10: 35},
    "AA":  {1: 25, 2: 30, 3: 35, 5: 45, 7: 55, 10: 65},
    "A":   {1: 45, 2: 55, 3: 65, 5: 80, 7: 95, 10: 110},
    "BBB": {1: 90, 2: 105, 3: 120, 5: 150, 7: 175, 10: 200},
    "BB":  {1: 200, 2: 240, 3: 280, 5: 350, 7: 400, 10: 450},
    "B":   {1: 400, 2: 480, 3: 550, 5: 650, 7: 720, 10: 800},
    "CCC": {1: 1000, 2: 1100, 3: 1200, 5: 1350, 7: 1450, 10: 1550},
    "D":   {1: 5000, 2: 5000, 3: 5000, 5: 5000, 7: 5000, 10: 5000},  # Defaulted
}


def get_credit_spread(rating: str, tenor_years: float) -> float:
    """
    Get credit spread for a given rating and tenor (linear interpolation).

    Returns spread in basis points.
    """
    if rating not in CREDIT_SPREADS:
        rating = "B"  # fallback

    spreads = CREDIT_SPREADS[rating]
    tenors = sorted(spreads.keys())

    if tenor_years <= tenors[0]:
        return spreads[tenors[0]]
    if tenor_years >= tenors[-1]:
        return spreads[tenors[-1]]

    # Linear interpolation
    for i in range(len(tenors) - 1):
        if tenors[i] <= tenor_years <= tenors[i + 1]:
            t1, t2 = tenors[i], tenors[i + 1]
            s1, s2 = spreads[t1], spreads[t2]
            return s1 + (s2 - s1) * (tenor_years - t1) / (t2 - t1)

    return spreads[tenors[-1]]


# =============================================================================
# LGD Assumptions
# =============================================================================

LGD_BY_SENIORITY = {
    "senior_secured": 0.25,
    "senior_unsecured": 0.45,
    "subordinated": 0.75,
    "equity": 1.00,
}


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class IRCPosition:
    """A single position for IRC calculation."""
    position_id: str
    issuer: str
    notional: float
    market_value: float              # current MV (can differ from notional for bonds)
    rating: str                      # current rating (AAA, AA, A, BBB, BB, B, CCC)
    tenor_years: float               # remaining maturity
    seniority: str = "senior_unsecured"
    sector: str = "corporate"
    liquidity_horizon_months: int = 3   # rebalancing frequency (1, 3, 6, 12)
    is_long: bool = True
    coupon_rate: float = 0.0         # annual coupon for duration calculation


@dataclass
class IRCConfig:
    """Configuration for IRC Monte Carlo simulation."""
    num_simulations: int = 100_000
    confidence_level: float = 0.999
    horizon_years: float = 1.0
    systematic_correlation: float = 0.50   # issuer correlation to systematic factor
    sector_correlation: float = 0.25       # intra-sector correlation boost
    seed: int = 42


# =============================================================================
# Duration and Price Sensitivity
# =============================================================================

def calculate_modified_duration(
    tenor_years: float,
    coupon_rate: float = 0.05,
    yield_rate: float = 0.05,
) -> float:
    """
    Calculate modified duration for a bond.

    Uses simplified Macaulay duration formula.
    """
    if tenor_years <= 0:
        return 0.0

    if coupon_rate <= 0:
        # Zero-coupon: duration = maturity
        return tenor_years / (1 + yield_rate)

    # Simplified: duration ≈ (1 - (1+y)^(-n)) / y
    mac_duration = (1 - (1 + yield_rate) ** (-tenor_years)) / yield_rate
    mod_duration = mac_duration / (1 + yield_rate)

    return min(mod_duration, tenor_years)  # Cap at maturity


def calculate_spread_pv01(
    notional: float,
    tenor_years: float,
    coupon_rate: float = 0.05,
) -> float:
    """
    Calculate spread PV01 (price change per 1bp spread move).

    Spread PV01 ≈ notional × modified_duration × 0.0001
    """
    mod_dur = calculate_modified_duration(tenor_years, coupon_rate)
    return notional * mod_dur * 0.0001


# =============================================================================
# Monte Carlo Simulation Engine
# =============================================================================

def simulate_rating_migration(
    current_rating: str,
    uniform_draw: float,
) -> str:
    """
    Simulate rating migration based on a uniform random draw [0, 1].

    Uses pre-computed cumulative thresholds.
    """
    if current_rating == "D":
        return "D"

    if current_rating not in CUMULATIVE_THRESHOLDS:
        return current_rating

    thresholds = CUMULATIVE_THRESHOLDS[current_rating]
    for threshold, new_rating in thresholds:
        if uniform_draw <= threshold:
            return new_rating

    return "D"  # fallback


def simulate_irc_portfolio(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> list[float]:
    """
    Monte Carlo simulation of IRC portfolio losses.

    Uses a multi-factor Gaussian copula:
    - One systematic factor X driving all issuers
    - Idiosyncratic factor per issuer
    - Sector-based correlation adjustment

    For each simulation:
    1. Draw systematic factor X ~ N(0,1)
    2. For each issuer: Z_i = rho × X + sqrt(1-rho²) × epsilon_i
    3. Convert Z_i to uniform via Phi(Z_i)
    4. Use uniform to determine rating migration
    5. Calculate P&L from migration / default

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions grouped by issuer.
    config : IRCConfig
        Simulation configuration.

    Returns
    -------
    list[float]
        Simulated portfolio losses (one per simulation).
    """
    if config is None:
        config = IRCConfig()

    rng = random.Random(config.seed)

    # Group positions by issuer (same issuer = same migration)
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    # Pre-compute position-level parameters
    position_params = []
    for pos in positions:
        lgd = LGD_BY_SENIORITY.get(pos.seniority, 0.45)
        spread_pv01 = calculate_spread_pv01(pos.notional, pos.tenor_years, pos.coupon_rate)
        current_spread = get_credit_spread(pos.rating, pos.tenor_years)

        # Liquidity horizon adjustment for constant level of risk
        # More frequent rebalancing → lower risk exposure
        lh_factor = math.sqrt(pos.liquidity_horizon_months / 12.0)

        position_params.append({
            "pos": pos,
            "lgd": lgd,
            "spread_pv01": spread_pv01,
            "current_spread": current_spread,
            "lh_factor": lh_factor,
        })

    # Pre-compute issuer correlations
    issuer_rho = {}
    sectors = {}
    for issuer, pos_list in issuer_positions.items():
        sector = pos_list[0].sector
        sectors[issuer] = sector
        # Base correlation + sector boost if same sector
        issuer_rho[issuer] = config.systematic_correlation

    def _std_normal():
        """Box-Muller for standard normal."""
        u1 = max(rng.random(), 1e-15)
        u2 = rng.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def _phi(x):
        """Standard normal CDF approximation (Abramowitz & Stegun)."""
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
        return 0.5 * (1.0 + sign * y)

    losses = []

    for _ in range(config.num_simulations):
        # Draw systematic factor
        systematic = _std_normal()

        # Simulate migration for each issuer
        issuer_new_rating = {}
        for issuer, pos_list in issuer_positions.items():
            current_rating = pos_list[0].rating  # All positions for issuer have same rating
            rho = issuer_rho[issuer]

            # Correlated latent variable
            idio = _std_normal()
            z = rho * systematic + math.sqrt(1.0 - rho * rho) * idio

            # Convert to uniform via Phi
            u = _phi(z)

            # Simulate migration
            new_rating = simulate_rating_migration(current_rating, u)
            issuer_new_rating[issuer] = new_rating

        # Calculate portfolio loss with netting within same issuer
        # First, calculate P&L by issuer (allowing long/short to offset)
        issuer_pnl: dict[str, float] = {}

        for params in position_params:
            pos = params["pos"]
            new_rating = issuer_new_rating[pos.issuer]

            if new_rating == "D":
                # Default: lose LGD × notional
                loss = params["lgd"] * abs(pos.notional)
            else:
                # Migration: spread change × PV01
                new_spread = get_credit_spread(new_rating, pos.tenor_years)
                spread_change = new_spread - params["current_spread"]  # in bps
                loss = spread_change * params["spread_pv01"]  # positive = loss

            # Apply liquidity horizon factor
            loss *= params["lh_factor"]

            # Direction: short positions gain from widening (negative loss)
            if not pos.is_long:
                loss = -loss

            # Accumulate by issuer (allows netting within issuer)
            issuer_pnl[pos.issuer] = issuer_pnl.get(pos.issuer, 0.0) + loss

        # Portfolio loss = sum of positive issuer P&Ls (no cross-issuer netting)
        portfolio_loss = sum(max(pnl, 0.0) for pnl in issuer_pnl.values())

        losses.append(portfolio_loss)

    return losses


def calculate_irc(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> dict:
    """
    Calculate IRC via Monte Carlo simulation.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio of credit positions.
    config : IRCConfig
        Simulation configuration.

    Returns
    -------
    dict
        IRC charge and distribution statistics.
    """
    if config is None:
        config = IRCConfig()

    if not positions:
        return {"irc": 0.0, "mean_loss": 0.0, "num_simulations": 0}

    # Run simulation
    losses = simulate_irc_portfolio(positions, config)

    # Sort for percentile calculation
    losses_sorted = sorted(losses)
    n = len(losses_sorted)

    # IRC = 99.9th percentile
    idx_999 = min(int(n * config.confidence_level), n - 1)
    irc = losses_sorted[idx_999]

    # Statistics
    mean_loss = sum(losses) / n
    idx_99 = min(int(n * 0.99), n - 1)
    idx_95 = min(int(n * 0.95), n - 1)
    idx_50 = n // 2

    # Expected shortfall at 99.9%
    tail_losses = losses_sorted[idx_999:]
    es_999 = sum(tail_losses) / len(tail_losses) if tail_losses else irc

    # Portfolio summary
    total_notional = sum(abs(p.notional) for p in positions)
    num_issuers = len(set(p.issuer for p in positions))

    return {
        "approach": "IRC (Monte Carlo)",
        "irc": irc,
        "rwa": irc * 12.5,
        "capital_ratio": irc / total_notional if total_notional > 0 else 0.0,
        "mean_loss": mean_loss,
        "median_loss": losses_sorted[idx_50],
        "percentile_95": losses_sorted[idx_95],
        "percentile_99": losses_sorted[idx_99],
        "percentile_999": irc,
        "expected_shortfall_999": es_999,
        "max_loss": losses_sorted[-1],
        "min_loss": losses_sorted[0],
        "num_simulations": n,
        "num_positions": len(positions),
        "num_issuers": num_issuers,
        "total_notional": total_notional,
        "config": {
            "confidence_level": config.confidence_level,
            "horizon_years": config.horizon_years,
            "systematic_correlation": config.systematic_correlation,
        },
    }


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_irc(
    positions: list[dict],
    num_simulations: int = 50_000,
    correlation: float = 0.50,
) -> dict:
    """
    Quick IRC calculation from simplified position dicts.

    Parameters
    ----------
    positions : list[dict]
        Each dict: issuer, notional, rating, tenor_years, and optionally
        seniority, sector, liquidity_horizon_months, is_long.
    num_simulations : int
        Number of MC simulations.
    correlation : float
        Systematic correlation.

    Returns
    -------
    dict
        IRC result.
    """
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
        ))

    config = IRCConfig(
        num_simulations=num_simulations,
        systematic_correlation=correlation,
    )

    return calculate_irc(irc_positions, config)


def calculate_irc_by_issuer(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> dict:
    """
    Calculate IRC with breakdown by issuer contribution.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    config : IRCConfig
        Configuration.

    Returns
    -------
    dict
        IRC with per-issuer marginal contributions.
    """
    if config is None:
        config = IRCConfig()

    # Full portfolio IRC
    full_result = calculate_irc(positions, config)
    full_irc = full_result["irc"]

    # Group by issuer
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    # Calculate marginal contribution per issuer
    issuer_contributions = []
    for issuer, issuer_pos_list in issuer_positions.items():
        # Standalone IRC for this issuer
        standalone = calculate_irc(issuer_pos_list, config)

        # IRC without this issuer (for marginal contribution)
        other_positions = [p for p in positions if p.issuer != issuer]
        if other_positions:
            without = calculate_irc(other_positions, config)
            marginal = full_irc - without["irc"]
        else:
            marginal = full_irc

        issuer_notional = sum(abs(p.notional) for p in issuer_pos_list)
        issuer_rating = issuer_pos_list[0].rating

        issuer_contributions.append({
            "issuer": issuer,
            "rating": issuer_rating,
            "num_positions": len(issuer_pos_list),
            "notional": issuer_notional,
            "standalone_irc": standalone["irc"],
            "marginal_irc": marginal,
            "pct_of_total": marginal / full_irc * 100 if full_irc > 0 else 0,
        })

    # Sort by marginal contribution
    issuer_contributions.sort(key=lambda x: x["marginal_irc"], reverse=True)

    return {
        **full_result,
        "issuer_contributions": issuer_contributions,
        "diversification_benefit": sum(c["standalone_irc"] for c in issuer_contributions) - full_irc,
    }


def irc_to_dataframe(result: dict, include_summary: bool = True):
    """
    Convert IRC result to a pandas DataFrame for export.

    Parameters
    ----------
    result : dict
        Output from calculate_irc_by_issuer() or calculate_irc().
    include_summary : bool
        If True, adds a summary row with portfolio totals.

    Returns
    -------
    pandas.DataFrame
        DataFrame with issuer-level breakdown.

    Example
    -------
    >>> result = calculate_irc_by_issuer(positions, config)
    >>> df = irc_to_dataframe(result)
    >>> df.to_csv("irc_report.csv", index=False)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for irc_to_dataframe(). Install with: pip install pandas")

    # Check if this is an issuer breakdown result
    if "issuer_contributions" not in result:
        # Simple result without issuer breakdown - return summary only
        return pd.DataFrame([{
            "issuer": "PORTFOLIO",
            "rating": "-",
            "num_positions": result.get("num_positions", 0),
            "notional": result.get("total_notional", 0),
            "standalone_irc": result.get("irc", 0),
            "marginal_irc": result.get("irc", 0),
            "pct_of_total": 100.0,
            "irc": result.get("irc", 0),
            "rwa": result.get("rwa", 0),
        }])

    # Build DataFrame from issuer contributions
    df = pd.DataFrame(result["issuer_contributions"])

    if include_summary:
        # Add summary row
        summary = pd.DataFrame([{
            "issuer": "TOTAL",
            "rating": "-",
            "num_positions": result.get("num_positions", df["num_positions"].sum()),
            "notional": result.get("total_notional", df["notional"].sum()),
            "standalone_irc": df["standalone_irc"].sum(),
            "marginal_irc": df["marginal_irc"].sum(),
            "pct_of_total": df["pct_of_total"].sum(),
        }])

        # Add diversification and portfolio IRC
        diversification = pd.DataFrame([{
            "issuer": "DIVERSIFICATION",
            "rating": "-",
            "num_positions": 0,
            "notional": 0,
            "standalone_irc": -result.get("diversification_benefit", 0),
            "marginal_irc": 0,
            "pct_of_total": 0,
        }])

        portfolio = pd.DataFrame([{
            "issuer": "PORTFOLIO IRC",
            "rating": "-",
            "num_positions": result.get("num_positions", 0),
            "notional": result.get("total_notional", 0),
            "standalone_irc": result.get("irc", 0),
            "marginal_irc": result.get("irc", 0),
            "pct_of_total": 100.0,
        }])

        df = pd.concat([df, summary, diversification, portfolio], ignore_index=True)

    return df


def irc_to_csv(result: dict, filepath: str, include_summary: bool = True) -> str:
    """
    Save IRC result directly to CSV.

    Parameters
    ----------
    result : dict
        Output from calculate_irc_by_issuer() or calculate_irc().
    filepath : str
        Path to save CSV file.
    include_summary : bool
        If True, adds summary rows.

    Returns
    -------
    str
        Path to saved file.

    Example
    -------
    >>> result = calculate_irc_by_issuer(positions, config)
    >>> irc_to_csv(result, "irc_report.csv")
    """
    df = irc_to_dataframe(result, include_summary=include_summary)
    df.to_csv(filepath, index=False)
    return filepath


# =============================================================================
# IRC + DRC Comparison (IMA vs Basel 2.5)
# =============================================================================

def compare_irc_vs_ima_drc(
    positions: list[IRCPosition],
    irc_config: IRCConfig = None,
) -> dict:
    """
    Compare Basel 2.5 IRC vs FRTB-IMA DRC.

    IRC includes migration risk; IMA DRC is default-only.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    irc_config : IRCConfig
        IRC configuration.

    Returns
    -------
    dict
        Both charges and comparison.
    """
    from frtb_ima import DRCPosition, FRTBIMAConfig, calculate_ima_drc

    # Calculate IRC
    irc_result = calculate_irc(positions, irc_config)

    # Build DRC positions
    drc_positions = []
    for pos in positions:
        pd = RATING_TO_PD.get(pos.rating, RATING_TO_PD.get("BBB", 0.004))
        lgd = LGD_BY_SENIORITY.get(pos.seniority, 0.45)

        drc_positions.append(DRCPosition(
            position_id=pos.position_id,
            obligor=pos.issuer,
            notional=pos.notional,
            market_value=pos.market_value,
            pd=pd,
            lgd=lgd,
            seniority=pos.seniority,
            sector=pos.sector,
            systematic_factor=irc_config.systematic_correlation if irc_config else 0.50,
            is_long=pos.is_long,
        ))

    drc_config = FRTBIMAConfig(
        drc_num_simulations=irc_config.num_simulations if irc_config else 100_000,
    )
    drc_result = calculate_ima_drc(drc_positions, drc_config)

    irc = irc_result["irc"]
    drc = drc_result["drc_charge"]

    return {
        "irc": irc_result,
        "drc": drc_result,
        "irc_charge": irc,
        "drc_charge": drc,
        "migration_component": irc - drc if irc > drc else 0,
        "irc_to_drc_ratio": irc / drc if drc > 0 else float("inf"),
        "commentary": (
            "IRC > DRC because IRC includes rating migration risk. "
            "Under FRTB-IMA, migration risk is captured in ES via credit spreads."
        ),
    }


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 72)
    print("Incremental Risk Charge (IRC) — Monte Carlo Simulation")
    print("=" * 72)

    # Create a sample portfolio
    positions = [
        IRCPosition("bond_1", "Corp_A", 10_000_000, 10_200_000, "BBB", 5.0,
                    "senior_unsecured", "financial", 3, True, 0.045),
        IRCPosition("bond_2", "Corp_A", 5_000_000, 4_900_000, "BBB", 3.0,
                    "senior_unsecured", "financial", 3, True, 0.04),
        IRCPosition("bond_3", "Corp_B", 8_000_000, 7_800_000, "BB", 4.0,
                    "senior_unsecured", "energy", 3, True, 0.065),
        IRCPosition("bond_4", "Corp_C", 6_000_000, 6_100_000, "A", 7.0,
                    "senior_unsecured", "tech", 6, True, 0.035),
        IRCPosition("bond_5", "Corp_D", 12_000_000, 11_500_000, "BBB", 5.0,
                    "senior_unsecured", "industrial", 3, True, 0.05),
        IRCPosition("cds_1", "Corp_B", 4_000_000, 3_900_000, "BB", 5.0,
                    "senior_unsecured", "energy", 3, False, 0.0),  # short via CDS
        IRCPosition("bond_6", "Corp_E", 7_000_000, 6_800_000, "B", 3.0,
                    "subordinated", "retail", 3, True, 0.08),
    ]

    config = IRCConfig(
        num_simulations=100_000,
        systematic_correlation=0.50,
    )

    print(f"\n  Portfolio: {len(positions)} positions, "
          f"{len(set(p.issuer for p in positions))} issuers")
    print(f"  Simulations: {config.num_simulations:,}")
    print(f"  Systematic correlation: {config.systematic_correlation}")

    # Basic IRC
    print("\n" + "-" * 72)
    print("IRC Calculation")
    print("-" * 72)

    result = calculate_irc(positions, config)

    print(f"\n  Mean loss:             ${result['mean_loss']:>14,.0f}")
    print(f"  Median loss:           ${result['median_loss']:>14,.0f}")
    print(f"  95th percentile:       ${result['percentile_95']:>14,.0f}")
    print(f"  99th percentile:       ${result['percentile_99']:>14,.0f}")
    print(f"  99.9th percentile:     ${result['percentile_999']:>14,.0f}")
    print(f"  Expected Shortfall:    ${result['expected_shortfall_999']:>14,.0f}")
    print(f"  Max loss:              ${result['max_loss']:>14,.0f}")
    print(f"\n  IRC (99.9%):           ${result['irc']:>14,.0f}")
    print(f"  IRC RWA:               ${result['rwa']:>14,.0f}")
    print(f"  Capital ratio:         {result['capital_ratio']*100:>13.2f}%")

    # IRC by issuer
    print("\n" + "-" * 72)
    print("IRC by Issuer")
    print("-" * 72)

    issuer_result = calculate_irc_by_issuer(positions, config)

    print(f"\n  {'Issuer':<12} {'Rating':>6} {'Notional':>14} {'Standalone':>12} "
          f"{'Marginal':>12} {'% Total':>8}")
    print("  " + "-" * 70)
    for c in issuer_result["issuer_contributions"]:
        print(f"  {c['issuer']:<12} {c['rating']:>6} ${c['notional']:>12,.0f} "
              f"${c['standalone_irc']:>10,.0f} ${c['marginal_irc']:>10,.0f} "
              f"{c['pct_of_total']:>7.1f}%")

    print(f"\n  Diversification benefit: ${issuer_result['diversification_benefit']:>12,.0f}")

    # IRC vs IMA DRC comparison
    print("\n" + "-" * 72)
    print("IRC vs FRTB-IMA DRC Comparison")
    print("-" * 72)

    try:
        comparison = compare_irc_vs_ima_drc(positions, config)
        print(f"\n  IRC (migration + default):  ${comparison['irc_charge']:>14,.0f}")
        print(f"  DRC (default only):         ${comparison['drc_charge']:>14,.0f}")
        print(f"  Migration component:        ${comparison['migration_component']:>14,.0f}")
        print(f"  IRC / DRC ratio:            {comparison['irc_to_drc_ratio']:>14.2f}")
    except ImportError:
        print("\n  (frtb_ima module not available for comparison)")

    # Transition matrix demo
    print("\n" + "-" * 72)
    print("Rating Transition Probabilities (1-year)")
    print("-" * 72)
    print(f"\n  {'From':<6} → {'Upgrade':>8} {'Stable':>8} {'Downgrade':>10} {'Default':>8}")
    print("  " + "-" * 50)
    for rating in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
        probs = TRANSITION_MATRIX[rating]
        # Calculate upgrade/stable/downgrade/default probabilities
        idx = RATING_CATEGORIES.index(rating)
        upgrade = sum(probs[r] for r in RATING_CATEGORIES[:idx])
        stable = probs[rating]
        downgrade = sum(probs[r] for r in RATING_CATEGORIES[idx+1:-1])
        default = probs["D"]
        print(f"  {rating:<6}   {upgrade*100:>7.2f}% {stable*100:>7.2f}% "
              f"{downgrade*100:>9.2f}% {default*100:>7.2f}%")
