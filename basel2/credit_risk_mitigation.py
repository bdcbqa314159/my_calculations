"""
Basel II Credit Risk Mitigation (CRM) Framework

Implements the Basel II CRM techniques:
1. Simple Approach: Collateral substitutes exposure RW
2. Comprehensive Approach: Collateral reduces exposure with haircuts
3. On-balance sheet netting
4. Guarantees and credit derivatives

Para 117-210 of Basel II framework.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =============================================================================
# Collateral Types and Eligibility (Para 145-154)
# =============================================================================

class CollateralType(Enum):
    """Eligible financial collateral types."""
    CASH = "cash"
    GOLD = "gold"
    DEBT_SECURITIES_SOVEREIGN = "debt_sovereign"  # Rated BB- or better
    DEBT_SECURITIES_PSE = "debt_pse"
    DEBT_SECURITIES_BANK = "debt_bank"  # Rated BBB- or better
    DEBT_SECURITIES_CORPORATE = "debt_corporate"  # Rated BBB- or better
    DEBT_SECURITIES_SECURITIZATION = "debt_securitization"  # Rated BBB- or better
    EQUITY_MAIN_INDEX = "equity_main_index"
    EQUITY_RECOGNIZED_EXCHANGE = "equity_exchange"
    UCITS_MUTUAL_FUND = "ucits"
    # For IRB only (Para 289):
    RECEIVABLES = "receivables"
    COMMERCIAL_REAL_ESTATE = "cre"
    RESIDENTIAL_REAL_ESTATE = "rre"
    OTHER_PHYSICAL = "other_physical"


# =============================================================================
# Simple Approach (Para 180-181) - SA banks only
# =============================================================================

# Simple approach risk weight floor
SIMPLE_APPROACH_FLOOR = 20  # 20% floor for most collateral

SIMPLE_APPROACH_RW = {
    CollateralType.CASH: 0,
    CollateralType.GOLD: 0,
    CollateralType.DEBT_SECURITIES_SOVEREIGN: 0,  # If rated AAA to AA-
    CollateralType.DEBT_SECURITIES_PSE: 20,
    CollateralType.DEBT_SECURITIES_BANK: 20,
    CollateralType.DEBT_SECURITIES_CORPORATE: 20,
    CollateralType.EQUITY_MAIN_INDEX: 20,
    CollateralType.EQUITY_RECOGNIZED_EXCHANGE: 20,
}


def calculate_simple_approach_rwa(
    ead: float,
    exposure_rw: float,
    collateral_type: CollateralType,
    collateral_value: float,
    collateral_rating: str = "unrated"
) -> dict:
    """
    Calculate RWA using Simple Approach for CRM.

    The collateral's risk weight substitutes for the exposure's RW
    for the collateralized portion.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_rw : float
        Risk weight of the exposure (%)
    collateral_type : CollateralType
        Type of collateral
    collateral_value : float
        Value of collateral
    collateral_rating : str
        Rating of debt collateral

    Returns:
    --------
    dict
        CRM calculation results
    """
    # Determine collateral risk weight
    if collateral_type == CollateralType.CASH:
        collateral_rw = 0
    elif collateral_type == CollateralType.GOLD:
        collateral_rw = 0
    elif collateral_type == CollateralType.DEBT_SECURITIES_SOVEREIGN:
        if collateral_rating in ["AAA", "AA+", "AA", "AA-"]:
            collateral_rw = 0
        else:
            collateral_rw = SIMPLE_APPROACH_FLOOR
    else:
        collateral_rw = SIMPLE_APPROACH_RW.get(collateral_type, SIMPLE_APPROACH_FLOOR)

    # Apply floor
    collateral_rw = max(collateral_rw, SIMPLE_APPROACH_FLOOR)

    # Calculate portions
    collateralized = min(collateral_value, ead)
    uncollateralized = ead - collateralized

    # RWA
    rwa_collateralized = collateralized * collateral_rw / 100
    rwa_uncollateralized = uncollateralized * exposure_rw / 100
    total_rwa = rwa_collateralized + rwa_uncollateralized

    return {
        "approach": "Simple",
        "ead": ead,
        "exposure_rw": exposure_rw,
        "collateral_type": collateral_type.value,
        "collateral_value": collateral_value,
        "collateral_rw": collateral_rw,
        "collateralized_portion": collateralized,
        "uncollateralized_portion": uncollateralized,
        "rwa_collateralized": rwa_collateralized,
        "rwa_uncollateralized": rwa_uncollateralized,
        "total_rwa": total_rwa,
        "rwa_without_crm": ead * exposure_rw / 100,
        "rwa_reduction": (ead * exposure_rw / 100) - total_rwa,
    }


# =============================================================================
# Comprehensive Approach - Supervisory Haircuts (Para 147-150)
# =============================================================================

# Standard supervisory haircuts for 10-business-day holding period
# Based on residual maturity and issuer type
SUPERVISORY_HAIRCUTS = {
    # Cash and gold
    CollateralType.CASH: {"any": 0.00},
    CollateralType.GOLD: {"any": 0.15},

    # Sovereign debt (AAA to AA-)
    "sovereign_aaa_aa": {
        "up_to_1y": 0.005,
        "1y_5y": 0.02,
        "over_5y": 0.04,
    },
    # Sovereign debt (A+ to BBB-)
    "sovereign_a_bbb": {
        "up_to_1y": 0.01,
        "1y_5y": 0.03,
        "over_5y": 0.06,
    },
    # Sovereign debt (BB+ to BB-)
    "sovereign_bb": {
        "up_to_1y": 0.15,
        "1y_5y": 0.15,
        "over_5y": 0.15,
    },

    # Bank/Corporate debt (AAA to AA-)
    "bank_corp_aaa_aa": {
        "up_to_1y": 0.01,
        "1y_5y": 0.04,
        "over_5y": 0.08,
    },
    # Bank/Corporate debt (A+ to BBB-)
    "bank_corp_a_bbb": {
        "up_to_1y": 0.02,
        "1y_5y": 0.06,
        "over_5y": 0.12,
    },

    # Securitization tranches (AAA to AA-)
    "securitization_aaa_aa": {
        "up_to_1y": 0.02,
        "1y_5y": 0.08,
        "over_5y": 0.16,
    },

    # Main index equities
    CollateralType.EQUITY_MAIN_INDEX: {"any": 0.15},

    # Other exchange-traded equities
    CollateralType.EQUITY_RECOGNIZED_EXCHANGE: {"any": 0.25},

    # UCITS/Mutual funds
    CollateralType.UCITS_MUTUAL_FUND: {"any": 0.25},  # Highest haircut of underlying

    # Currency mismatch add-on
    "currency_mismatch": 0.08,
}

# FX haircut for currency mismatch
FX_HAIRCUT = 0.08


def get_maturity_bucket(residual_maturity: float) -> str:
    """Get maturity bucket for haircut lookup."""
    if residual_maturity <= 1:
        return "up_to_1y"
    elif residual_maturity <= 5:
        return "1y_5y"
    else:
        return "over_5y"


def get_supervisory_haircut(
    collateral_type: CollateralType,
    rating: str = "unrated",
    residual_maturity: float = 1.0,
    is_sovereign: bool = False
) -> float:
    """
    Get supervisory haircut for collateral.

    Parameters:
    -----------
    collateral_type : CollateralType
        Type of collateral
    rating : str
        Credit rating of collateral
    residual_maturity : float
        Residual maturity in years
    is_sovereign : bool
        Whether issuer is sovereign

    Returns:
    --------
    float
        Haircut as decimal (e.g., 0.02 for 2%)
    """
    # Cash
    if collateral_type == CollateralType.CASH:
        return 0.00

    # Gold
    if collateral_type == CollateralType.GOLD:
        return 0.15

    # Equities
    if collateral_type == CollateralType.EQUITY_MAIN_INDEX:
        return 0.15
    if collateral_type == CollateralType.EQUITY_RECOGNIZED_EXCHANGE:
        return 0.25

    # UCITS
    if collateral_type == CollateralType.UCITS_MUTUAL_FUND:
        return 0.25

    # Debt securities - determine category
    bucket = get_maturity_bucket(residual_maturity)

    if is_sovereign or collateral_type == CollateralType.DEBT_SECURITIES_SOVEREIGN:
        if rating in ["AAA", "AA+", "AA", "AA-"]:
            return SUPERVISORY_HAIRCUTS["sovereign_aaa_aa"][bucket]
        elif rating in ["A+", "A", "A-", "BBB+", "BBB", "BBB-"]:
            return SUPERVISORY_HAIRCUTS["sovereign_a_bbb"][bucket]
        elif rating in ["BB+", "BB", "BB-"]:
            return SUPERVISORY_HAIRCUTS["sovereign_bb"][bucket]
        else:
            return 0.25  # Ineligible or very low rating

    elif collateral_type == CollateralType.DEBT_SECURITIES_SECURITIZATION:
        if rating in ["AAA", "AA+", "AA", "AA-"]:
            return SUPERVISORY_HAIRCUTS["securitization_aaa_aa"][bucket]
        else:
            return 0.25  # Higher haircut or ineligible

    else:  # Bank or corporate debt
        if rating in ["AAA", "AA+", "AA", "AA-"]:
            return SUPERVISORY_HAIRCUTS["bank_corp_aaa_aa"][bucket]
        elif rating in ["A+", "A", "A-", "BBB+", "BBB", "BBB-"]:
            return SUPERVISORY_HAIRCUTS["bank_corp_a_bbb"][bucket]
        else:
            return 0.25  # Ineligible


def calculate_comprehensive_haircut(
    collateral_type: CollateralType,
    collateral_value: float,
    collateral_rating: str = "unrated",
    residual_maturity: float = 1.0,
    is_sovereign: bool = False,
    currency_mismatch: bool = False,
    holding_period_days: int = 10
) -> dict:
    """
    Calculate haircut-adjusted collateral value using Comprehensive Approach.

    Parameters:
    -----------
    collateral_type : CollateralType
        Type of collateral
    collateral_value : float
        Market value of collateral
    collateral_rating : str
        Credit rating
    residual_maturity : float
        Residual maturity in years
    is_sovereign : bool
        Sovereign issuer
    currency_mismatch : bool
        Collateral/exposure currency mismatch
    holding_period_days : int
        Holding period (default 10 days for most transactions)

    Returns:
    --------
    dict
        Haircut calculation results
    """
    # Get base haircut
    hc = get_supervisory_haircut(
        collateral_type, collateral_rating, residual_maturity, is_sovereign
    )

    # Adjust for holding period (if different from 10-day base)
    if holding_period_days != 10:
        hc = hc * math.sqrt(holding_period_days / 10)

    # Currency mismatch add-on
    hfx = FX_HAIRCUT if currency_mismatch else 0

    # Total haircut
    total_haircut = hc + hfx

    # Adjusted collateral value
    adjusted_value = collateral_value * (1 - total_haircut)

    return {
        "collateral_type": collateral_type.value,
        "collateral_value": collateral_value,
        "rating": collateral_rating,
        "residual_maturity": residual_maturity,
        "base_haircut": hc,
        "fx_haircut": hfx,
        "total_haircut": total_haircut,
        "adjusted_value": adjusted_value,
        "haircut_amount": collateral_value - adjusted_value,
    }


def calculate_exposure_with_collateral(
    ead: float,
    exposure_rw: float,
    collateral_value: float,
    collateral_type: CollateralType,
    collateral_rating: str = "unrated",
    residual_maturity: float = 1.0,
    is_sovereign: bool = False,
    currency_mismatch: bool = False,
    exposure_haircut: float = 0.0
) -> dict:
    """
    Calculate exposure after CRM using Comprehensive Approach.

    E* = max(0, [E × (1 + He) - C × (1 - Hc - Hfx)])

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_rw : float
        Risk weight of exposure (%)
    collateral_value : float
        Market value of collateral
    collateral_type : CollateralType
        Type of collateral
    collateral_rating : str
        Collateral rating
    residual_maturity : float
        Collateral residual maturity
    is_sovereign : bool
        Sovereign collateral issuer
    currency_mismatch : bool
        FX mismatch
    exposure_haircut : float
        Haircut on exposure (He) - for repos

    Returns:
    --------
    dict
        CRM calculation results
    """
    # Calculate collateral haircut
    hc_result = calculate_comprehensive_haircut(
        collateral_type, collateral_value, collateral_rating,
        residual_maturity, is_sovereign, currency_mismatch
    )

    # Exposure after haircuts
    e_adjusted = ead * (1 + exposure_haircut)
    c_adjusted = hc_result["adjusted_value"]

    # Net exposure
    e_star = max(0, e_adjusted - c_adjusted)

    # RWA
    rwa = e_star * exposure_rw / 100
    rwa_without_crm = ead * exposure_rw / 100

    return {
        "approach": "Comprehensive",
        "original_ead": ead,
        "exposure_rw": exposure_rw,
        "exposure_haircut": exposure_haircut,
        "adjusted_exposure": e_adjusted,
        "collateral": hc_result,
        "adjusted_collateral": c_adjusted,
        "exposure_after_crm": e_star,
        "rwa": rwa,
        "rwa_without_crm": rwa_without_crm,
        "rwa_reduction": rwa_without_crm - rwa,
        "rwa_reduction_pct": ((rwa_without_crm - rwa) / rwa_without_crm * 100) if rwa_without_crm > 0 else 0,
    }


# =============================================================================
# Guarantees and Credit Derivatives (Para 189-201)
# =============================================================================

def calculate_exposure_with_guarantee(
    ead: float,
    exposure_rw: float,
    guarantee_value: float,
    guarantor_rw: float,
    is_proportional: bool = True
) -> dict:
    """
    Calculate exposure with guarantee/credit derivative protection.

    The protected portion receives the guarantor's risk weight (substitution).

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_rw : float
        Obligor's risk weight (%)
    guarantee_value : float
        Value of guarantee (may be less than EAD)
    guarantor_rw : float
        Guarantor's risk weight (%)
    is_proportional : bool
        Whether to apply proportional coverage

    Returns:
    --------
    dict
        Guarantee CRM results
    """
    # Protected and unprotected portions
    protected = min(guarantee_value, ead)
    unprotected = ead - protected

    # RWA calculation
    rwa_protected = protected * guarantor_rw / 100
    rwa_unprotected = unprotected * exposure_rw / 100
    total_rwa = rwa_protected + rwa_unprotected

    rwa_without_crm = ead * exposure_rw / 100

    return {
        "approach": "Guarantee Substitution",
        "ead": ead,
        "exposure_rw": exposure_rw,
        "guarantee_value": guarantee_value,
        "guarantor_rw": guarantor_rw,
        "protected_portion": protected,
        "unprotected_portion": unprotected,
        "rwa_protected": rwa_protected,
        "rwa_unprotected": rwa_unprotected,
        "total_rwa": total_rwa,
        "rwa_without_crm": rwa_without_crm,
        "rwa_reduction": rwa_without_crm - total_rwa,
    }


# =============================================================================
# On-Balance Sheet Netting (Para 139-143)
# =============================================================================

def calculate_netting_benefit(
    loans: float,
    deposits: float,
    is_legally_enforceable: bool = True
) -> dict:
    """
    Calculate on-balance sheet netting benefit.

    Net exposure = max(0, Loans - Deposits)

    Parameters:
    -----------
    loans : float
        Total loans to counterparty
    deposits : float
        Total deposits from counterparty
    is_legally_enforceable : bool
        Whether netting is legally enforceable

    Returns:
    --------
    dict
        Netting calculation results
    """
    if not is_legally_enforceable:
        net_exposure = loans
        netting_benefit = 0
    else:
        net_exposure = max(0, loans - deposits)
        netting_benefit = loans - net_exposure

    return {
        "approach": "On-Balance Sheet Netting",
        "gross_loans": loans,
        "deposits": deposits,
        "is_legally_enforceable": is_legally_enforceable,
        "net_exposure": net_exposure,
        "netting_benefit": netting_benefit,
        "netting_ratio": netting_benefit / loans if loans > 0 else 0,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Credit Risk Mitigation")
    print("=" * 70)

    # Simple Approach
    print("\n  Simple Approach:")
    simple = calculate_simple_approach_rwa(
        ead=1_000_000,
        exposure_rw=100,
        collateral_type=CollateralType.CASH,
        collateral_value=500_000
    )
    print(f"  EAD: ${simple['ead']:,.0f}")
    print(f"  Collateral: ${simple['collateral_value']:,.0f} (Cash)")
    print(f"  RWA without CRM: ${simple['rwa_without_crm']:,.0f}")
    print(f"  RWA with CRM: ${simple['total_rwa']:,.0f}")
    print(f"  RWA Reduction: ${simple['rwa_reduction']:,.0f}")

    # Comprehensive Approach - Haircuts
    print("\n  Comprehensive Approach Haircuts:")
    print(f"\n  {'Collateral Type':<25} {'Rating':<10} {'Haircut':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10}")

    test_cases = [
        (CollateralType.CASH, "N/A", 1.0, False),
        (CollateralType.GOLD, "N/A", 1.0, False),
        (CollateralType.DEBT_SECURITIES_SOVEREIGN, "AAA", 3.0, True),
        (CollateralType.DEBT_SECURITIES_SOVEREIGN, "A", 3.0, True),
        (CollateralType.DEBT_SECURITIES_CORPORATE, "AA", 2.0, False),
        (CollateralType.EQUITY_MAIN_INDEX, "N/A", 0, False),
    ]

    for coll_type, rating, mat, is_sov in test_cases:
        hc = get_supervisory_haircut(coll_type, rating, mat, is_sov)
        print(f"  {coll_type.value:<25} {rating:<10} {hc*100:>9.1f}%")

    # Comprehensive Approach - Full Calculation
    print("\n  Comprehensive Approach - Full Calculation:")
    comp = calculate_exposure_with_collateral(
        ead=1_000_000,
        exposure_rw=100,
        collateral_value=600_000,
        collateral_type=CollateralType.DEBT_SECURITIES_SOVEREIGN,
        collateral_rating="AA",
        residual_maturity=3.0,
        is_sovereign=True,
        currency_mismatch=True
    )
    print(f"\n  Original EAD: ${comp['original_ead']:,.0f}")
    print(f"  Collateral: ${comp['collateral']['collateral_value']:,.0f}")
    print(f"  Base Haircut: {comp['collateral']['base_haircut']*100:.1f}%")
    print(f"  FX Haircut: {comp['collateral']['fx_haircut']*100:.1f}%")
    print(f"  Adjusted Collateral: ${comp['adjusted_collateral']:,.0f}")
    print(f"  Exposure after CRM: ${comp['exposure_after_crm']:,.0f}")
    print(f"  RWA: ${comp['rwa']:,.0f}")
    print(f"  RWA Reduction: {comp['rwa_reduction_pct']:.1f}%")

    # Guarantee
    print("\n  Guarantee Substitution:")
    guar = calculate_exposure_with_guarantee(
        ead=1_000_000,
        exposure_rw=100,
        guarantee_value=800_000,
        guarantor_rw=20
    )
    print(f"  EAD: ${guar['ead']:,.0f} (RW: {guar['exposure_rw']}%)")
    print(f"  Guarantee: ${guar['guarantee_value']:,.0f} (Guarantor RW: {guar['guarantor_rw']}%)")
    print(f"  RWA without guarantee: ${guar['rwa_without_crm']:,.0f}")
    print(f"  RWA with guarantee: ${guar['total_rwa']:,.0f}")
    print(f"  RWA Reduction: ${guar['rwa_reduction']:,.0f}")
