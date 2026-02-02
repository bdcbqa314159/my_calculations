"""
IRRBB - Interest Rate Risk in the Banking Book

Implements:
- EVE: Economic Value of Equity approach
- NII: Net Interest Income approach
- Standardised shock scenarios

Reference: SRP31 (Interest Rate Risk in Banking Book)
"""

import math
from typing import Optional


# =============================================================================
# IRRBB Shock Scenarios (SRP31.90)
# =============================================================================

# Standardised interest rate shock scenarios (in basis points)
IRRBB_SHOCK_SCENARIOS = {
    # Scenario: {currency: shock_by_tenor}
    "parallel_up": {
        "USD": 200,
        "EUR": 200,
        "GBP": 250,
        "JPY": 100,
        "CHF": 100,
        "other": 200,
    },
    "parallel_down": {
        "USD": -200,
        "EUR": -200,
        "GBP": -250,
        "JPY": -100,
        "CHF": -100,
        "other": -200,
    },
    "steepener": {
        # Short rates down, long rates up
        "short_shock": -100,  # Up to 1Y
        "long_shock": 100,    # Over 10Y
    },
    "flattener": {
        # Short rates up, long rates down
        "short_shock": 100,
        "long_shock": -100,
    },
    "short_up": {
        "shock": 300,  # Shock at short end
    },
    "short_down": {
        "shock": -300,
    },
}

# Time buckets for gap analysis (SRP31.97)
TIME_BUCKETS = [
    ("overnight", 0, 1/365),
    ("1d_1m", 1/365, 1/12),
    ("1m_3m", 1/12, 3/12),
    ("3m_6m", 3/12, 6/12),
    ("6m_9m", 6/12, 9/12),
    ("9m_1y", 9/12, 1),
    ("1y_2y", 1, 2),
    ("2y_3y", 2, 3),
    ("3y_4y", 3, 4),
    ("4y_5y", 4, 5),
    ("5y_7y", 5, 7),
    ("7y_10y", 7, 10),
    ("10y_15y", 10, 15),
    ("15y_20y", 15, 20),
    ("over_20y", 20, 30),
]

# Midpoint durations for each bucket (approximate)
BUCKET_DURATIONS = {
    "overnight": 0.001,
    "1d_1m": 0.04,
    "1m_3m": 0.17,
    "3m_6m": 0.375,
    "6m_9m": 0.625,
    "9m_1y": 0.875,
    "1y_2y": 1.5,
    "2y_3y": 2.5,
    "3y_4y": 3.5,
    "4y_5y": 4.5,
    "5y_7y": 6.0,
    "7y_10y": 8.5,
    "10y_15y": 12.5,
    "15y_20y": 17.5,
    "over_20y": 25.0,
}


# =============================================================================
# EVE (Economic Value of Equity) Approach
# =============================================================================

def calculate_pv01(
    notional: float,
    duration: float,
    rate: float = 0.05
) -> float:
    """
    Calculate PV01 (price value of a basis point).

    PV01 ≈ Notional × Duration × 0.0001

    Parameters:
    -----------
    notional : float
        Notional/principal amount
    duration : float
        Modified duration in years
    rate : float
        Current interest rate (for convexity adjustment)

    Returns:
    --------
    float
        PV01 value
    """
    return notional * duration * 0.0001


def calculate_duration_gap(
    assets: list[dict],
    liabilities: list[dict]
) -> dict:
    """
    Calculate duration gap analysis.

    Parameters:
    -----------
    assets : list of dict
        Each should have: notional, duration
    liabilities : list of dict
        Each should have: notional, duration

    Returns:
    --------
    dict
        Duration gap analysis
    """
    total_assets = sum(a["notional"] for a in assets)
    total_liabilities = sum(l["notional"] for l in liabilities)

    # Weighted average duration
    wa_duration_assets = sum(a["notional"] * a["duration"] for a in assets) / total_assets if total_assets > 0 else 0
    wa_duration_liabilities = sum(l["notional"] * l["duration"] for l in liabilities) / total_liabilities if total_liabilities > 0 else 0

    # Duration gap
    leverage = total_assets / (total_assets - total_liabilities) if total_assets != total_liabilities else 1
    duration_gap = wa_duration_assets - (total_liabilities / total_assets) * wa_duration_liabilities if total_assets > 0 else 0

    # PV01
    pv01_assets = sum(calculate_pv01(a["notional"], a["duration"]) for a in assets)
    pv01_liabilities = sum(calculate_pv01(l["notional"], l["duration"]) for l in liabilities)
    net_pv01 = pv01_assets - pv01_liabilities

    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "equity": total_assets - total_liabilities,
        "wa_duration_assets": wa_duration_assets,
        "wa_duration_liabilities": wa_duration_liabilities,
        "duration_gap": duration_gap,
        "pv01_assets": pv01_assets,
        "pv01_liabilities": pv01_liabilities,
        "net_pv01": net_pv01,
    }


