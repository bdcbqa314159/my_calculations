"""
Equity Investments and CCP Exposures

Implements:
- Equity under IRB (PD/LGD approach, simple risk weight)
- Equity investments in funds (look-through, mandate-based, fall-back)
- CCP exposures (trade exposures, default fund contributions)

Reference: CRE36 (Equity), CRE54 (CCPs)
"""

import math
from typing import Optional


# =============================================================================
# Equity Exposures under IRB (CRE36)
# =============================================================================

# Simple risk weight method for equity (CRE36.5)
EQUITY_SIMPLE_RW = {
    "exchange_traded": 300,     # 300%
    "private_equity": 400,      # 400%
    "other": 400,               # 400%
}

# Internal models approach parameters
EQUITY_MINIMUM_PD = 0.0009  # 9 basis points floor (CRE36.12)
EQUITY_LGD = 0.90           # 90% LGD for equity (CRE36.11)


def calculate_equity_simple_rw(
    ead: float,
    equity_type: str = "exchange_traded"
) -> dict:
    """
    Calculate equity RWA using simple risk weight method.

    Parameters:
    -----------
    ead : float
        Exposure at Default (market value)
    equity_type : str
        "exchange_traded", "private_equity", "other"

    Returns:
    --------
    dict
        Equity RWA calculation
    """
    rw = EQUITY_SIMPLE_RW.get(equity_type, 400)
    rwa = ead * rw / 100

    return {
        "approach": "Simple RW",
        "ead": ead,
        "equity_type": equity_type,
        "risk_weight_pct": rw,
        "rwa": rwa,
        "capital_requirement_k": rw / 100 / 12.5,
    }


def calculate_equity_pd_lgd(
    ead: float,
    pd: float,
    lgd: float = 0.90,
    maturity: float = 5.0
) -> dict:
    """
    Calculate equity RWA using PD/LGD approach.

    Same formula as corporate IRB but with:
    - LGD = 90%
    - No maturity adjustment (or 5-year maturity)
    - Minimum PD of 0.09%

    Parameters:
    -----------
    ead : float
        Exposure at Default (market value)
    pd : float
        Probability of default of underlying
    lgd : float
        Loss given default (default 90%)
    maturity : float
        Assumed 5 years for equity

    Returns:
    --------
    dict
        Equity RWA calculation
    """
    from scipy.stats import norm

    # Apply PD floor
    pd = max(pd, EQUITY_MINIMUM_PD)

    # Correlation for equity (fixed at 0.12 for corporate-like)
    r = 0.12

    # IRB formula
    g_pd = norm.ppf(pd)
    g_confidence = norm.ppf(0.999)

    conditional_pd = norm.cdf(
        (1 - r) ** (-0.5) * g_pd + (r / (1 - r)) ** 0.5 * g_confidence
    )

    # Capital requirement
    k = lgd * conditional_pd - pd * lgd

    # Maturity adjustment (simplified)
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    maturity_factor = (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)
    k = k * maturity_factor

    # Risk weight
    risk_weight = k * 12.5 * 100

    # Floor at 100% (CRE36.13)
    risk_weight = max(risk_weight, 100)

    rwa = ead * risk_weight / 100

    return {
        "approach": "PD/LGD",
        "ead": ead,
        "pd": pd,
        "lgd": lgd,
        "correlation": r,
        "capital_requirement_k": k,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
    }


# =============================================================================
# Equity Investments in Funds (CRE60)
# =============================================================================

# Fall-back risk weight for funds
FUND_FALLBACK_RW = 1250  # 1250%


