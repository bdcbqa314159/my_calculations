"""
Crypto-assets Prudential Treatment

Implements:
- Group 1a: Tokenised traditional assets
- Group 1b: Stablecoins with effective stabilisation
- Group 2a: Other crypto with hedging recognition
- Group 2b: Other crypto without hedging recognition

Reference: BCBS d545 (Prudential treatment of cryptoasset exposures)
"""

import math
from typing import Optional


# =============================================================================
# Crypto-asset Classification (SCO60)
# =============================================================================

# Group 1a: Tokenised traditional assets - same RW as underlying
# Group 1b: Stablecoins - modified treatment based on tests
# Group 2a: Crypto with hedging - 100% RW with netting
# Group 2b: Other crypto - 1250% RW

CRYPTO_GROUPS = {
    "1a": {
        "description": "Tokenised traditional assets",
        "base_rw": None,  # Same as underlying
        "leverage_add_on": 0,
    },
    "1b": {
        "description": "Stablecoins with effective stabilisation",
        "base_rw": None,  # Based on reserve assets
        "leverage_add_on": 0,
        "redemption_risk_add_on": 0.025,  # 2.5% add-on
    },
    "2a": {
        "description": "Crypto-assets with hedging recognition",
        "base_rw": 100,  # 100% minimum
        "leverage_add_on": 0,
        "hedging_recognition": True,
    },
    "2b": {
        "description": "Other crypto-assets",
        "base_rw": 1250,  # 1250%
        "leverage_add_on": 0,
        "hedging_recognition": False,
    },
}

# Group 2 exposure limit (2% of Tier 1)
GROUP2_EXPOSURE_LIMIT = 0.02
GROUP2B_EXPOSURE_LIMIT = 0.01


def classify_crypto_asset(
    is_tokenised_traditional: bool = False,
    has_effective_stabilisation: bool = False,
    passes_redemption_test: bool = False,
    passes_reserve_test: bool = False,
    infrastructure_risk_acceptable: bool = True
) -> str:
    """
    Classify a crypto-asset into Group 1a, 1b, 2a, or 2b.

    Parameters:
    -----------
    is_tokenised_traditional : bool
        Whether asset is a token representing traditional asset
    has_effective_stabilisation : bool
        Whether stablecoin has effective value stabilisation
    passes_redemption_test : bool
        Whether redemption rights are adequate
    passes_reserve_test : bool
        Whether reserve assets meet requirements
    infrastructure_risk_acceptable : bool
        Whether infrastructure/technology risk is acceptable

    Returns:
    --------
    str
        Classification ("1a", "1b", "2a", "2b")
    """
    if not infrastructure_risk_acceptable:
        return "2b"

    if is_tokenised_traditional:
        return "1a"

    if has_effective_stabilisation and passes_redemption_test and passes_reserve_test:
        return "1b"

    # Group 2 - check if hedging can be recognized
    # Simplified: if traded on regulated exchange, hedging recognized
    # For now, default to 2b (most conservative)
    return "2b"


# =============================================================================
# Group 1a: Tokenised Traditional Assets
# =============================================================================

def calculate_group1a_rwa(
    exposure: float,
    underlying_type: str,
    underlying_rw: float = None,
    underlying_rating: str = "unrated"
) -> dict:
    """
    Calculate RWA for Group 1a (tokenised traditional assets).

    Same treatment as the underlying traditional asset.

    Parameters:
    -----------
    exposure : float
        Exposure amount
    underlying_type : str
        Type of underlying ("equity", "bond", "commodity", etc.)
    underlying_rw : float, optional
        Risk weight of underlying if known
    underlying_rating : str
        Rating of underlying for RW lookup

    Returns:
    --------
    dict
        RWA calculation
    """
    # If RW not provided, use standard approach
    if underlying_rw is None:
        if underlying_type == "equity":
            underlying_rw = 250  # Equity RW
        elif underlying_type == "sovereign":
            rw_map = {"AAA": 0, "AA": 0, "A": 20, "BBB": 50, "BB": 100, "unrated": 100}
            underlying_rw = rw_map.get(underlying_rating, 100)
        elif underlying_type == "corporate":
            rw_map = {"AAA": 20, "AA": 20, "A": 50, "BBB": 75, "BB": 100, "unrated": 100}
            underlying_rw = rw_map.get(underlying_rating, 100)
        else:
            underlying_rw = 100  # Default

    # Infrastructure add-on (2.5% of exposure for operational risk)
    infrastructure_addon = exposure * 0.025

    rwa = exposure * underlying_rw / 100 + infrastructure_addon

    return {
        "group": "1a",
        "exposure": exposure,
        "underlying_type": underlying_type,
        "underlying_rw": underlying_rw,
        "infrastructure_addon": infrastructure_addon,
        "risk_weight_pct": underlying_rw,
        "rwa": rwa,
        "total_rwa_equivalent_rw": (rwa / exposure * 100) if exposure > 0 else 0,
    }