def calculate_eve_impact(
    gap_analysis: dict,
    rate_shock_bps: int = 200
) -> dict:
    """
    Calculate EVE impact from interest rate shock.

    ΔEVE = -Duration Gap × Equity × Δr

    Parameters:
    -----------
    gap_analysis : dict
        Output from calculate_duration_gap
    rate_shock_bps : int
        Interest rate shock in basis points

    Returns:
    --------
    dict
        EVE impact analysis
    """
    equity = gap_analysis["equity"]
    duration_gap = gap_analysis["duration_gap"]
    net_pv01 = gap_analysis["net_pv01"]

    # Rate shock as decimal
    rate_shock = rate_shock_bps / 10000

    # EVE change
    eve_change = -duration_gap * equity * rate_shock

    # Alternative: using PV01
    eve_change_pv01 = net_pv01 * rate_shock_bps

    # As % of equity
    eve_change_pct = (eve_change / equity * 100) if equity > 0 else 0

    return {
        "equity": equity,
        "duration_gap": duration_gap,
        "rate_shock_bps": rate_shock_bps,
        "eve_change": eve_change,
        "eve_change_pv01": eve_change_pv01,
        "eve_change_pct": eve_change_pct,
        "new_equity": equity + eve_change,
    }


def calculate_eve_all_scenarios(
    assets: list[dict],
    liabilities: list[dict],
    currency: str = "USD"
) -> dict:
    """
    Calculate EVE impact under all standardised scenarios.

    Parameters:
    -----------
    assets : list of dict
        Banking book assets with notional, duration
    liabilities : list of dict
        Banking book liabilities with notional, duration
    currency : str
        Currency for shock calibration

    Returns:
    --------
    dict
        EVE results for all scenarios
    """
    gap_analysis = calculate_duration_gap(assets, liabilities)

    results = {"gap_analysis": gap_analysis, "scenarios": {}}

    # Parallel shocks
    for scenario in ["parallel_up", "parallel_down"]:
        shock = IRRBB_SHOCK_SCENARIOS[scenario].get(currency, IRRBB_SHOCK_SCENARIOS[scenario]["other"])
        impact = calculate_eve_impact(gap_analysis, shock)
        results["scenarios"][scenario] = impact

    # Find worst-case scenario
    worst_scenario = min(results["scenarios"].items(), key=lambda x: x[1]["eve_change"])
    results["worst_scenario"] = worst_scenario[0]
    results["worst_eve_change"] = worst_scenario[1]["eve_change"]
    results["worst_eve_change_pct"] = worst_scenario[1]["eve_change_pct"]

    return results


# =============================================================================
# NII (Net Interest Income) Approach
# =============================================================================

def calculate_repricing_gap(
    assets_by_bucket: dict,
    liabilities_by_bucket: dict
) -> dict:
    """
    Calculate repricing gap by time bucket.

    Parameters:
    -----------
    assets_by_bucket : dict
        {bucket_name: amount}
    liabilities_by_bucket : dict
        {bucket_name: amount}

    Returns:
    --------
    dict
        Repricing gap analysis
    """
    gaps = {}
    cumulative_gap = 0

    for bucket, _, _ in TIME_BUCKETS:
        asset_amount = assets_by_bucket.get(bucket, 0)
        liability_amount = liabilities_by_bucket.get(bucket, 0)
        gap = asset_amount - liability_amount
        cumulative_gap += gap

        gaps[bucket] = {
            "assets": asset_amount,
            "liabilities": liability_amount,
            "gap": gap,
            "cumulative_gap": cumulative_gap,
        }

    return gaps