def calculate_fund_look_through(
    fund_value: float,
    underlying_exposures: list[dict]
) -> dict:
    """
    Calculate fund RWA using look-through approach.

    Bank calculates RWA for each underlying as if directly held.

    Parameters:
    -----------
    fund_value : float
        Value of fund investment
    underlying_exposures : list of dict
        Each should have: exposure_type, amount, risk_weight

    Returns:
    --------
    dict
        Look-through RWA calculation
    """
    total_underlying = sum(e["amount"] for e in underlying_exposures)
    total_rwa = sum(e["amount"] * e["risk_weight"] / 100 for e in underlying_exposures)

    # Scale to fund value
    scale_factor = fund_value / total_underlying if total_underlying > 0 else 1
    scaled_rwa = total_rwa * scale_factor

    avg_rw = (scaled_rwa / fund_value * 100) if fund_value > 0 else 0

    return {
        "approach": "Look-Through",
        "fund_value": fund_value,
        "total_underlying": total_underlying,
        "underlying_rwa": total_rwa,
        "scale_factor": scale_factor,
        "scaled_rwa": scaled_rwa,
        "average_risk_weight_pct": avg_rw,
        "exposures": underlying_exposures,
    }


def calculate_fund_mandate_based(
    fund_value: float,
    mandate_limits: dict
) -> dict:
    """
    Calculate fund RWA using mandate-based approach.

    Assume maximum permitted allocation to each asset class.

    Parameters:
    -----------
    fund_value : float
        Value of fund investment
    mandate_limits : dict
        {asset_class: (max_allocation_pct, risk_weight)}
        Example: {"equity": (0.30, 300), "corporate_bonds": (0.50, 100), "sovereign": (0.20, 0)}

    Returns:
    --------
    dict
        Mandate-based RWA calculation
    """
    # Assume worst-case: maximum allocation to highest RW assets
    allocations = []
    remaining = 1.0

    # Sort by risk weight (highest first)
    sorted_limits = sorted(mandate_limits.items(), key=lambda x: x[1][1], reverse=True)

    for asset_class, (max_alloc, rw) in sorted_limits:
        actual_alloc = min(max_alloc, remaining)
        if actual_alloc > 0:
            allocations.append({
                "asset_class": asset_class,
                "allocation": actual_alloc,
                "risk_weight": rw,
                "rwa_contribution": fund_value * actual_alloc * rw / 100,
            })
            remaining -= actual_alloc

    total_rwa = sum(a["rwa_contribution"] for a in allocations)
    avg_rw = (total_rwa / fund_value * 100) if fund_value > 0 else 0

    return {
        "approach": "Mandate-Based",
        "fund_value": fund_value,
        "rwa": total_rwa,
        "average_risk_weight_pct": avg_rw,
        "allocations": allocations,
    }


def calculate_fund_fallback(
    fund_value: float,
    leverage_factor: float = 1.0
) -> dict:
    """
    Calculate fund RWA using fall-back approach.

    1250% risk weight applied.

    Parameters:
    -----------
    fund_value : float
        Value of fund investment
    leverage_factor : float
        Fund leverage (exposure/NAV)

    Returns:
    --------
    dict
        Fall-back RWA calculation
    """
    # Apply leverage
    exposure = fund_value * leverage_factor

    # Apply 1250% RW
    rwa = exposure * FUND_FALLBACK_RW / 100

    # Cap at deduction (1250% equivalent)
    rwa = min(rwa, fund_value * 12.5)

    return {
        "approach": "Fall-Back",
        "fund_value": fund_value,
        "leverage_factor": leverage_factor,
        "exposure": exposure,
        "risk_weight_pct": FUND_FALLBACK_RW,
        "rwa": rwa,
    }


# =============================================================================
# CCP Exposures (CRE54)
# =============================================================================

# CCP exposure risk weights
CCP_RISK_WEIGHTS = {
    "qualifying_ccp_trade": 2,      # 2% for QCCP trade exposures
    "non_qualifying_ccp_trade": 100,  # 100% for non-QCCP (bilateral treatment)
    "qualifying_ccp_df": 0,         # Special calculation for default fund
}