# =============================================================================
# Group 1b: Stablecoins
# =============================================================================

def assess_stabilisation_mechanism(
    reserve_composition: dict,
    redemption_frequency: str = "daily",
    peg_deviation_history: float = 0.01
) -> dict:
    """
    Assess effectiveness of stablecoin stabilisation mechanism.

    Parameters:
    -----------
    reserve_composition : dict
        {asset_type: percentage} of reserve assets
    redemption_frequency : str
        "daily", "weekly", "other"
    peg_deviation_history : float
        Historical max deviation from peg

    Returns:
    --------
    dict
        Assessment results
    """
    # Check reserve quality
    high_quality_assets = ["cash", "central_bank_reserves", "sovereign_aaa", "sovereign_aa"]
    hqla_percentage = sum(
        pct for asset, pct in reserve_composition.items()
        if asset in high_quality_assets
    )

    # Tests
    passes_reserve_test = hqla_percentage >= 0.80  # 80% in HQLA
    passes_redemption_test = redemption_frequency in ["daily", "same_day"]
    passes_stability_test = peg_deviation_history <= 0.02  # Max 2% deviation

    passes_all = passes_reserve_test and passes_redemption_test and passes_stability_test

    return {
        "hqla_percentage": hqla_percentage,
        "passes_reserve_test": passes_reserve_test,
        "passes_redemption_test": passes_redemption_test,
        "passes_stability_test": passes_stability_test,
        "qualifies_group_1b": passes_all,
    }


def calculate_group1b_rwa(
    exposure: float,
    reserve_composition: dict,
    redemption_risk_addon: float = 0.025
) -> dict:
    """
    Calculate RWA for Group 1b (stablecoins).

    RWA based on reserve assets plus redemption risk add-on.

    Parameters:
    -----------
    exposure : float
        Exposure amount
    reserve_composition : dict
        {asset_type: (percentage, risk_weight)}
    redemption_risk_addon : float
        Add-on for redemption risk (default 2.5%)

    Returns:
    --------
    dict
        RWA calculation
    """
    # Weighted average RW of reserves
    weighted_rw = 0
    for asset_type, (percentage, rw) in reserve_composition.items():
        weighted_rw += percentage * rw

    # Base RWA from reserves
    base_rwa = exposure * weighted_rw / 100

    # Redemption risk add-on
    redemption_addon = exposure * redemption_risk_addon

    # Infrastructure add-on
    infrastructure_addon = exposure * 0.025

    total_rwa = base_rwa + redemption_addon + infrastructure_addon

    return {
        "group": "1b",
        "exposure": exposure,
        "weighted_reserve_rw": weighted_rw,
        "base_rwa": base_rwa,
        "redemption_addon": redemption_addon,
        "infrastructure_addon": infrastructure_addon,
        "total_rwa": total_rwa,
        "effective_rw_pct": (total_rwa / exposure * 100) if exposure > 0 else 0,
    }


# =============================================================================
# Group 2: Unbacked Crypto-assets
# =============================================================================

def calculate_group2_rwa(
    long_exposure: float,
    short_exposure: float = 0,
    is_group_2a: bool = False,
    market_value: float = None
) -> dict:
    """
    Calculate RWA for Group 2 crypto-assets.

    Group 2a: 100% RW with netting
    Group 2b: 1250% RW, no netting

    Parameters:
    -----------
    long_exposure : float
        Long positions
    short_exposure : float
        Short positions
    is_group_2a : bool
        Whether hedging recognition applies
    market_value : float, optional
        Market value for leverage exposure

    Returns:
    --------
    dict
        RWA calculation
    """
    if market_value is None:
        market_value = long_exposure

    if is_group_2a:
        # Net exposure with hedging recognition
        net_exposure = abs(long_exposure - short_exposure)
        gross_exposure = long_exposure + short_exposure
        risk_weight = 100

        rwa = net_exposure * risk_weight / 100

        return {
            "group": "2a",
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "net_exposure": net_exposure,
            "gross_exposure": gross_exposure,
            "risk_weight_pct": risk_weight,
            "rwa": rwa,
            "hedging_benefit": (gross_exposure - net_exposure) * risk_weight / 100,
        }
    else:
        # Group 2b: gross exposure, 1250% RW
        gross_exposure = long_exposure + abs(short_exposure)
        risk_weight = 1250

        rwa = gross_exposure * risk_weight / 100

        return {
            "group": "2b",
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "gross_exposure": gross_exposure,
            "risk_weight_pct": risk_weight,
            "rwa": rwa,
            "hedging_benefit": 0,
        }


