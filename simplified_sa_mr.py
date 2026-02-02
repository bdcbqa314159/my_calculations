"""
Simplified Standardised Approach for Market Risk (Simplified SA)
Basel III/IV - BCBS d457

For banks with smaller trading books that don't meet FRTB-SA thresholds.
Simplified approach based on notional amounts and basic risk weights.

Key Features:
- Available for banks with trading book < 5% of total assets (or < EUR 50mn)
- Uses basic notional-based capital calculation
- No sensitivity-based method required
- Simpler than full FRTB-SA

Reference: BCBS d457 (January 2019) - Minimum capital requirements for market risk
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class InstrumentType(Enum):
    """Types of instruments for simplified SA."""
    INTEREST_RATE = "interest_rate"
    EQUITY = "equity"
    FOREIGN_EXCHANGE = "fx"
    COMMODITY = "commodity"
    CREDIT = "credit"
    OPTION = "option"


# Simplified risk weights by instrument type (as % of notional)
SIMPLIFIED_RISK_WEIGHTS = {
    InstrumentType.INTEREST_RATE: {
        "residual_maturity_0_1y": 0.0020,    # 0.2%
        "residual_maturity_1_5y": 0.0080,    # 0.8%
        "residual_maturity_5_10y": 0.0200,   # 2.0%
        "residual_maturity_10y_plus": 0.0400, # 4.0%
    },
    InstrumentType.EQUITY: {
        "specific_risk": 0.08,   # 8% for specific risk
        "general_risk": 0.08,   # 8% for general market risk
        "total": 0.12,          # 12% combined (with diversification)
    },
    InstrumentType.FOREIGN_EXCHANGE: {
        "general_risk": 0.08,   # 8% of net open position
    },
    InstrumentType.COMMODITY: {
        "directional_risk": 0.15,   # 15%
        "basis_risk": 0.03,         # 3% additional for spread
    },
    InstrumentType.CREDIT: {
        "investment_grade": 0.08,   # 8%
        "high_yield": 0.12,         # 12%
        "unrated": 0.12,            # 12%
    },
    InstrumentType.OPTION: {
        "delta_plus_method": True,  # Use delta-plus for options
        "gamma_charge_factor": 0.5,
        "vega_charge_factor": 0.25,
    },
}


# Thresholds for simplified SA eligibility
ELIGIBILITY_THRESHOLDS = {
    "trading_book_ratio": 0.05,     # < 5% of total assets
    "trading_book_absolute": 50e6,  # < EUR 50 million
    "derivative_ratio": 0.02,       # < 2% of total assets (for derivative exemption)
}


@dataclass
class SimplifiedPosition:
    """A position for simplified SA calculation."""
    instrument_type: InstrumentType
    notional: float
    market_value: float
    residual_maturity: Optional[float] = None  # in years
    is_long: bool = True
    credit_quality: Optional[str] = None  # investment_grade, high_yield, unrated
    delta: Optional[float] = None  # for options
    gamma: Optional[float] = None  # for options
    vega: Optional[float] = None   # for options


def check_simplified_sa_eligibility(
    total_assets: float,
    trading_book_assets: float,
    derivative_notional: float,
) -> Dict:
    """
    Check if bank is eligible for Simplified SA.

    Args:
        total_assets: Total on-balance sheet assets
        trading_book_assets: Total trading book assets
        derivative_notional: Total derivative notional

    Returns:
        Dict with eligibility result and details
    """
    trading_book_ratio = trading_book_assets / total_assets if total_assets > 0 else 0
    derivative_ratio = derivative_notional / total_assets if total_assets > 0 else 0

    # Check conditions
    ratio_eligible = trading_book_ratio < ELIGIBILITY_THRESHOLDS["trading_book_ratio"]
    absolute_eligible = trading_book_assets < ELIGIBILITY_THRESHOLDS["trading_book_absolute"]

    # Either ratio OR absolute threshold must be met
    is_eligible = ratio_eligible or absolute_eligible

    return {
        "is_eligible": is_eligible,
        "trading_book_ratio": trading_book_ratio,
        "trading_book_absolute": trading_book_assets,
        "ratio_threshold": ELIGIBILITY_THRESHOLDS["trading_book_ratio"],
        "absolute_threshold": ELIGIBILITY_THRESHOLDS["trading_book_absolute"],
        "ratio_eligible": ratio_eligible,
        "absolute_eligible": absolute_eligible,
        "derivative_ratio": derivative_ratio,
    }


def calculate_interest_rate_charge(positions: List[SimplifiedPosition]) -> Dict:
    """
    Calculate interest rate risk charge under simplified SA.

    Args:
        positions: List of interest rate positions

    Returns:
        Dict with charge breakdown
    """
    ir_positions = [p for p in positions if p.instrument_type == InstrumentType.INTEREST_RATE]

    maturity_buckets = {
        "0_1y": {"long": 0, "short": 0, "rw": SIMPLIFIED_RISK_WEIGHTS[InstrumentType.INTEREST_RATE]["residual_maturity_0_1y"]},
        "1_5y": {"long": 0, "short": 0, "rw": SIMPLIFIED_RISK_WEIGHTS[InstrumentType.INTEREST_RATE]["residual_maturity_1_5y"]},
        "5_10y": {"long": 0, "short": 0, "rw": SIMPLIFIED_RISK_WEIGHTS[InstrumentType.INTEREST_RATE]["residual_maturity_5_10y"]},
        "10y_plus": {"long": 0, "short": 0, "rw": SIMPLIFIED_RISK_WEIGHTS[InstrumentType.INTEREST_RATE]["residual_maturity_10y_plus"]},
    }

    for pos in ir_positions:
        maturity = pos.residual_maturity or 1
        if maturity <= 1:
            bucket = "0_1y"
        elif maturity <= 5:
            bucket = "1_5y"
        elif maturity <= 10:
            bucket = "5_10y"
        else:
            bucket = "10y_plus"

        if pos.is_long:
            maturity_buckets[bucket]["long"] += pos.market_value
        else:
            maturity_buckets[bucket]["short"] += abs(pos.market_value)

    # Calculate charges per bucket
    total_charge = 0
    bucket_charges = {}

    for bucket, data in maturity_buckets.items():
        net_position = abs(data["long"] - data["short"])
        matched_position = min(data["long"], data["short"])

        # Charge on net position at full rate
        net_charge = net_position * data["rw"]
        # Reduced charge on matched positions (vertical disallowance)
        matched_charge = matched_position * data["rw"] * 0.10  # 10% of matched

        bucket_charge = net_charge + matched_charge
        bucket_charges[bucket] = bucket_charge
        total_charge += bucket_charge

    return {
        "total_charge": total_charge,
        "bucket_charges": bucket_charges,
        "maturity_buckets": maturity_buckets,
    }


def calculate_equity_charge(positions: List[SimplifiedPosition]) -> Dict:
    """
    Calculate equity risk charge under simplified SA.

    Args:
        positions: List of equity positions

    Returns:
        Dict with charge breakdown
    """
    eq_positions = [p for p in positions if p.instrument_type == InstrumentType.EQUITY]

    gross_position = sum(abs(p.market_value) for p in eq_positions)
    long_position = sum(p.market_value for p in eq_positions if p.is_long)
    short_position = sum(abs(p.market_value) for p in eq_positions if not p.is_long)
    net_position = abs(long_position - short_position)

    rw = SIMPLIFIED_RISK_WEIGHTS[InstrumentType.EQUITY]

    # Specific risk on gross, general risk on net
    specific_risk_charge = gross_position * rw["specific_risk"]
    general_risk_charge = net_position * rw["general_risk"]

    total_charge = specific_risk_charge + general_risk_charge

    return {
        "total_charge": total_charge,
        "specific_risk_charge": specific_risk_charge,
        "general_risk_charge": general_risk_charge,
        "gross_position": gross_position,
        "net_position": net_position,
    }


def calculate_fx_charge(positions: List[SimplifiedPosition]) -> Dict:
    """
    Calculate foreign exchange risk charge under simplified SA.

    Args:
        positions: List of FX positions

    Returns:
        Dict with charge breakdown
    """
    fx_positions = [p for p in positions if p.instrument_type == InstrumentType.FOREIGN_EXCHANGE]

    # Calculate net open position per currency (simplified: just sum)
    long_total = sum(p.market_value for p in fx_positions if p.is_long)
    short_total = sum(abs(p.market_value) for p in fx_positions if not p.is_long)

    # Shorthand method: 8% of greater of sum of longs or sum of shorts
    net_open_position = max(long_total, short_total)

    rw = SIMPLIFIED_RISK_WEIGHTS[InstrumentType.FOREIGN_EXCHANGE]["general_risk"]
    total_charge = net_open_position * rw

    return {
        "total_charge": total_charge,
        "net_open_position": net_open_position,
        "long_total": long_total,
        "short_total": short_total,
        "risk_weight": rw,
    }


def calculate_commodity_charge(positions: List[SimplifiedPosition]) -> Dict:
    """
    Calculate commodity risk charge under simplified SA.

    Args:
        positions: List of commodity positions

    Returns:
        Dict with charge breakdown
    """
    com_positions = [p for p in positions if p.instrument_type == InstrumentType.COMMODITY]

    gross_position = sum(abs(p.market_value) for p in com_positions)
    long_position = sum(p.market_value for p in com_positions if p.is_long)
    short_position = sum(abs(p.market_value) for p in com_positions if not p.is_long)
    net_position = abs(long_position - short_position)

    rw = SIMPLIFIED_RISK_WEIGHTS[InstrumentType.COMMODITY]

    # Directional risk on net, basis risk on gross
    directional_charge = net_position * rw["directional_risk"]
    basis_charge = gross_position * rw["basis_risk"]

    total_charge = directional_charge + basis_charge

    return {
        "total_charge": total_charge,
        "directional_charge": directional_charge,
        "basis_charge": basis_charge,
        "net_position": net_position,
        "gross_position": gross_position,
    }


def calculate_option_charge(positions: List[SimplifiedPosition]) -> Dict:
    """
    Calculate option risk charge using delta-plus method.

    Args:
        positions: List of option positions with greeks

    Returns:
        Dict with charge breakdown
    """
    opt_positions = [p for p in positions if p.instrument_type == InstrumentType.OPTION]

    delta_equivalent = 0
    gamma_charge = 0
    vega_charge = 0

    for pos in opt_positions:
        if pos.delta is not None:
            delta_equivalent += pos.notional * pos.delta

        if pos.gamma is not None:
            # Gamma charge: 0.5 * gamma * (underlying price change)^2
            assumed_move = pos.notional * 0.08  # 8% assumed move
            gamma_charge += abs(0.5 * pos.gamma * assumed_move ** 2)

        if pos.vega is not None:
            # Vega charge: 25% volatility shift
            vega_charge += abs(pos.vega * 0.25)

    total_charge = abs(delta_equivalent) * 0.08 + gamma_charge + vega_charge

    return {
        "total_charge": total_charge,
        "delta_equivalent": delta_equivalent,
        "delta_charge": abs(delta_equivalent) * 0.08,
        "gamma_charge": gamma_charge,
        "vega_charge": vega_charge,
    }


def calculate_simplified_sa_capital(
    positions: List[SimplifiedPosition],
    include_options: bool = True,
) -> Dict:
    """
    Calculate total market risk capital under Simplified SA.

    Args:
        positions: List of all trading book positions
        include_options: Whether to include delta-plus for options

    Returns:
        Dict with total capital and breakdown
    """
    # Calculate charges by risk type
    ir_result = calculate_interest_rate_charge(positions)
    eq_result = calculate_equity_charge(positions)
    fx_result = calculate_fx_charge(positions)
    com_result = calculate_commodity_charge(positions)

    total_capital = (
        ir_result["total_charge"] +
        eq_result["total_charge"] +
        fx_result["total_charge"] +
        com_result["total_charge"]
    )

    opt_result = None
    if include_options:
        opt_result = calculate_option_charge(positions)
        total_capital += opt_result["total_charge"]

    return {
        "total_capital": total_capital,
        "interest_rate": ir_result,
        "equity": eq_result,
        "foreign_exchange": fx_result,
        "commodity": com_result,
        "options": opt_result,
    }


def calculate_de_minimis_exemption(
    total_assets: float,
    trading_book_assets: float,
    derivative_notional: float,
) -> Dict:
    """
    Check de minimis exemption for very small trading books.

    Banks may be exempt from market risk capital if:
    - Trading book < 5% of total assets AND < EUR 15mn (de minimis)
    - May use banking book treatment instead

    Args:
        total_assets: Total on-balance sheet assets
        trading_book_assets: Total trading book assets
        derivative_notional: Total derivative notional

    Returns:
        Dict with exemption result
    """
    trading_ratio = trading_book_assets / total_assets if total_assets > 0 else 0

    DE_MINIMIS_RATIO = 0.05
    DE_MINIMIS_ABSOLUTE = 15e6  # EUR 15 million

    ratio_met = trading_ratio < DE_MINIMIS_RATIO
    absolute_met = trading_book_assets < DE_MINIMIS_ABSOLUTE

    # Both conditions must be met for de minimis exemption
    is_exempt = ratio_met and absolute_met

    return {
        "is_exempt": is_exempt,
        "trading_ratio": trading_ratio,
        "trading_book_assets": trading_book_assets,
        "ratio_threshold": DE_MINIMIS_RATIO,
        "absolute_threshold": DE_MINIMIS_ABSOLUTE,
        "conditions_met": {
            "ratio": ratio_met,
            "absolute": absolute_met,
        },
        "treatment": "Banking book (credit risk)" if is_exempt else "Trading book (market risk)",
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("SIMPLIFIED STANDARDISED APPROACH FOR MARKET RISK - EXAMPLE")
    print("=" * 70)

    # Check eligibility
    print("\n1. ELIGIBILITY CHECK")
    print("-" * 40)

    eligibility = check_simplified_sa_eligibility(
        total_assets=2_000_000_000,      # EUR 2 billion total
        trading_book_assets=40_000_000,  # EUR 40 million trading
        derivative_notional=20_000_000,  # EUR 20 million derivatives
    )

    print(f"Trading Book Ratio: {eligibility['trading_book_ratio']:.2%}")
    print(f"Trading Book Absolute: EUR {eligibility['trading_book_absolute']:,.0f}")
    print(f"Eligible for Simplified SA: {eligibility['is_eligible']}")

    # Check de minimis
    print("\n2. DE MINIMIS EXEMPTION CHECK")
    print("-" * 40)

    de_minimis = calculate_de_minimis_exemption(
        total_assets=500_000_000,
        trading_book_assets=10_000_000,
        derivative_notional=5_000_000,
    )

    print(f"Trading Ratio: {de_minimis['trading_ratio']:.2%}")
    print(f"Trading Book: EUR {de_minimis['trading_book_assets']:,.0f}")
    print(f"Exempt from Market Risk Capital: {de_minimis['is_exempt']}")
    print(f"Treatment: {de_minimis['treatment']}")

    # Sample positions
    print("\n3. SIMPLIFIED SA CAPITAL CALCULATION")
    print("-" * 40)

    positions = [
        # Interest rate positions
        SimplifiedPosition(InstrumentType.INTEREST_RATE, 10_000_000, 10_100_000,
                          residual_maturity=0.5, is_long=True),
        SimplifiedPosition(InstrumentType.INTEREST_RATE, 8_000_000, 8_050_000,
                          residual_maturity=3, is_long=True),
        SimplifiedPosition(InstrumentType.INTEREST_RATE, 5_000_000, 4_900_000,
                          residual_maturity=7, is_long=False),

        # Equity positions
        SimplifiedPosition(InstrumentType.EQUITY, 2_000_000, 2_100_000, is_long=True),
        SimplifiedPosition(InstrumentType.EQUITY, 1_000_000, 950_000, is_long=False),

        # FX positions
        SimplifiedPosition(InstrumentType.FOREIGN_EXCHANGE, 5_000_000, 5_000_000, is_long=True),
        SimplifiedPosition(InstrumentType.FOREIGN_EXCHANGE, 3_000_000, 3_000_000, is_long=False),

        # Commodity positions
        SimplifiedPosition(InstrumentType.COMMODITY, 1_000_000, 1_050_000, is_long=True),

        # Options
        SimplifiedPosition(InstrumentType.OPTION, 2_000_000, 100_000,
                          delta=0.5, gamma=0.02, vega=5_000),
    ]

    result = calculate_simplified_sa_capital(positions)

    print(f"\nInterest Rate Risk Charge: EUR {result['interest_rate']['total_charge']:,.0f}")
    print(f"Equity Risk Charge: EUR {result['equity']['total_charge']:,.0f}")
    print(f"FX Risk Charge: EUR {result['foreign_exchange']['total_charge']:,.0f}")
    print(f"Commodity Risk Charge: EUR {result['commodity']['total_charge']:,.0f}")
    print(f"Option Risk Charge: EUR {result['options']['total_charge']:,.0f}")
    print(f"\nTOTAL MARKET RISK CAPITAL: EUR {result['total_capital']:,.0f}")

    # Detailed breakdown
    print("\n4. DETAILED BREAKDOWN")
    print("-" * 40)

    print("\nInterest Rate by Maturity Bucket:")
    for bucket, charge in result['interest_rate']['bucket_charges'].items():
        print(f"  {bucket}: EUR {charge:,.0f}")

    print(f"\nEquity Breakdown:")
    print(f"  Specific Risk: EUR {result['equity']['specific_risk_charge']:,.0f}")
    print(f"  General Risk: EUR {result['equity']['general_risk_charge']:,.0f}")

    print(f"\nOption Greeks:")
    print(f"  Delta Equivalent: EUR {result['options']['delta_equivalent']:,.0f}")
    print(f"  Delta Charge: EUR {result['options']['delta_charge']:,.0f}")
    print(f"  Gamma Charge: EUR {result['options']['gamma_charge']:,.0f}")
    print(f"  Vega Charge: EUR {result['options']['vega_charge']:,.0f}")