def calculate_ccp_trade_exposure(
    ead: float,
    is_qualifying_ccp: bool = True
) -> dict:
    """
    Calculate RWA for trade exposures to CCPs.

    Parameters:
    -----------
    ead : float
        Exposure at Default (from SA-CCR or CEM)
    is_qualifying_ccp : bool
        Whether CCP is a qualifying CCP (QCCP)

    Returns:
    --------
    dict
        CCP trade exposure RWA
    """
    if is_qualifying_ccp:
        rw = CCP_RISK_WEIGHTS["qualifying_ccp_trade"]
    else:
        rw = CCP_RISK_WEIGHTS["non_qualifying_ccp_trade"]

    rwa = ead * rw / 100

    return {
        "exposure_type": "CCP Trade",
        "ead": ead,
        "is_qualifying_ccp": is_qualifying_ccp,
        "risk_weight_pct": rw,
        "rwa": rwa,
    }


def calculate_ccp_default_fund(
    df_contribution: float,
    k_ccp: float,
    total_df: float,
    ccp_capital: float,
    is_qualifying_ccp: bool = True
) -> dict:
    """
    Calculate RWA for default fund contributions to CCPs.

    For QCCP: K_i = max(K_CCP × DF_i/DF_total - c × DF_CM_i, 0) × 8 × 0.02

    Parameters:
    -----------
    df_contribution : float
        Bank's default fund contribution
    k_ccp : float
        CCP's hypothetical capital requirement
    total_df : float
        Total default fund (all members)
    ccp_capital : float
        CCP's own capital contribution
    is_qualifying_ccp : bool
        Whether CCP is qualifying

    Returns:
    --------
    dict
        Default fund RWA calculation
    """
    if not is_qualifying_ccp:
        # Non-QCCP: treat as bilateral exposure
        rw = 100
        rwa = df_contribution * rw / 100
        return {
            "exposure_type": "CCP Default Fund",
            "df_contribution": df_contribution,
            "is_qualifying_ccp": is_qualifying_ccp,
            "risk_weight_pct": rw,
            "rwa": rwa,
        }

    # QCCP calculation
    # Bank's share of default fund
    df_share = df_contribution / total_df if total_df > 0 else 0

    # CCP's capital contribution as % of total resources
    c = 2  # Concentration factor

    # Capital requirement
    k_cm = max(k_ccp * df_share - c * df_contribution / total_df * ccp_capital, 0)

    # RWA = K × 12.5
    rwa = k_cm * 12.5

    # Implied risk weight
    rw = (rwa / df_contribution * 100) if df_contribution > 0 else 0

    return {
        "exposure_type": "CCP Default Fund",
        "df_contribution": df_contribution,
        "k_ccp": k_ccp,
        "total_df": total_df,
        "ccp_capital": ccp_capital,
        "df_share": df_share,
        "is_qualifying_ccp": is_qualifying_ccp,
        "capital_requirement": k_cm,
        "risk_weight_pct": rw,
        "rwa": rwa,
    }


