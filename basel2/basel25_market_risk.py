"""
Basel 2.5 Market Risk Enhancements (2009)

Implements the post-crisis market risk enhancements:
1. Stressed VaR (sVaR) - Para 718(Lxxvi)
2. Incremental Risk Charge (IRC) - Para 718(xcii)
3. Comprehensive Risk Measure (CRM) - For correlation trading
4. Enhanced specific risk charge

These were introduced in response to the 2008 financial crisis
to address procyclicality and tail risks in trading books.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


# =============================================================================
# Stressed VaR (sVaR) - Para 718(Lxxvi)
# =============================================================================

@dataclass
class VaRParameters:
    """Parameters for VaR and Stressed VaR calculation."""
    var_10day_99: float           # Current 10-day 99% VaR
    var_1day_99: float = None     # 1-day VaR (for scaling)
    avg_var_60days: float = None  # 60-day average VaR
    stressed_var_10day_99: float = None  # Stressed VaR
    avg_stressed_var_60days: float = None  # 60-day average sVaR
    stress_period_start: str = None  # e.g., "2007-07"
    stress_period_end: str = None    # e.g., "2009-03"


def calculate_stressed_var_capital(
    var_params: VaRParameters,
    multiplication_factor: float = 3.0,
    plus_factor: float = 0.0,
    stressed_multiplication_factor: float = 3.0,
    stressed_plus_factor: float = 0.0
) -> dict:
    """
    Calculate market risk capital with Stressed VaR component.

    Capital = max(VaR_t-1, mc × avg_VaR_60) + max(sVaR_t-1, ms × avg_sVaR_60)

    Where:
    - mc = multiplication factor for normal VaR (3 + plus factor)
    - ms = multiplication factor for stressed VaR (3 + plus factor)

    Parameters:
    -----------
    var_params : VaRParameters
        VaR and sVaR values
    multiplication_factor : float
        Base multiplier for normal VaR (minimum 3)
    plus_factor : float
        Regulatory add-on based on backtesting (0 to 1)
    stressed_multiplication_factor : float
        Multiplier for stressed VaR
    stressed_plus_factor : float
        Plus factor for stressed VaR

    Returns:
    --------
    dict
        Capital calculation with sVaR
    """
    # Total multipliers
    mc = multiplication_factor + plus_factor
    ms = stressed_multiplication_factor + stressed_plus_factor

    # Normal VaR component
    if var_params.avg_var_60days:
        var_component = max(var_params.var_10day_99, mc * var_params.avg_var_60days)
    else:
        var_component = mc * var_params.var_10day_99

    # Stressed VaR component
    if var_params.stressed_var_10day_99:
        if var_params.avg_stressed_var_60days:
            svar_component = max(
                var_params.stressed_var_10day_99,
                ms * var_params.avg_stressed_var_60days
            )
        else:
            svar_component = ms * var_params.stressed_var_10day_99
    else:
        svar_component = 0

    total_capital = var_component + svar_component
    rwa = total_capital * 12.5

    return {
        "approach": "Basel 2.5 VaR + sVaR",
        "var_10day_99": var_params.var_10day_99,
        "avg_var_60days": var_params.avg_var_60days,
        "multiplication_factor": mc,
        "var_component": var_component,
        "stressed_var_10day_99": var_params.stressed_var_10day_99,
        "avg_stressed_var_60days": var_params.avg_stressed_var_60days,
        "stressed_multiplication_factor": ms,
        "svar_component": svar_component,
        "stress_period": f"{var_params.stress_period_start} to {var_params.stress_period_end}",
        "total_capital": total_capital,
        "rwa": rwa,
    }


def scale_var_to_10day(var_1day: float, scaling_method: str = "sqrt") -> float:
    """
    Scale 1-day VaR to 10-day VaR.

    Parameters:
    -----------
    var_1day : float
        1-day VaR
    scaling_method : str
        "sqrt" for square-root-of-time scaling

    Returns:
    --------
    float
        10-day VaR
    """
    if scaling_method == "sqrt":
        return var_1day * math.sqrt(10)
    else:
        return var_1day * 10  # Linear (conservative)


# =============================================================================
# Backtesting Framework - Para 718(xciv-xcix)
# =============================================================================

class TrafficLightZone(Enum):
    """Backtesting traffic light zones."""
    GREEN = "green"    # 0-4 exceptions
    YELLOW = "yellow"  # 5-9 exceptions
    RED = "red"        # 10+ exceptions


# Plus factor by number of exceptions (Para 718(xcix))
BACKTESTING_PLUS_FACTORS = {
    0: 0.00, 1: 0.00, 2: 0.00, 3: 0.00, 4: 0.00,  # Green zone
    5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85,  # Yellow zone
    # 10+: Red zone - typically 1.00 or model review required
}


def evaluate_backtesting(
    exceptions_count: int,
    observation_days: int = 250
) -> dict:
    """
    Evaluate backtesting results and determine plus factor.

    An exception occurs when actual loss exceeds VaR.

    Parameters:
    -----------
    exceptions_count : int
        Number of exceptions in observation period
    observation_days : int
        Number of trading days (typically 250)

    Returns:
    --------
    dict
        Backtesting evaluation
    """
    # Expected exceptions at 99% confidence over 250 days = 2.5
    expected_exceptions = observation_days * 0.01

    # Determine zone
    if exceptions_count <= 4:
        zone = TrafficLightZone.GREEN
        plus_factor = BACKTESTING_PLUS_FACTORS.get(exceptions_count, 0.00)
        action = "No action required"
    elif exceptions_count <= 9:
        zone = TrafficLightZone.YELLOW
        plus_factor = BACKTESTING_PLUS_FACTORS.get(exceptions_count, 0.85)
        action = "Model review recommended; plus factor applied"
    else:
        zone = TrafficLightZone.RED
        plus_factor = 1.00
        action = "Model presumed inaccurate; full review required"

    exception_rate = exceptions_count / observation_days

    return {
        "exceptions_count": exceptions_count,
        "observation_days": observation_days,
        "expected_exceptions": expected_exceptions,
        "exception_rate": exception_rate,
        "zone": zone.value,
        "plus_factor": plus_factor,
        "total_multiplier": 3.0 + plus_factor,
        "action_required": action,
    }


# =============================================================================
# Incremental Risk Charge (IRC) - Para 718(xcii)
# =============================================================================

class RatingMigration(Enum):
    """Rating migration events."""
    UPGRADE = "upgrade"
    STABLE = "stable"
    DOWNGRADE = "downgrade"
    DEFAULT = "default"


# Default probabilities by rating (1-year horizon)
IRC_DEFAULT_PROBABILITIES = {
    "AAA": 0.0001,
    "AA": 0.0002,
    "A": 0.0005,
    "BBB": 0.0020,
    "BB": 0.0100,
    "B": 0.0400,
    "CCC": 0.1500,
    "D": 1.0000,
}

# LGD assumptions for IRC
IRC_LGD = {
    "senior_secured": 0.25,
    "senior_unsecured": 0.45,
    "subordinated": 0.75,
}

# Rating migration probabilities (simplified 1-year matrix)
# Format: current_rating -> {new_rating: probability}
RATING_MIGRATION_MATRIX = {
    "AAA": {"AAA": 0.9081, "AA": 0.0833, "A": 0.0068, "BBB": 0.0006, "BB": 0.0012, "B": 0.0000, "CCC": 0.0000, "D": 0.0000},
    "AA": {"AAA": 0.0070, "AA": 0.9065, "A": 0.0779, "BBB": 0.0064, "BB": 0.0006, "B": 0.0014, "CCC": 0.0002, "D": 0.0000},
    "A": {"AAA": 0.0009, "AA": 0.0227, "A": 0.9105, "BBB": 0.0552, "BB": 0.0074, "B": 0.0026, "CCC": 0.0001, "D": 0.0006},
    "BBB": {"AAA": 0.0002, "AA": 0.0033, "A": 0.0595, "BBB": 0.8693, "BB": 0.0530, "B": 0.0117, "CCC": 0.0012, "D": 0.0018},
    "BB": {"AAA": 0.0003, "AA": 0.0014, "A": 0.0067, "BBB": 0.0773, "BB": 0.8053, "B": 0.0884, "CCC": 0.0100, "D": 0.0106},
    "B": {"AAA": 0.0000, "AA": 0.0011, "A": 0.0024, "BBB": 0.0043, "BB": 0.0648, "B": 0.8346, "CCC": 0.0407, "D": 0.0521},
    "CCC": {"AAA": 0.0022, "AA": 0.0000, "A": 0.0022, "BBB": 0.0130, "BB": 0.0238, "B": 0.1124, "CCC": 0.6486, "D": 0.1978},
}


@dataclass
class IRCPosition:
    """A position for IRC calculation."""
    position_id: str
    issuer: str
    notional: float
    market_value: float
    rating: str
    seniority: str = "senior_unsecured"
    liquidity_horizon: int = 3  # months (1, 3, 6, or 12)
    is_long: bool = True


def calculate_irc_position(
    position: IRCPosition,
    confidence_level: float = 0.999,
    horizon_years: float = 1.0
) -> dict:
    """
    Calculate IRC for a single position.

    IRC captures default risk and migration risk over 1-year horizon
    at 99.9% confidence level.

    Parameters:
    -----------
    position : IRCPosition
        Position details
    confidence_level : float
        Confidence level (99.9%)
    horizon_years : float
        Capital horizon (1 year)

    Returns:
    --------
    dict
        IRC calculation for position
    """
    # Default probability
    pd = IRC_DEFAULT_PROBABILITIES.get(position.rating, 0.10)

    # LGD
    lgd = IRC_LGD.get(position.seniority, 0.45)

    # Expected default loss
    expected_loss = abs(position.market_value) * pd * lgd

    # Migration risk (simplified - spread widening from downgrade)
    migration_probs = RATING_MIGRATION_MATRIX.get(position.rating, {})

    # Calculate expected migration loss (simplified)
    migration_loss = 0
    spread_impact = {
        "AAA": 0.00, "AA": 0.01, "A": 0.02, "BBB": 0.04,
        "BB": 0.08, "B": 0.15, "CCC": 0.30, "D": lgd
    }

    current_spread = spread_impact.get(position.rating, 0.05)

    for new_rating, prob in migration_probs.items():
        new_spread = spread_impact.get(new_rating, 0.10)
        spread_change = new_spread - current_spread

        if spread_change > 0:  # Downgrade
            # Price impact ≈ spread change × duration × notional
            duration = min(position.liquidity_horizon / 12 * 5, 5)  # Simplified duration
            price_impact = spread_change * duration * abs(position.market_value)
            migration_loss += prob * price_impact

    # Liquidity horizon adjustment
    # Shorter liquidity = more frequent rebalancing = lower risk
    liquidity_adjustment = math.sqrt(position.liquidity_horizon / 12)

    # Total IRC (simplified)
    # At 99.9% confidence, use ~3x expected loss as approximation
    irc = (expected_loss + migration_loss) * 3.0 * liquidity_adjustment

    # Long vs short position adjustment
    if not position.is_long:
        irc *= 0.5  # Short positions have partial offset benefit

    return {
        "position_id": position.position_id,
        "issuer": position.issuer,
        "rating": position.rating,
        "notional": position.notional,
        "market_value": position.market_value,
        "pd": pd,
        "lgd": lgd,
        "expected_loss": expected_loss,
        "migration_loss": migration_loss,
        "liquidity_horizon_months": position.liquidity_horizon,
        "liquidity_adjustment": liquidity_adjustment,
        "irc": irc,
    }


def calculate_irc_portfolio(
    positions: list[IRCPosition],
    correlation: float = 0.25
) -> dict:
    """
    Calculate IRC for a portfolio of positions.

    Includes diversification benefit from imperfect correlation.

    Parameters:
    -----------
    positions : list of IRCPosition
        Portfolio positions
    correlation : float
        Inter-issuer correlation (typically 0.2-0.3)

    Returns:
    --------
    dict
        Portfolio IRC calculation
    """
    if not positions:
        return {"total_irc": 0, "positions": []}

    position_results = []
    total_irc_standalone = 0

    for pos in positions:
        result = calculate_irc_position(pos)
        position_results.append(result)
        total_irc_standalone += result["irc"]

    # Diversification benefit (simplified square-root correlation model)
    n = len(positions)
    if n > 1:
        # Diversified IRC ≈ sqrt(sum(IRC_i^2) + 2 × ρ × sum_i<j(IRC_i × IRC_j))
        ircs = [r["irc"] for r in position_results]
        sum_sq = sum(i ** 2 for i in ircs)
        sum_cross = sum(ircs[i] * ircs[j] for i in range(n) for j in range(i + 1, n))

        diversified_irc = math.sqrt(sum_sq + 2 * correlation * sum_cross)
        diversification_benefit = total_irc_standalone - diversified_irc
    else:
        diversified_irc = total_irc_standalone
        diversification_benefit = 0

    return {
        "approach": "IRC",
        "confidence_level": "99.9%",
        "horizon": "1 year",
        "position_count": n,
        "correlation_assumption": correlation,
        "total_irc_standalone": total_irc_standalone,
        "diversification_benefit": diversification_benefit,
        "diversified_irc": diversified_irc,
        "rwa": diversified_irc * 12.5,
        "positions": position_results,
    }


# =============================================================================
# Comprehensive Risk Measure (CRM) - Para 718(xciii)
# =============================================================================

@dataclass
class CorrelationTradingPosition:
    """Position in correlation trading portfolio."""
    position_id: str
    instrument_type: str  # "cdo_tranche", "nth_to_default", "index_cds"
    notional: float
    market_value: float
    attachment: float = 0.0  # For tranches
    detachment: float = 1.0  # For tranches
    underlying_pool_size: int = 100


def calculate_crm_charge(
    positions: list[CorrelationTradingPosition],
    floor_percentage: float = 0.08  # 8% floor
) -> dict:
    """
    Calculate Comprehensive Risk Measure for correlation trading.

    CRM replaces specific risk charge for securitization positions
    in the trading book. It must capture:
    - Cumulative default risk
    - Credit spread risk
    - Correlation risk
    - Basis risk

    Parameters:
    -----------
    positions : list of CorrelationTradingPosition
        Correlation trading positions
    floor_percentage : float
        Floor as percentage of specific risk charge (8%)

    Returns:
    --------
    dict
        CRM calculation
    """
    if not positions:
        return {"crm_charge": 0, "positions": []}

    total_notional = sum(abs(p.notional) for p in positions)
    total_mv = sum(abs(p.market_value) for p in positions)

    position_results = []
    total_specific_risk = 0

    for pos in positions:
        # Base specific risk charge depends on tranche type
        if pos.instrument_type == "cdo_tranche":
            # Equity tranches (attachment = 0) get higher charge
            if pos.attachment == 0:
                specific_risk_rate = 0.24  # 24% for equity
            elif pos.detachment <= 0.15:
                specific_risk_rate = 0.12  # 12% for mezzanine
            else:
                specific_risk_rate = 0.04  # 4% for senior
        elif pos.instrument_type == "nth_to_default":
            specific_risk_rate = 0.16  # 16% for nth-to-default
        else:
            specific_risk_rate = 0.08  # 8% for index CDS

        specific_risk = abs(pos.market_value) * specific_risk_rate
        total_specific_risk += specific_risk

        position_results.append({
            "position_id": pos.position_id,
            "instrument_type": pos.instrument_type,
            "notional": pos.notional,
            "market_value": pos.market_value,
            "attachment": pos.attachment,
            "detachment": pos.detachment,
            "specific_risk_rate": specific_risk_rate,
            "specific_risk": specific_risk,
        })

    # CRM charge with floor
    crm_floor = total_specific_risk * floor_percentage
    crm_charge = max(total_specific_risk, crm_floor)

    return {
        "approach": "CRM",
        "total_notional": total_notional,
        "total_market_value": total_mv,
        "total_specific_risk": total_specific_risk,
        "floor_percentage": floor_percentage,
        "crm_floor": crm_floor,
        "crm_charge": crm_charge,
        "rwa": crm_charge * 12.5,
        "positions": position_results,
    }


# =============================================================================
# Enhanced Securitization Specific Risk - Para 718
# =============================================================================

# Re-securitization higher risk weights (Basel 2.5)
RESECURITIZATION_RISK_WEIGHTS = {
    "AAA": 0.016,    # 1.6% (vs 0.8% for securitization)
    "AA": 0.024,     # 2.4%
    "A": 0.04,       # 4%
    "BBB": 0.06,     # 6%
    "BB": 0.12,      # 12%
    "below_BB": 1.00,  # Deduction
}

SECURITIZATION_RISK_WEIGHTS = {
    "AAA": 0.008,    # 0.8%
    "AA": 0.012,     # 1.2%
    "A": 0.016,      # 1.6%
    "BBB": 0.028,    # 2.8%
    "BB": 0.08,      # 8%
    "below_BB": 1.00,  # Deduction
}


def calculate_securitization_specific_risk(
    market_value: float,
    rating: str,
    is_resecuritization: bool = False
) -> dict:
    """
    Calculate specific risk charge for securitization in trading book.

    Basel 2.5 introduced higher charges for re-securitizations.

    Parameters:
    -----------
    market_value : float
        Market value of position
    rating : str
        External rating
    is_resecuritization : bool
        Whether position is a re-securitization

    Returns:
    --------
    dict
        Specific risk calculation
    """
    if is_resecuritization:
        risk_weights = RESECURITIZATION_RISK_WEIGHTS
        approach = "Re-securitization"
    else:
        risk_weights = SECURITIZATION_RISK_WEIGHTS
        approach = "Securitization"

    # Normalize rating
    if rating in ["AAA"]:
        rating_key = "AAA"
    elif rating in ["AA+", "AA", "AA-"]:
        rating_key = "AA"
    elif rating in ["A+", "A", "A-"]:
        rating_key = "A"
    elif rating in ["BBB+", "BBB", "BBB-"]:
        rating_key = "BBB"
    elif rating in ["BB+", "BB", "BB-"]:
        rating_key = "BB"
    else:
        rating_key = "below_BB"

    risk_weight = risk_weights.get(rating_key, 1.00)

    if risk_weight >= 1.00:
        specific_risk = abs(market_value)  # Full deduction
        is_deduction = True
    else:
        specific_risk = abs(market_value) * risk_weight
        is_deduction = False

    return {
        "approach": approach,
        "market_value": market_value,
        "rating": rating,
        "risk_weight": risk_weight,
        "specific_risk_charge": specific_risk,
        "is_deduction": is_deduction,
    }


# =============================================================================
# Total Basel 2.5 Market Risk Capital
# =============================================================================

def calculate_basel25_market_risk_capital(
    var_params: VaRParameters,
    irc_positions: list[IRCPosition] = None,
    crm_positions: list[CorrelationTradingPosition] = None,
    backtesting_exceptions: int = 0,
    specific_risk_charge: float = 0
) -> dict:
    """
    Calculate total Basel 2.5 market risk capital.

    Total = VaR component + sVaR component + IRC + CRM + Specific Risk

    Parameters:
    -----------
    var_params : VaRParameters
        VaR and Stressed VaR parameters
    irc_positions : list of IRCPosition
        Positions for IRC calculation
    crm_positions : list of CorrelationTradingPosition
        Correlation trading positions
    backtesting_exceptions : int
        Number of backtesting exceptions
    specific_risk_charge : float
        Additional specific risk charge (non-IRC positions)

    Returns:
    --------
    dict
        Total market risk capital
    """
    # Backtesting evaluation
    bt_result = evaluate_backtesting(backtesting_exceptions)
    plus_factor = bt_result["plus_factor"]

    # VaR + sVaR
    var_result = calculate_stressed_var_capital(
        var_params,
        multiplication_factor=3.0,
        plus_factor=plus_factor,
        stressed_multiplication_factor=3.0,
        stressed_plus_factor=0.0  # No backtesting adjustment for sVaR
    )

    # IRC
    if irc_positions:
        irc_result = calculate_irc_portfolio(irc_positions)
        irc_charge = irc_result["diversified_irc"]
    else:
        irc_result = None
        irc_charge = 0

    # CRM
    if crm_positions:
        crm_result = calculate_crm_charge(crm_positions)
        crm_charge = crm_result["crm_charge"]
    else:
        crm_result = None
        crm_charge = 0

    # Total capital
    total_capital = (
        var_result["total_capital"] +
        irc_charge +
        crm_charge +
        specific_risk_charge
    )

    total_rwa = total_capital * 12.5

    return {
        "approach": "Basel 2.5",
        "backtesting": bt_result,
        "var_svar": {
            "var_component": var_result["var_component"],
            "svar_component": var_result["svar_component"],
            "total": var_result["total_capital"],
        },
        "irc": {
            "charge": irc_charge,
            "details": irc_result,
        },
        "crm": {
            "charge": crm_charge,
            "details": crm_result,
        },
        "specific_risk": specific_risk_charge,
        "total_capital": total_capital,
        "total_rwa": total_rwa,
        "breakdown": {
            "VaR": var_result["var_component"],
            "sVaR": var_result["svar_component"],
            "IRC": irc_charge,
            "CRM": crm_charge,
            "Specific Risk": specific_risk_charge,
        },
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel 2.5 Market Risk Enhancements")
    print("=" * 70)

    # VaR and Stressed VaR
    print("\n  Stressed VaR Component:")
    var_params = VaRParameters(
        var_10day_99=5_000_000,
        avg_var_60days=4_500_000,
        stressed_var_10day_99=12_000_000,
        avg_stressed_var_60days=11_000_000,
        stress_period_start="2008-07",
        stress_period_end="2009-03"
    )

    svar_result = calculate_stressed_var_capital(var_params)
    print(f"\n  Normal VaR (10-day, 99%): ${var_params.var_10day_99:,.0f}")
    print(f"  Stressed VaR (10-day, 99%): ${var_params.stressed_var_10day_99:,.0f}")
    print(f"  Stress period: {svar_result['stress_period']}")
    print(f"\n  VaR component: ${svar_result['var_component']:,.0f}")
    print(f"  sVaR component: ${svar_result['svar_component']:,.0f}")
    print(f"  Total capital: ${svar_result['total_capital']:,.0f}")

    # Backtesting
    print("\n" + "=" * 70)
    print("Backtesting Evaluation")
    print("=" * 70)

    for exceptions in [2, 5, 7, 10]:
        bt = evaluate_backtesting(exceptions)
        print(f"\n  Exceptions: {exceptions}")
        print(f"  Zone: {bt['zone']}")
        print(f"  Plus factor: {bt['plus_factor']}")
        print(f"  Total multiplier: {bt['total_multiplier']}")

    # IRC
    print("\n" + "=" * 70)
    print("Incremental Risk Charge (IRC)")
    print("=" * 70)

    irc_positions = [
        IRCPosition("P1", "Issuer A", 10_000_000, 10_200_000, "BBB", "senior_unsecured", 3, True),
        IRCPosition("P2", "Issuer B", 8_000_000, 7_800_000, "BB", "senior_unsecured", 3, True),
        IRCPosition("P3", "Issuer C", 5_000_000, 5_100_000, "A", "senior_unsecured", 3, True),
        IRCPosition("P4", "Issuer D", 3_000_000, 2_900_000, "BBB", "subordinated", 6, False),
    ]

    irc_result = calculate_irc_portfolio(irc_positions)
    print(f"\n  Portfolio: {irc_result['position_count']} positions")
    print(f"  Standalone IRC: ${irc_result['total_irc_standalone']:,.0f}")
    print(f"  Diversification benefit: ${irc_result['diversification_benefit']:,.0f}")
    print(f"  Diversified IRC: ${irc_result['diversified_irc']:,.0f}")

    # Total Basel 2.5 Capital
    print("\n" + "=" * 70)
    print("Total Basel 2.5 Market Risk Capital")
    print("=" * 70)

    total = calculate_basel25_market_risk_capital(
        var_params=var_params,
        irc_positions=irc_positions,
        backtesting_exceptions=3,
        specific_risk_charge=500_000
    )

    print(f"\n  {'Component':<20} {'Capital':>15}")
    print(f"  {'-'*20} {'-'*15}")
    for comp, value in total["breakdown"].items():
        print(f"  {comp:<20} ${value:>13,.0f}")
    print(f"  {'-'*20} {'-'*15}")
    print(f"  {'Total':<20} ${total['total_capital']:>13,.0f}")
    print(f"\n  Total RWA: ${total['total_rwa']:,.0f}")
