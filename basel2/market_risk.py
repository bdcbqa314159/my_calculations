"""
Basel II Market Risk Capital Requirements

Implements the Basel II (1996 Amendment) market risk framework:
1. Standardised Measurement Method (SMM)
2. Internal Models Approach (IMA) based on VaR

Key differences from Basel III/FRTB:
- Basel II uses VaR (10-day, 99%) vs Expected Shortfall
- Basel II has simpler add-on structure
- No Sensitivities-Based Method (SbM)
- No Default Risk Charge as separate component
- Specific risk charges instead of residual risk add-on
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =============================================================================
# Standardised Measurement Method (SMM)
# =============================================================================

# Interest Rate Risk - Specific Risk Charges (Para 709-718)
IR_SPECIFIC_RISK = {
    # Government securities
    "government_aaa_aa": 0.00,
    "government_a_bbb": 0.0025,  # 0.25% (residual maturity <= 6m)
    "government_a_bbb_6m_24m": 0.01,  # 1.00%
    "government_a_bbb_over_24m": 0.016,  # 1.60%
    "government_bb_b": 0.08,  # 8%
    "government_below_b": 0.12,  # 12%
    "government_unrated": 0.08,  # 8%
    # Qualifying securities (rated investment grade)
    "qualifying_up_to_6m": 0.0025,
    "qualifying_6m_24m": 0.01,
    "qualifying_over_24m": 0.016,
    # Other
    "other": 0.08,  # 8%
}

# Interest Rate Risk - General Risk (Maturity Method) - Para 718
# Time bands and risk weights
IR_MATURITY_BANDS = [
    # (time_band, risk_weight, zone)
    ("up_to_1m", 0.0000, 1),
    ("1m_3m", 0.0020, 1),
    ("3m_6m", 0.0040, 1),
    ("6m_12m", 0.0070, 1),
    ("1y_2y", 0.0125, 2),
    ("2y_3y", 0.0175, 2),
    ("3y_4y", 0.0225, 2),
    ("4y_5y", 0.0275, 3),
    ("5y_7y", 0.0325, 3),
    ("7y_10y", 0.0375, 3),
    ("10y_15y", 0.0450, 3),
    ("15y_20y", 0.0525, 3),
    ("over_20y", 0.0600, 3),
]

# Equity Risk (Para 718)
EQUITY_SPECIFIC_RISK = 0.08  # 8% for specific risk
EQUITY_GENERAL_RISK = 0.08  # 8% for general market risk

# Foreign Exchange Risk (Para 718)
FX_RISK_WEIGHT = 0.08  # 8% of net open position

# Commodity Risk (Para 718)
COMMODITY_RISK_WEIGHT = 0.15  # 15% (simplified approach)
COMMODITY_DIRECTIONAL_RISK = 0.03  # 3% for basis risk


class AssetClass(Enum):
    INTEREST_RATE = "interest_rate"
    EQUITY = "equity"
    FOREIGN_EXCHANGE = "fx"
    COMMODITY = "commodity"


@dataclass
class MarketRiskPosition:
    """A trading book position for market risk calculation."""
    asset_class: AssetClass
    instrument_type: str  # e.g., "government_bond", "corporate_bond", "equity", "fx_spot"
    notional: float
    market_value: float
    is_long: bool
    rating: str = "unrated"
    residual_maturity: float = 1.0  # years
    currency: str = "USD"
    issuer: str = None


# =============================================================================
# Interest Rate Risk
# =============================================================================

def calculate_ir_specific_risk(
    positions: list[MarketRiskPosition]
) -> dict:
    """
    Calculate specific risk charge for interest rate positions.

    Specific risk covers issuer-specific factors (credit spread risk).
    """
    total_charge = 0
    position_details = []

    for pos in positions:
        if pos.asset_class != AssetClass.INTEREST_RATE:
            continue

        # Determine specific risk weight based on issuer type and rating
        if "government" in pos.instrument_type.lower():
            if pos.rating in ["AAA", "AA+", "AA", "AA-"]:
                rw = IR_SPECIFIC_RISK["government_aaa_aa"]
            elif pos.rating in ["A+", "A", "A-", "BBB+", "BBB", "BBB-"]:
                if pos.residual_maturity <= 0.5:
                    rw = IR_SPECIFIC_RISK["government_a_bbb"]
                elif pos.residual_maturity <= 2:
                    rw = IR_SPECIFIC_RISK["government_a_bbb_6m_24m"]
                else:
                    rw = IR_SPECIFIC_RISK["government_a_bbb_over_24m"]
            elif pos.rating in ["BB+", "BB", "BB-", "B+", "B", "B-"]:
                rw = IR_SPECIFIC_RISK["government_bb_b"]
            elif pos.rating.startswith("below") or pos.rating in ["CCC", "CC", "C", "D"]:
                rw = IR_SPECIFIC_RISK["government_below_b"]
            else:
                rw = IR_SPECIFIC_RISK["government_unrated"]
        elif pos.rating in ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"]:
            # Qualifying securities
            if pos.residual_maturity <= 0.5:
                rw = IR_SPECIFIC_RISK["qualifying_up_to_6m"]
            elif pos.residual_maturity <= 2:
                rw = IR_SPECIFIC_RISK["qualifying_6m_24m"]
            else:
                rw = IR_SPECIFIC_RISK["qualifying_over_24m"]
        else:
            rw = IR_SPECIFIC_RISK["other"]

        charge = abs(pos.market_value) * rw
        total_charge += charge

        position_details.append({
            "instrument": pos.instrument_type,
            "market_value": pos.market_value,
            "rating": pos.rating,
            "maturity": pos.residual_maturity,
            "risk_weight": rw,
            "charge": charge,
        })

    return {
        "specific_risk_charge": total_charge,
        "positions": position_details,
    }


def calculate_ir_general_risk(
    positions: list[MarketRiskPosition],
    method: str = "maturity"
) -> dict:
    """
    Calculate general market risk for interest rate positions.

    Uses the maturity method (Para 718) which slots positions into
    time bands and applies risk weights.
    """
    # Initialize time band positions
    band_positions = {band[0]: {"long": 0, "short": 0, "weight": band[1], "zone": band[2]}
                      for band in IR_MATURITY_BANDS}

    # Slot positions into bands
    for pos in positions:
        if pos.asset_class != AssetClass.INTEREST_RATE:
            continue

        # Determine time band based on maturity
        mat = pos.residual_maturity
        if mat <= 1/12:
            band = "up_to_1m"
        elif mat <= 3/12:
            band = "1m_3m"
        elif mat <= 6/12:
            band = "3m_6m"
        elif mat <= 1:
            band = "6m_12m"
        elif mat <= 2:
            band = "1y_2y"
        elif mat <= 3:
            band = "2y_3y"
        elif mat <= 4:
            band = "3y_4y"
        elif mat <= 5:
            band = "4y_5y"
        elif mat <= 7:
            band = "5y_7y"
        elif mat <= 10:
            band = "7y_10y"
        elif mat <= 15:
            band = "10y_15y"
        elif mat <= 20:
            band = "15y_20y"
        else:
            band = "over_20y"

        weighted_pos = pos.market_value * band_positions[band]["weight"]
        if pos.is_long:
            band_positions[band]["long"] += weighted_pos
        else:
            band_positions[band]["short"] += abs(weighted_pos)

    # Calculate net and matched positions per band
    band_net = {}
    total_matched = 0

    for band, data in band_positions.items():
        matched = min(data["long"], data["short"])
        net = abs(data["long"] - data["short"])
        total_matched += matched
        band_net[band] = net

    # Zone matching (10% for zone 1, 30% for zone 2, 30% for zone 3)
    zone_totals = {1: 0, 2: 0, 3: 0}
    for band, data in band_positions.items():
        net = band_net[band]
        zone_totals[data["zone"]] += net

    # Adjacent zone matching (40%)
    adjacent_zone_matched = min(zone_totals[1], zone_totals[2]) * 0.40
    adjacent_zone_matched += min(zone_totals[2], zone_totals[3]) * 0.40

    # Calculate total charge
    # Vertical disallowance (10% of matched in each band)
    vertical_charge = total_matched * 0.10

    # Horizontal disallowance within zones
    zone_charges = {
        1: total_matched * 0.10,  # Zone 1: 10%
        2: total_matched * 0.30,  # Zone 2: 30%
        3: total_matched * 0.30,  # Zone 3: 30%
    }

    # Net open position
    net_open = sum(zone_totals.values())

    total_charge = vertical_charge + sum(zone_charges.values()) + net_open

    return {
        "method": method,
        "general_risk_charge": total_charge,
        "vertical_disallowance": vertical_charge,
        "zone_charges": zone_charges,
        "net_open_position": net_open,
        "band_positions": band_positions,
    }


# =============================================================================
# Equity Risk
# =============================================================================

def calculate_equity_risk(
    positions: list[MarketRiskPosition]
) -> dict:
    """
    Calculate equity risk charge (specific + general).

    Specific risk: 8% per position (4% if liquid diversified portfolio)
    General risk: 8% of net position per market
    """
    markets = {}

    for pos in positions:
        if pos.asset_class != AssetClass.EQUITY:
            continue

        market = pos.currency  # Use currency as proxy for market

        if market not in markets:
            markets[market] = {
                "gross_long": 0,
                "gross_short": 0,
                "positions": [],
            }

        mv = abs(pos.market_value)
        if pos.is_long:
            markets[market]["gross_long"] += mv
        else:
            markets[market]["gross_short"] += mv

        markets[market]["positions"].append({
            "issuer": pos.issuer,
            "market_value": pos.market_value,
            "is_long": pos.is_long,
        })

    # Calculate charges
    total_specific = 0
    total_general = 0

    for market, data in markets.items():
        # Specific risk: 8% of gross positions
        gross = data["gross_long"] + data["gross_short"]
        specific = gross * EQUITY_SPECIFIC_RISK
        total_specific += specific

        # General risk: 8% of net position
        net = abs(data["gross_long"] - data["gross_short"])
        general = net * EQUITY_GENERAL_RISK
        total_general += general

        data["specific_risk"] = specific
        data["general_risk"] = general
        data["net_position"] = net

    return {
        "specific_risk_charge": total_specific,
        "general_risk_charge": total_general,
        "total_equity_risk": total_specific + total_general,
        "markets": markets,
    }


# =============================================================================
# Foreign Exchange Risk
# =============================================================================

def calculate_fx_risk(
    positions: list[MarketRiskPosition],
    base_currency: str = "USD"
) -> dict:
    """
    Calculate FX risk charge.

    Charge = 8% of max(sum of net long positions, sum of net short positions) + gold
    """
    currency_positions = {}

    for pos in positions:
        if pos.asset_class != AssetClass.FOREIGN_EXCHANGE:
            continue

        ccy = pos.currency
        if ccy == base_currency:
            continue

        if ccy not in currency_positions:
            currency_positions[ccy] = 0

        if pos.is_long:
            currency_positions[ccy] += pos.market_value
        else:
            currency_positions[ccy] -= pos.market_value

    # Calculate net long and short totals
    net_long = sum(p for p in currency_positions.values() if p > 0)
    net_short = abs(sum(p for p in currency_positions.values() if p < 0))

    # Shorthand method: 8% of larger of net long/short
    net_open = max(net_long, net_short)
    charge = net_open * FX_RISK_WEIGHT

    return {
        "fx_risk_charge": charge,
        "net_long_positions": net_long,
        "net_short_positions": net_short,
        "net_open_position": net_open,
        "currency_positions": currency_positions,
    }


# =============================================================================
# Commodity Risk
# =============================================================================

def calculate_commodity_risk(
    positions: list[MarketRiskPosition],
    method: str = "simplified"
) -> dict:
    """
    Calculate commodity risk charge.

    Simplified approach: 15% of net position + 3% of gross for basis risk
    """
    commodity_positions = {}

    for pos in positions:
        if pos.asset_class != AssetClass.COMMODITY:
            continue

        commodity = pos.instrument_type

        if commodity not in commodity_positions:
            commodity_positions[commodity] = {"long": 0, "short": 0}

        if pos.is_long:
            commodity_positions[commodity]["long"] += abs(pos.market_value)
        else:
            commodity_positions[commodity]["short"] += abs(pos.market_value)

    # Calculate charges
    total_directional = 0
    total_basis = 0

    for commodity, data in commodity_positions.items():
        net = abs(data["long"] - data["short"])
        gross = data["long"] + data["short"]

        directional = net * COMMODITY_RISK_WEIGHT
        basis = gross * COMMODITY_DIRECTIONAL_RISK

        total_directional += directional
        total_basis += basis

        data["net"] = net
        data["gross"] = gross
        data["directional_charge"] = directional
        data["basis_charge"] = basis

    return {
        "directional_risk_charge": total_directional,
        "basis_risk_charge": total_basis,
        "total_commodity_risk": total_directional + total_basis,
        "commodities": commodity_positions,
    }


# =============================================================================
# Total SMM Capital
# =============================================================================

def calculate_smm_capital(
    positions: list[MarketRiskPosition],
    base_currency: str = "USD"
) -> dict:
    """
    Calculate total Standardised Measurement Method capital.

    Total = IR Specific + IR General + Equity + FX + Commodity
    """
    ir_positions = [p for p in positions if p.asset_class == AssetClass.INTEREST_RATE]
    eq_positions = [p for p in positions if p.asset_class == AssetClass.EQUITY]
    fx_positions = [p for p in positions if p.asset_class == AssetClass.FOREIGN_EXCHANGE]
    com_positions = [p for p in positions if p.asset_class == AssetClass.COMMODITY]

    ir_specific = calculate_ir_specific_risk(ir_positions)
    ir_general = calculate_ir_general_risk(ir_positions)
    equity = calculate_equity_risk(eq_positions)
    fx = calculate_fx_risk(fx_positions, base_currency)
    commodity = calculate_commodity_risk(com_positions)

    total_capital = (
        ir_specific["specific_risk_charge"] +
        ir_general["general_risk_charge"] +
        equity["total_equity_risk"] +
        fx["fx_risk_charge"] +
        commodity["total_commodity_risk"]
    )

    return {
        "approach": "SMM",
        "interest_rate": {
            "specific_risk": ir_specific["specific_risk_charge"],
            "general_risk": ir_general["general_risk_charge"],
            "total": ir_specific["specific_risk_charge"] + ir_general["general_risk_charge"],
        },
        "equity": equity,
        "fx": fx,
        "commodity": commodity,
        "total_capital": total_capital,
        "rwa": total_capital * 12.5,
    }


# =============================================================================
# Internal Models Approach (IMA) - VaR Based
# =============================================================================

def calculate_var_capital(
    var_10day_99: float,
    stressed_var_10day_99: float = None,
    specific_risk_var: float = 0,
    multiplication_factor: float = 3.0,
    plus_factor: float = 0.0
) -> dict:
    """
    Calculate market risk capital using Internal Models Approach (VaR-based).

    Capital = max(VaR_t-1, mc × avg(VaR_60days)) + max(sVaR_t-1, ms × avg(sVaR_60days))
             + Specific Risk Charge

    Parameters:
    -----------
    var_10day_99 : float
        10-day 99% VaR (current)
    stressed_var_10day_99 : float
        10-day 99% Stressed VaR (if applicable, Basel 2.5 addition)
    specific_risk_var : float
        Incremental specific risk charge
    multiplication_factor : float
        Base multiplier (minimum 3)
    plus_factor : float
        Regulatory add-on based on backtesting (0 to 1)

    Returns:
    --------
    dict
        IMA capital calculation
    """
    # Total multiplication factor
    mc = multiplication_factor + plus_factor

    # General market risk
    general_risk = mc * var_10day_99

    # Stressed VaR (Basel 2.5 addition)
    if stressed_var_10day_99:
        stressed_component = mc * stressed_var_10day_99
    else:
        stressed_component = 0

    # Total capital
    total_capital = general_risk + stressed_component + specific_risk_var

    return {
        "approach": "IMA (VaR)",
        "var_10day_99": var_10day_99,
        "stressed_var_10day_99": stressed_var_10day_99,
        "multiplication_factor": multiplication_factor,
        "plus_factor": plus_factor,
        "total_multiplier": mc,
        "general_risk_charge": general_risk,
        "stressed_risk_charge": stressed_component,
        "specific_risk_charge": specific_risk_var,
        "total_capital": total_capital,
        "rwa": total_capital * 12.5,
    }


def calculate_specific_risk(
    positions: list[MarketRiskPosition]
) -> dict:
    """Calculate specific risk component for IMA banks."""
    ir_specific = calculate_ir_specific_risk(
        [p for p in positions if p.asset_class == AssetClass.INTEREST_RATE]
    )
    eq_specific = calculate_equity_risk(
        [p for p in positions if p.asset_class == AssetClass.EQUITY]
    )

    return {
        "ir_specific_risk": ir_specific["specific_risk_charge"],
        "equity_specific_risk": eq_specific["specific_risk_charge"],
        "total_specific_risk": ir_specific["specific_risk_charge"] + eq_specific["specific_risk_charge"],
    }


def calculate_general_risk(
    positions: list[MarketRiskPosition]
) -> dict:
    """Calculate general market risk component."""
    ir_general = calculate_ir_general_risk(
        [p for p in positions if p.asset_class == AssetClass.INTEREST_RATE]
    )
    eq = calculate_equity_risk(
        [p for p in positions if p.asset_class == AssetClass.EQUITY]
    )
    fx = calculate_fx_risk(
        [p for p in positions if p.asset_class == AssetClass.FOREIGN_EXCHANGE]
    )
    com = calculate_commodity_risk(
        [p for p in positions if p.asset_class == AssetClass.COMMODITY]
    )

    return {
        "ir_general_risk": ir_general["general_risk_charge"],
        "equity_general_risk": eq["general_risk_charge"],
        "fx_risk": fx["fx_risk_charge"],
        "commodity_risk": com["total_commodity_risk"],
        "total_general_risk": (
            ir_general["general_risk_charge"] +
            eq["general_risk_charge"] +
            fx["fx_risk_charge"] +
            com["total_commodity_risk"]
        ),
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Market Risk")
    print("=" * 70)

    # Sample positions
    positions = [
        MarketRiskPosition(AssetClass.INTEREST_RATE, "government_bond", 10_000_000, 10_200_000,
                           True, "AA", 5.0, "USD"),
        MarketRiskPosition(AssetClass.INTEREST_RATE, "corporate_bond", 5_000_000, 4_800_000,
                           True, "BBB", 3.0, "USD"),
        MarketRiskPosition(AssetClass.EQUITY, "stock", 2_000_000, 2_100_000,
                           True, "NR", 0, "USD", "AAPL"),
        MarketRiskPosition(AssetClass.EQUITY, "stock", 1_500_000, 1_400_000,
                           False, "NR", 0, "USD", "MSFT"),
        MarketRiskPosition(AssetClass.FOREIGN_EXCHANGE, "fx_spot", 3_000_000, 3_000_000,
                           True, "NR", 0, "EUR"),
        MarketRiskPosition(AssetClass.COMMODITY, "oil", 1_000_000, 1_050_000,
                           True, "NR", 0, "USD"),
    ]

    # SMM calculation
    smm = calculate_smm_capital(positions)

    print("\n  Standardised Measurement Method (SMM):")
    print(f"\n  {'Risk Category':<20} {'Capital':>15}")
    print(f"  {'-'*20} {'-'*15}")
    print(f"  {'IR Specific':<20} ${smm['interest_rate']['specific_risk']:>13,.0f}")
    print(f"  {'IR General':<20} ${smm['interest_rate']['general_risk']:>13,.0f}")
    print(f"  {'Equity':<20} ${smm['equity']['total_equity_risk']:>13,.0f}")
    print(f"  {'FX':<20} ${smm['fx']['fx_risk_charge']:>13,.0f}")
    print(f"  {'Commodity':<20} ${smm['commodity']['total_commodity_risk']:>13,.0f}")
    print(f"  {'-'*20} {'-'*15}")
    print(f"  {'Total':<20} ${smm['total_capital']:>13,.0f}")
    print(f"  {'RWA':<20} ${smm['rwa']:>13,.0f}")

    # VaR calculation
    print("\n  Internal Models Approach (VaR):")
    var_result = calculate_var_capital(
        var_10day_99=5_000_000,
        stressed_var_10day_99=8_000_000,
        specific_risk_var=500_000,
        multiplication_factor=3.0,
        plus_factor=0.5
    )
    print(f"  VaR (10-day, 99%): ${var_result['var_10day_99']:,.0f}")
    print(f"  Stressed VaR: ${var_result['stressed_var_10day_99']:,.0f}")
    print(f"  Multiplier: {var_result['total_multiplier']:.1f}x")
    print(f"  Total Capital: ${var_result['total_capital']:,.0f}")
    print(f"  RWA: ${var_result['rwa']:,.0f}")
