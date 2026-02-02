"""
Basel II Equity Positions in the Banking Book

Implements the Basel II treatment for equity exposures held
outside the trading book (Para 343-361):

1. Market-Based Approach:
   - Simple Risk Weight Method (SRW)
   - Internal Models Method (IMM)

2. PD/LGD Approach (for A-IRB banks)

Key differences from Basel III:
- Basel III has stricter treatment with higher risk weights
- Basel III removed internal models option for equities
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from scipy.stats import norm


# =============================================================================
# Equity Types and Classifications
# =============================================================================

class EquityType(Enum):
    """Types of equity exposures."""
    PUBLICLY_TRADED = "publicly_traded"        # Listed on recognized exchange
    PRIVATELY_HELD = "privately_held"          # Not publicly traded
    PRIVATE_EQUITY = "private_equity"          # PE/VC investments
    SPECULATIVE = "speculative"                # Speculative unlisted equity
    HEDGE_FUND = "hedge_fund"                  # Hedge fund investments
    SIGNIFICANT_INVESTMENT = "significant"     # Significant stake (>10%)


class EquityApproach(Enum):
    """Basel II approaches for equity."""
    SIMPLE_RISK_WEIGHT = "simple_rw"           # Simple RW method
    INTERNAL_MODELS = "imm"                    # Internal models
    PD_LGD = "pd_lgd"                          # PD/LGD approach


# =============================================================================
# Simple Risk Weight Method (Para 344-350)
# =============================================================================

# Risk weights under Simple Risk Weight Method
SIMPLE_RW_RISK_WEIGHTS = {
    EquityType.PUBLICLY_TRADED: 300,           # 300% for publicly traded
    EquityType.PRIVATELY_HELD: 400,            # 400% for all other equities
    EquityType.PRIVATE_EQUITY: 400,            # 400%
    EquityType.SPECULATIVE: 400,               # 400%
    EquityType.HEDGE_FUND: 400,                # 400%
    EquityType.SIGNIFICANT_INVESTMENT: 400,    # 400%
}

# National discretion options (Para 345)
# Some jurisdictions allow lower RW for certain equities
NATIONAL_DISCRETION_RW = {
    "diversified_portfolio": 200,              # 200% if well-diversified
    "government_development": 100,             # 100% for policy-related investments
}


@dataclass
class EquityPosition:
    """An equity position in the banking book."""
    position_id: str
    issuer: str
    equity_type: EquityType
    fair_value: float                          # Current fair value
    cost_basis: float = None                   # Original cost (for gains/losses)
    ownership_percentage: float = 0.0          # Ownership stake
    is_listed: bool = False
    exchange: str = None                       # Exchange if listed
    country: str = "US"
    sector: str = "general"
    # For PD/LGD approach
    pd: float = None                           # If using PD/LGD
    lgd: float = 0.90                          # 90% floor for equity


def calculate_simple_rw_rwa(
    position: EquityPosition,
    use_national_discretion: bool = False,
    discretion_type: str = None
) -> dict:
    """
    Calculate RWA using Simple Risk Weight Method.

    Parameters:
    -----------
    position : EquityPosition
        Equity position details
    use_national_discretion : bool
        Whether to apply national discretion
    discretion_type : str
        Type of discretion if applicable

    Returns:
    --------
    dict
        RWA calculation
    """
    # Base risk weight by equity type
    base_rw = SIMPLE_RW_RISK_WEIGHTS.get(position.equity_type, 400)

    # Apply national discretion if applicable
    if use_national_discretion and discretion_type:
        discretion_rw = NATIONAL_DISCRETION_RW.get(discretion_type)
        if discretion_rw and discretion_rw < base_rw:
            risk_weight = discretion_rw
            rw_source = f"national_discretion_{discretion_type}"
        else:
            risk_weight = base_rw
            rw_source = "standard"
    else:
        risk_weight = base_rw
        rw_source = "standard"

    # RWA
    rwa = position.fair_value * risk_weight / 100

    # Capital requirement (8%)
    capital = rwa * 0.08

    # Unrealized gains/losses
    if position.cost_basis:
        unrealized_gain = position.fair_value - position.cost_basis
    else:
        unrealized_gain = None

    return {
        "approach": "Simple Risk Weight",
        "position_id": position.position_id,
        "issuer": position.issuer,
        "equity_type": position.equity_type.value,
        "fair_value": position.fair_value,
        "cost_basis": position.cost_basis,
        "unrealized_gain": unrealized_gain,
        "base_risk_weight": base_rw,
        "applied_risk_weight": risk_weight,
        "rw_source": rw_source,
        "rwa": rwa,
        "capital_requirement": capital,
    }


# =============================================================================
# Internal Models Method (Para 351-361)
# =============================================================================

@dataclass
class EquityVaRParameters:
    """Parameters for equity internal models."""
    var_99_quarterly: float      # 99% quarterly VaR
    var_99_annual: float = None  # 99% annual VaR (if different model)
    model_type: str = "historical_simulation"  # or "parametric", "monte_carlo"
    observation_period_years: float = 5.0
    volatility_annual: float = None


def calculate_imm_rwa(
    position: EquityPosition,
    var_params: EquityVaRParameters,
    use_annual_var: bool = False
) -> dict:
    """
    Calculate RWA using Internal Models Method.

    Banks may use internal VaR models subject to:
    - 99% confidence interval
    - Quarterly (or annual) time horizon
    - At least 5 years of historical data

    RWA = VaR × 12.5 (subject to floor based on Simple RW)

    Parameters:
    -----------
    position : EquityPosition
        Equity position
    var_params : EquityVaRParameters
        VaR model parameters
    use_annual_var : bool
        Use annual horizon instead of quarterly

    Returns:
    --------
    dict
        IMM RWA calculation
    """
    # VaR-based capital
    if use_annual_var and var_params.var_99_annual:
        var_capital = var_params.var_99_annual
        horizon = "annual"
    else:
        var_capital = var_params.var_99_quarterly
        horizon = "quarterly"

    # RWA from VaR
    rwa_var = var_capital * 12.5

    # Calculate floor (based on Simple RW method at 200%)
    floor_rw = 200  # 200% floor for IMM
    rwa_floor = position.fair_value * floor_rw / 100

    # Apply floor
    rwa = max(rwa_var, rwa_floor)
    floor_binding = rwa_var < rwa_floor

    # Implied risk weight
    implied_rw = (rwa / position.fair_value) * 100 if position.fair_value > 0 else 0

    return {
        "approach": "Internal Models",
        "position_id": position.position_id,
        "issuer": position.issuer,
        "fair_value": position.fair_value,
        "var_horizon": horizon,
        "var_99": var_capital,
        "model_type": var_params.model_type,
        "rwa_from_var": rwa_var,
        "floor_risk_weight": floor_rw,
        "rwa_floor": rwa_floor,
        "floor_binding": floor_binding,
        "rwa": rwa,
        "implied_risk_weight": implied_rw,
        "capital_requirement": rwa * 0.08,
    }


# =============================================================================
# PD/LGD Approach (Para 350) - For A-IRB banks
# =============================================================================

def calculate_equity_correlation(pd: float) -> float:
    """
    Calculate asset correlation for equity under PD/LGD approach.

    R = 0.12 × (1 - EXP(-50 × PD)) / (1 - EXP(-50))
      + 0.24 × [1 - (1 - EXP(-50 × PD)) / (1 - EXP(-50))]

    For equity, a fixed correlation of 0.12-0.24 range applies,
    but typically banks use higher correlation for equities.
    """
    # Use same formula as corporate but often with adjustment
    exp_factor = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    r = 0.12 * exp_factor + 0.24 * (1 - exp_factor)

    # Equity often gets higher correlation
    r = max(r, 0.20)  # Floor at 20%

    return r


def calculate_pd_lgd_rwa(
    position: EquityPosition,
    pd: float = None,
    lgd: float = 0.90,  # 90% LGD floor for equity
    maturity: float = 5.0  # 5-year assumed maturity
) -> dict:
    """
    Calculate RWA using PD/LGD approach for equity.

    This approach is available to A-IRB banks and uses
    the same formula as corporate exposures but with:
    - 90% LGD floor
    - 5-year maturity assumption
    - Minimum PD floors

    Parameters:
    -----------
    position : EquityPosition
        Equity position
    pd : float
        Probability of Default (bank estimate or prescribed)
    lgd : float
        LGD (90% floor)
    maturity : float
        Effective maturity (5 years typical)

    Returns:
    --------
    dict
        PD/LGD RWA calculation
    """
    # Use position PD if available
    if pd is None:
        pd = position.pd if position.pd else 0.05  # Default 5% if not specified

    # PD floor
    pd = max(pd, 0.0005)  # 5 bps floor

    # LGD floor at 90%
    lgd = max(lgd, 0.90)

    # Asset correlation
    r = calculate_equity_correlation(pd)

    # IRB formula
    g_pd = norm.ppf(pd)
    g_conf = norm.ppf(0.999)

    conditional_pd = norm.cdf(
        (1 - r) ** (-0.5) * g_pd + (r / (1 - r)) ** 0.5 * g_conf
    )

    # Capital for unexpected loss
    k_base = lgd * conditional_pd - pd * lgd

    # Maturity adjustment
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    k = k_base * (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)
    k = max(k, 0)

    # Risk weight
    risk_weight = k * 12.5 * 100

    # Apply floors
    # - 200% floor for publicly traded equities
    # - 300% floor for other equities
    if position.equity_type == EquityType.PUBLICLY_TRADED:
        floor_rw = 200
    else:
        floor_rw = 300

    applied_rw = max(risk_weight, floor_rw)
    floor_binding = risk_weight < floor_rw

    # RWA
    rwa = position.fair_value * applied_rw / 100

    return {
        "approach": "PD/LGD",
        "position_id": position.position_id,
        "issuer": position.issuer,
        "equity_type": position.equity_type.value,
        "fair_value": position.fair_value,
        "pd": pd,
        "lgd": lgd,
        "maturity": maturity,
        "correlation": r,
        "capital_k": k,
        "calculated_rw": risk_weight,
        "floor_rw": floor_rw,
        "applied_rw": applied_rw,
        "floor_binding": floor_binding,
        "rwa": rwa,
        "expected_loss": pd * lgd * position.fair_value,
        "capital_requirement": rwa * 0.08,
    }


# =============================================================================
# Portfolio-Level Calculations
# =============================================================================

def calculate_equity_portfolio_rwa(
    positions: list[EquityPosition],
    approach: EquityApproach,
    var_params: dict[str, EquityVaRParameters] = None,  # position_id -> params
    pd_overrides: dict[str, float] = None  # position_id -> PD
) -> dict:
    """
    Calculate RWA for an equity portfolio.

    Parameters:
    -----------
    positions : list of EquityPosition
        Portfolio positions
    approach : EquityApproach
        Calculation approach
    var_params : dict
        VaR parameters by position (for IMM)
    pd_overrides : dict
        PD overrides by position (for PD/LGD)

    Returns:
    --------
    dict
        Portfolio RWA
    """
    results = []
    total_fair_value = 0
    total_rwa = 0
    total_capital = 0

    for position in positions:
        if approach == EquityApproach.SIMPLE_RISK_WEIGHT:
            result = calculate_simple_rw_rwa(position)

        elif approach == EquityApproach.INTERNAL_MODELS:
            if var_params and position.position_id in var_params:
                vp = var_params[position.position_id]
            else:
                # Default VaR estimate (30% annual volatility)
                estimated_var = position.fair_value * 0.30 * 2.33 / 2  # Quarterly 99%
                vp = EquityVaRParameters(var_99_quarterly=estimated_var)
            result = calculate_imm_rwa(position, vp)

        elif approach == EquityApproach.PD_LGD:
            pd = None
            if pd_overrides and position.position_id in pd_overrides:
                pd = pd_overrides[position.position_id]
            result = calculate_pd_lgd_rwa(position, pd=pd)

        else:
            raise ValueError(f"Unknown approach: {approach}")

        results.append(result)
        total_fair_value += position.fair_value
        total_rwa += result["rwa"]
        total_capital += result["capital_requirement"]

    avg_rw = (total_rwa / total_fair_value * 100) if total_fair_value > 0 else 0

    return {
        "approach": approach.value,
        "position_count": len(positions),
        "total_fair_value": total_fair_value,
        "total_rwa": total_rwa,
        "average_risk_weight": avg_rw,
        "total_capital": total_capital,
        "positions": results,
    }


def compare_equity_approaches(
    position: EquityPosition,
    var_params: EquityVaRParameters = None,
    pd: float = None
) -> dict:
    """
    Compare all equity approaches for a single position.

    Parameters:
    -----------
    position : EquityPosition
        Equity position
    var_params : EquityVaRParameters
        For IMM (or estimated)
    pd : float
        For PD/LGD approach

    Returns:
    --------
    dict
        Comparison results
    """
    # Simple Risk Weight
    simple_rw = calculate_simple_rw_rwa(position)

    # IMM
    if var_params is None:
        # Estimate VaR (assume 35% annual vol for equity)
        estimated_var = position.fair_value * 0.35 * 2.33 / 2
        var_params = EquityVaRParameters(var_99_quarterly=estimated_var)
    imm = calculate_imm_rwa(position, var_params)

    # PD/LGD
    if pd is None:
        # Estimate PD based on equity type
        if position.equity_type == EquityType.PUBLICLY_TRADED:
            pd = 0.02  # 2% for public
        else:
            pd = 0.05  # 5% for private
    pd_lgd = calculate_pd_lgd_rwa(position, pd=pd)

    results = [
        ("Simple RW", simple_rw["rwa"], simple_rw["applied_risk_weight"]),
        ("IMM", imm["rwa"], imm["implied_risk_weight"]),
        ("PD/LGD", pd_lgd["rwa"], pd_lgd["applied_rw"]),
    ]

    results_sorted = sorted(results, key=lambda x: x[1], reverse=True)

    return {
        "position": position.position_id,
        "fair_value": position.fair_value,
        "simple_rw": simple_rw,
        "imm": imm,
        "pd_lgd": pd_lgd,
        "most_conservative": results_sorted[0][0],
        "least_conservative": results_sorted[-1][0],
        "ranking": [r[0] for r in results_sorted],
    }


# =============================================================================
# Significant Investment Treatment (Para 356-360)
# =============================================================================

def calculate_significant_investment_treatment(
    investment_value: float,
    bank_cet1_capital: float,
    ownership_percentage: float,
    investee_is_bank: bool = False
) -> dict:
    """
    Treatment for significant investments in financial entities.

    Significant = >10% ownership in a bank or financial entity

    Parameters:
    -----------
    investment_value : float
        Fair value of investment
    bank_cet1_capital : float
        Bank's CET1 capital
    ownership_percentage : float
        Ownership stake (e.g., 0.15 for 15%)
    investee_is_bank : bool
        Whether investee is a bank/financial institution

    Returns:
    --------
    dict
        Significant investment treatment
    """
    is_significant = ownership_percentage > 0.10

    if is_significant and investee_is_bank:
        # Deduction approach for significant investments in banks
        # Deduct from capital rather than risk-weight
        deduction = investment_value
        rwa = 0
        treatment = "capital_deduction"
    elif is_significant:
        # Risk weight significant non-bank investments
        risk_weight = 400  # 400% for significant investments
        rwa = investment_value * risk_weight / 100
        deduction = 0
        treatment = "risk_weighted_400"
    else:
        # Non-significant - normal treatment
        risk_weight = 300 if investee_is_bank else 400
        rwa = investment_value * risk_weight / 100
        deduction = 0
        treatment = "normal"

    # Threshold amount (some jurisdictions allow threshold before deduction)
    threshold = bank_cet1_capital * 0.10  # 10% of CET1

    return {
        "investment_value": investment_value,
        "ownership_percentage": ownership_percentage,
        "is_significant": is_significant,
        "investee_is_bank": investee_is_bank,
        "treatment": treatment,
        "deduction_amount": deduction,
        "rwa": rwa,
        "threshold_amount": threshold,
        "exceeds_threshold": investment_value > threshold,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Equity Exposures in Banking Book")
    print("=" * 70)

    # Sample positions
    positions = [
        EquityPosition("E1", "Tech Corp", EquityType.PUBLICLY_TRADED, 5_000_000, 4_000_000, 0.02, True, "NYSE"),
        EquityPosition("E2", "Private Co", EquityType.PRIVATELY_HELD, 3_000_000, 2_500_000, 0.05, False),
        EquityPosition("E3", "PE Fund", EquityType.PRIVATE_EQUITY, 2_000_000, 2_000_000, 0.08, False),
        EquityPosition("E4", "Listed Bank", EquityType.PUBLICLY_TRADED, 1_500_000, 1_200_000, 0.03, True, "LSE"),
    ]

    # Simple Risk Weight Method
    print("\n  Simple Risk Weight Method:")
    print(f"\n  {'Position':<12} {'Type':<20} {'Fair Value':>12} {'RW':>8} {'RWA':>15}")
    print(f"  {'-'*12} {'-'*20} {'-'*12} {'-'*8} {'-'*15}")

    total_rwa = 0
    for pos in positions:
        result = calculate_simple_rw_rwa(pos)
        print(f"  {pos.position_id:<12} {pos.equity_type.value:<20} "
              f"${pos.fair_value:>10,.0f} {result['applied_risk_weight']:>7.0f}% "
              f"${result['rwa']:>13,.0f}")
        total_rwa += result["rwa"]

    print(f"  {'-'*12} {'-'*20} {'-'*12} {'-'*8} {'-'*15}")
    print(f"  {'Total':<12} {'':<20} ${sum(p.fair_value for p in positions):>10,.0f} "
          f"{'':<8} ${total_rwa:>13,.0f}")

    # Approach Comparison
    print("\n" + "=" * 70)
    print("Approach Comparison - Single Position (Publicly Traded)")
    print("=" * 70)

    test_pos = positions[0]  # Tech Corp
    comp = compare_equity_approaches(test_pos, pd=0.02)

    print(f"\n  Position: {test_pos.issuer}")
    print(f"  Fair Value: ${test_pos.fair_value:,.0f}")
    print(f"\n  {'Approach':<15} {'Risk Weight':>12} {'RWA':>15} {'Capital':>12}")
    print(f"  {'-'*15} {'-'*12} {'-'*15} {'-'*12}")
    print(f"  {'Simple RW':<15} {comp['simple_rw']['applied_risk_weight']:>11.0f}% "
          f"${comp['simple_rw']['rwa']:>13,.0f} ${comp['simple_rw']['capital_requirement']:>10,.0f}")
    print(f"  {'IMM':<15} {comp['imm']['implied_risk_weight']:>11.1f}% "
          f"${comp['imm']['rwa']:>13,.0f} ${comp['imm']['capital_requirement']:>10,.0f}")
    print(f"  {'PD/LGD':<15} {comp['pd_lgd']['applied_rw']:>11.1f}% "
          f"${comp['pd_lgd']['rwa']:>13,.0f} ${comp['pd_lgd']['capital_requirement']:>10,.0f}")

    print(f"\n  Most conservative: {comp['most_conservative']}")
    print(f"  Least conservative: {comp['least_conservative']}")

    # Significant Investment
    print("\n" + "=" * 70)
    print("Significant Investment Treatment")
    print("=" * 70)

    sig = calculate_significant_investment_treatment(
        investment_value=10_000_000,
        bank_cet1_capital=500_000_000,
        ownership_percentage=0.15,
        investee_is_bank=True
    )

    print(f"\n  Investment: ${sig['investment_value']:,.0f}")
    print(f"  Ownership: {sig['ownership_percentage']*100:.1f}%")
    print(f"  Is significant: {sig['is_significant']}")
    print(f"  Investee is bank: {sig['investee_is_bank']}")
    print(f"  Treatment: {sig['treatment']}")
    print(f"  Deduction: ${sig['deduction_amount']:,.0f}")
    print(f"  RWA: ${sig['rwa']:,.0f}")