def check_group2_exposure_limit(
    group2a_exposure: float,
    group2b_exposure: float,
    tier1_capital: float
) -> dict:
    """
    Check Group 2 exposure limits.

    Total Group 2: max 2% of Tier 1
    Group 2b alone: max 1% of Tier 1

    Parameters:
    -----------
    group2a_exposure : float
        Total Group 2a exposure
    group2b_exposure : float
        Total Group 2b exposure
    tier1_capital : float
        Tier 1 capital

    Returns:
    --------
    dict
        Limit check results
    """
    total_group2 = group2a_exposure + group2b_exposure

    group2_ratio = total_group2 / tier1_capital if tier1_capital > 0 else 0
    group2b_ratio = group2b_exposure / tier1_capital if tier1_capital > 0 else 0

    group2_limit_breached = group2_ratio > GROUP2_EXPOSURE_LIMIT
    group2b_limit_breached = group2b_ratio > GROUP2B_EXPOSURE_LIMIT

    # Excess exposure gets 1250% RW regardless of classification
    group2_excess = max(0, total_group2 - tier1_capital * GROUP2_EXPOSURE_LIMIT)
    group2b_excess = max(0, group2b_exposure - tier1_capital * GROUP2B_EXPOSURE_LIMIT)

    return {
        "group2a_exposure": group2a_exposure,
        "group2b_exposure": group2b_exposure,
        "total_group2": total_group2,
        "tier1_capital": tier1_capital,
        "group2_ratio_pct": group2_ratio * 100,
        "group2b_ratio_pct": group2b_ratio * 100,
        "group2_limit_pct": GROUP2_EXPOSURE_LIMIT * 100,
        "group2b_limit_pct": GROUP2B_EXPOSURE_LIMIT * 100,
        "group2_limit_breached": group2_limit_breached,
        "group2b_limit_breached": group2b_limit_breached,
        "group2_excess": group2_excess,
        "group2b_excess": group2b_excess,
        "excess_rwa": (group2_excess + group2b_excess) * 12.5,  # 1250% RW
    }