def calculate_nii_sensitivity(
    repricing_gaps: dict,
    rate_shock_bps: int = 200,
    time_horizon_years: float = 1.0
) -> dict:
    """
    Calculate NII sensitivity to interest rate changes.

    ΔNII = Σ(Gap_i × Δr × Time_remaining_i)

    Parameters:
    -----------
    repricing_gaps : dict
        Output from calculate_repricing_gap
    rate_shock_bps : int
        Interest rate shock in basis points
    time_horizon_years : float
        NII calculation horizon (typically 1 year)

    Returns:
    --------
    dict
        NII sensitivity analysis
    """
    rate_shock = rate_shock_bps / 10000

    total_nii_impact = 0
    bucket_impacts = {}

    for bucket, data in repricing_gaps.items():
        # Get midpoint of bucket for time remaining calculation
        duration = BUCKET_DURATIONS.get(bucket, 0.5)

        # Time remaining in horizon
        time_in_horizon = max(0, min(time_horizon_years - duration/2, time_horizon_years))

        # NII impact for this bucket
        nii_impact = data["gap"] * rate_shock * time_in_horizon

        bucket_impacts[bucket] = {
            "gap": data["gap"],
            "time_weight": time_in_horizon,
            "nii_impact": nii_impact,
        }

        total_nii_impact += nii_impact

    return {
        "rate_shock_bps": rate_shock_bps,
        "time_horizon": time_horizon_years,
        "total_nii_impact": total_nii_impact,
        "bucket_impacts": bucket_impacts,
    }


# =============================================================================
# Comprehensive IRRBB Analysis
# =============================================================================

def calculate_irrbb_capital(
    eve_worst_case: float,
    tier1_capital: float,
    threshold_pct: float = 0.15
) -> dict:
    """
    Calculate IRRBB capital implications.

    Outlier test: If ΔEVE > 15% of Tier 1, bank is an outlier.

    Parameters:
    -----------
    eve_worst_case : float
        Worst-case EVE change (negative = loss)
    tier1_capital : float
        Tier 1 capital
    threshold_pct : float
        Outlier threshold (default 15%)

    Returns:
    --------
    dict
        IRRBB capital analysis
    """
    eve_loss = abs(eve_worst_case) if eve_worst_case < 0 else 0
    eve_loss_pct = eve_loss / tier1_capital if tier1_capital > 0 else 0

    is_outlier = eve_loss_pct > threshold_pct

    # Suggested Pillar 2 add-on (if outlier)
    if is_outlier:
        pillar2_addon = eve_loss - (threshold_pct * tier1_capital)
    else:
        pillar2_addon = 0

    return {
        "eve_worst_case": eve_worst_case,
        "eve_loss": eve_loss,
        "tier1_capital": tier1_capital,
        "eve_loss_pct": eve_loss_pct * 100,
        "threshold_pct": threshold_pct * 100,
        "is_outlier": is_outlier,
        "pillar2_addon": pillar2_addon,
    }