def calculate_total_ccp_exposure(
    trade_exposures: list[dict],
    default_fund_contributions: list[dict]
) -> dict:
    """
    Calculate total RWA for CCP exposures.

    Parameters:
    -----------
    trade_exposures : list of dict
        Each should have: ead, is_qualifying_ccp
    default_fund_contributions : list of dict
        Each should have: df_contribution, k_ccp, total_df, ccp_capital, is_qualifying_ccp

    Returns:
    --------
    dict
        Total CCP exposure RWA
    """
    total_trade_rwa = 0
    trade_results = []

    for trade in trade_exposures:
        result = calculate_ccp_trade_exposure(
            trade["ead"],
            trade.get("is_qualifying_ccp", True)
        )
        trade_results.append(result)
        total_trade_rwa += result["rwa"]

    total_df_rwa = 0
    df_results = []

    for df in default_fund_contributions:
        result = calculate_ccp_default_fund(
            df["df_contribution"],
            df.get("k_ccp", 0),
            df.get("total_df", df["df_contribution"]),
            df.get("ccp_capital", 0),
            df.get("is_qualifying_ccp", True)
        )
        df_results.append(result)
        total_df_rwa += result["rwa"]

    return {
        "trade_exposure_rwa": total_trade_rwa,
        "default_fund_rwa": total_df_rwa,
        "total_ccp_rwa": total_trade_rwa + total_df_rwa,
        "trade_exposures": trade_results,
        "default_fund_contributions": df_results,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Equity Exposures")
    print("=" * 70)

    # Simple risk weight approach
    print("\n  Simple Risk Weight Approach:")
    eq_simple = calculate_equity_simple_rw(10_000_000, "exchange_traded")
    print(f"    Exchange-traded: RW={eq_simple['risk_weight_pct']}%, RWA=${eq_simple['rwa']:,.0f}")

    eq_private = calculate_equity_simple_rw(5_000_000, "private_equity")
    print(f"    Private equity:  RW={eq_private['risk_weight_pct']}%, RWA=${eq_private['rwa']:,.0f}")

    # PD/LGD approach
    print("\n  PD/LGD Approach:")
    eq_pdlgd = calculate_equity_pd_lgd(10_000_000, pd=0.02, lgd=0.90)
    print(f"    PD=2%, LGD=90%: RW={eq_pdlgd['risk_weight_pct']:.1f}%, RWA=${eq_pdlgd['rwa']:,.0f}")

    print("\n" + "=" * 70)
    print("Equity Investments in Funds")
    print("=" * 70)

    # Look-through
    print("\n  Look-Through Approach:")
    underlying = [
        {"exposure_type": "equity", "amount": 3_000_000, "risk_weight": 300},
        {"exposure_type": "corporate_bonds", "amount": 5_000_000, "risk_weight": 100},
        {"exposure_type": "sovereign", "amount": 2_000_000, "risk_weight": 0},
    ]
    fund_lt = calculate_fund_look_through(10_000_000, underlying)
    print(f"    Fund value: ${fund_lt['fund_value']:,.0f}")
    print(f"    Avg RW: {fund_lt['average_risk_weight_pct']:.1f}%")
    print(f"    RWA: ${fund_lt['scaled_rwa']:,.0f}")

    # Mandate-based
    print("\n  Mandate-Based Approach:")
    mandate = {
        "equity": (0.30, 300),
        "corporate_bonds": (0.50, 100),
        "sovereign": (0.20, 0),
    }
    fund_mb = calculate_fund_mandate_based(10_000_000, mandate)
    print(f"    Fund value: ${fund_mb['fund_value']:,.0f}")
    print(f"    Avg RW (worst-case): {fund_mb['average_risk_weight_pct']:.1f}%")
    print(f"    RWA: ${fund_mb['rwa']:,.0f}")

    # Fall-back
    print("\n  Fall-Back Approach:")
    fund_fb = calculate_fund_fallback(10_000_000)
    print(f"    Fund value: ${fund_fb['fund_value']:,.0f}")
    print(f"    RW: {fund_fb['risk_weight_pct']}%")
    print(f"    RWA: ${fund_fb['rwa']:,.0f}")

    print("\n" + "=" * 70)
    print("CCP Exposures")
    print("=" * 70)

    # Trade exposures
    trade_exposures = [
        {"ead": 50_000_000, "is_qualifying_ccp": True},
        {"ead": 10_000_000, "is_qualifying_ccp": False},
    ]

    # Default fund contributions
    df_contributions = [
        {
            "df_contribution": 5_000_000,
            "k_ccp": 100_000_000,
            "total_df": 500_000_000,
            "ccp_capital": 50_000_000,
            "is_qualifying_ccp": True
        },
    ]

    ccp_result = calculate_total_ccp_exposure(trade_exposures, df_contributions)

    print(f"\n  Trade Exposures:")
    for trade in ccp_result["trade_exposures"]:
        ccp_type = "QCCP" if trade["is_qualifying_ccp"] else "Non-QCCP"
        print(f"    {ccp_type}: EAD=${trade['ead']:,.0f}, RW={trade['risk_weight_pct']}%, RWA=${trade['rwa']:,.0f}")

    print(f"\n  Default Fund Contributions:")
    for df in ccp_result["default_fund_contributions"]:
        print(f"    DF=${df['df_contribution']:,.0f}, RWA=${df['rwa']:,.0f}")

    print(f"\n  Total CCP RWA: ${ccp_result['total_ccp_rwa']:,.0f}")