def calculate_total_crypto_rwa(
    exposures: list[dict],
    tier1_capital: float
) -> dict:
    """
    Calculate total RWA for all crypto-asset exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each should have: amount, group, and group-specific parameters
    tier1_capital : float
        Tier 1 capital for limit checks

    Returns:
    --------
    dict
        Total crypto RWA calculation
    """
    results = {
        "group_1a": {"exposure": 0, "rwa": 0, "details": []},
        "group_1b": {"exposure": 0, "rwa": 0, "details": []},
        "group_2a": {"exposure": 0, "rwa": 0, "details": []},
        "group_2b": {"exposure": 0, "rwa": 0, "details": []},
    }

    for exp in exposures:
        group = exp.get("group", "2b")
        amount = exp.get("amount", 0)

        if group == "1a":
            result = calculate_group1a_rwa(
                amount,
                exp.get("underlying_type", "equity"),
                exp.get("underlying_rw"),
                exp.get("underlying_rating", "unrated")
            )
            results["group_1a"]["exposure"] += amount
            results["group_1a"]["rwa"] += result["rwa"]
            results["group_1a"]["details"].append(result)

        elif group == "1b":
            result = calculate_group1b_rwa(
                amount,
                exp.get("reserve_composition", {"cash": (1.0, 0)})
            )
            results["group_1b"]["exposure"] += amount
            results["group_1b"]["rwa"] += result["total_rwa"]
            results["group_1b"]["details"].append(result)

        elif group == "2a":
            result = calculate_group2_rwa(
                amount,
                exp.get("short_exposure", 0),
                is_group_2a=True
            )
            results["group_2a"]["exposure"] += amount
            results["group_2a"]["rwa"] += result["rwa"]
            results["group_2a"]["details"].append(result)

        else:  # 2b
            result = calculate_group2_rwa(
                amount,
                exp.get("short_exposure", 0),
                is_group_2a=False
            )
            results["group_2b"]["exposure"] += amount
            results["group_2b"]["rwa"] += result["rwa"]
            results["group_2b"]["details"].append(result)

    # Check limits
    limit_check = check_group2_exposure_limit(
        results["group_2a"]["exposure"],
        results["group_2b"]["exposure"],
        tier1_capital
    )

    # Total RWA including excess penalty
    total_rwa = (
        results["group_1a"]["rwa"] +
        results["group_1b"]["rwa"] +
        results["group_2a"]["rwa"] +
        results["group_2b"]["rwa"] +
        limit_check["excess_rwa"]
    )

    return {
        "by_group": results,
        "limit_check": limit_check,
        "total_exposure": sum(r["exposure"] for r in results.values()),
        "total_rwa": total_rwa,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Crypto-assets Prudential Treatment")
    print("=" * 70)

    # Group 1a: Tokenised bond
    print("\n  Group 1a - Tokenised Bond:")
    g1a = calculate_group1a_rwa(10_000_000, "corporate", underlying_rating="A")
    print(f"    Exposure: ${g1a['exposure']:,.0f}")
    print(f"    Underlying RW: {g1a['underlying_rw']}%")
    print(f"    RWA: ${g1a['rwa']:,.0f}")
    print(f"    Effective RW: {g1a['total_rwa_equivalent_rw']:.1f}%")

    # Group 1b: Stablecoin
    print("\n  Group 1b - Stablecoin:")
    reserve_comp = {
        "cash": (0.50, 0),
        "sovereign_aa": (0.30, 0),
        "corporate_aa": (0.20, 20),
    }
    g1b = calculate_group1b_rwa(10_000_000, reserve_comp)
    print(f"    Exposure: ${g1b['exposure']:,.0f}")
    print(f"    Weighted Reserve RW: {g1b['weighted_reserve_rw']:.1f}%")
    print(f"    Total RWA: ${g1b['total_rwa']:,.0f}")
    print(f"    Effective RW: {g1b['effective_rw_pct']:.1f}%")

    # Group 2a: Bitcoin with hedge
    print("\n  Group 2a - Bitcoin (with hedge):")
    g2a = calculate_group2_rwa(5_000_000, short_exposure=3_000_000, is_group_2a=True)
    print(f"    Long: ${g2a['long_exposure']:,.0f}")
    print(f"    Short: ${g2a['short_exposure']:,.0f}")
    print(f"    Net: ${g2a['net_exposure']:,.0f}")
    print(f"    RW: {g2a['risk_weight_pct']}%")
    print(f"    RWA: ${g2a['rwa']:,.0f}")
    print(f"    Hedging benefit: ${g2a['hedging_benefit']:,.0f}")

    # Group 2b: Altcoin
    print("\n  Group 2b - Altcoin (no hedge):")
    g2b = calculate_group2_rwa(2_000_000, is_group_2a=False)
    print(f"    Gross: ${g2b['gross_exposure']:,.0f}")
    print(f"    RW: {g2b['risk_weight_pct']}%")
    print(f"    RWA: ${g2b['rwa']:,.0f}")

    # Exposure limits
    print("\n" + "=" * 70)
    print("Exposure Limit Check")
    print("=" * 70)

    tier1 = 100_000_000_000  # 100bn Tier 1

    limit_check = check_group2_exposure_limit(
        group2a_exposure=1_500_000_000,  # 1.5bn
        group2b_exposure=800_000_000,    # 800m
        tier1_capital=tier1
    )

    print(f"\n  Tier 1 Capital:          ${tier1/1e9:.0f}bn")
    print(f"  Group 2a Exposure:       ${limit_check['group2a_exposure']/1e9:.1f}bn ({limit_check['group2_ratio_pct'] - limit_check['group2b_ratio_pct']:.2f}%)")
    print(f"  Group 2b Exposure:       ${limit_check['group2b_exposure']/1e9:.1f}bn ({limit_check['group2b_ratio_pct']:.2f}%)")
    print(f"  Total Group 2:           ${limit_check['total_group2']/1e9:.1f}bn ({limit_check['group2_ratio_pct']:.2f}%)")
    print(f"  Group 2 Limit (2%):      {'BREACHED' if limit_check['group2_limit_breached'] else 'OK'}")
    print(f"  Group 2b Limit (1%):     {'BREACHED' if limit_check['group2b_limit_breached'] else 'OK'}")