def calculate_full_irrbb_analysis(
    assets: list[dict],
    liabilities: list[dict],
    assets_by_bucket: dict,
    liabilities_by_bucket: dict,
    tier1_capital: float,
    currency: str = "USD"
) -> dict:
    """
    Comprehensive IRRBB analysis including EVE, NII, and capital.

    Parameters:
    -----------
    assets : list of dict
        Assets with notional, duration
    liabilities : list of dict
        Liabilities with notional, duration
    assets_by_bucket : dict
        Assets by repricing bucket
    liabilities_by_bucket : dict
        Liabilities by repricing bucket
    tier1_capital : float
        Tier 1 capital
    currency : str
        Currency for shock calibration

    Returns:
    --------
    dict
        Complete IRRBB analysis
    """
    # EVE analysis
    eve_results = calculate_eve_all_scenarios(assets, liabilities, currency)

    # NII analysis
    repricing_gaps = calculate_repricing_gap(assets_by_bucket, liabilities_by_bucket)
    nii_up = calculate_nii_sensitivity(repricing_gaps, 200)
    nii_down = calculate_nii_sensitivity(repricing_gaps, -200)

    # Capital analysis
    capital_analysis = calculate_irrbb_capital(
        eve_results["worst_eve_change"],
        tier1_capital
    )

    return {
        "eve": eve_results,
        "nii": {
            "repricing_gaps": repricing_gaps,
            "parallel_up": nii_up,
            "parallel_down": nii_down,
        },
        "capital": capital_analysis,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("IRRBB - Interest Rate Risk in Banking Book")
    print("=" * 70)

    # Sample banking book
    assets = [
        {"notional": 500_000_000, "duration": 4.5},   # Mortgages
        {"notional": 300_000_000, "duration": 2.0},   # Corporate loans
        {"notional": 100_000_000, "duration": 0.25},  # Short-term
        {"notional": 100_000_000, "duration": 7.0},   # Bonds
    ]

    liabilities = [
        {"notional": 600_000_000, "duration": 0.5},   # Deposits
        {"notional": 200_000_000, "duration": 3.0},   # Term funding
        {"notional": 100_000_000, "duration": 5.0},   # Bonds issued
    ]

    # Repricing buckets (simplified)
    assets_by_bucket = {
        "overnight": 50_000_000,
        "1m_3m": 100_000_000,
        "3m_6m": 100_000_000,
        "6m_9m": 50_000_000,
        "1y_2y": 200_000_000,
        "2y_3y": 150_000_000,
        "5y_7y": 200_000_000,
        "7y_10y": 150_000_000,
    }

    liabilities_by_bucket = {
        "overnight": 200_000_000,
        "1m_3m": 300_000_000,
        "3m_6m": 100_000_000,
        "1y_2y": 100_000_000,
        "2y_3y": 100_000_000,
        "5y_7y": 100_000_000,
    }

    tier1_capital = 100_000_000

    # Full analysis
    result = calculate_full_irrbb_analysis(
        assets, liabilities,
        assets_by_bucket, liabilities_by_bucket,
        tier1_capital, "USD"
    )

    # Print EVE results
    print("\n  EVE Analysis:")
    print(f"    Total Assets:          ${result['eve']['gap_analysis']['total_assets']:,.0f}")
    print(f"    Total Liabilities:     ${result['eve']['gap_analysis']['total_liabilities']:,.0f}")
    print(f"    Equity:                ${result['eve']['gap_analysis']['equity']:,.0f}")
    print(f"    Duration Gap:          {result['eve']['gap_analysis']['duration_gap']:.2f} years")
    print(f"    Net PV01:              ${result['eve']['gap_analysis']['net_pv01']:,.0f}")

    print("\n  EVE Scenarios:")
    for scenario, impact in result['eve']['scenarios'].items():
        print(f"    {scenario:<15}: ΔEVE = ${impact['eve_change']:,.0f} ({impact['eve_change_pct']:.1f}%)")

    print(f"\n    Worst scenario:        {result['eve']['worst_scenario']}")
    print(f"    Worst ΔEVE:            ${result['eve']['worst_eve_change']:,.0f} ({result['eve']['worst_eve_change_pct']:.1f}%)")

    # Print NII results
    print("\n  NII Analysis (1-year horizon):")
    print(f"    +200bps impact:        ${result['nii']['parallel_up']['total_nii_impact']:,.0f}")
    print(f"    -200bps impact:        ${result['nii']['parallel_down']['total_nii_impact']:,.0f}")

    # Print capital results
    print("\n  Capital Analysis:")
    print(f"    Tier 1 Capital:        ${result['capital']['tier1_capital']:,.0f}")
    print(f"    EVE Loss:              ${result['capital']['eve_loss']:,.0f} ({result['capital']['eve_loss_pct']:.1f}% of T1)")
    print(f"    Outlier (>15%):        {result['capital']['is_outlier']}")
    if result['capital']['pillar2_addon'] > 0:
        print(f"    Suggested P2 add-on:   ${result['capital']['pillar2_addon']:,.0f}")
