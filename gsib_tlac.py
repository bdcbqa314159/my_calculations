"""
G-SIB Framework and TLAC/MREL

Implements:
- G-SIB scoring methodology
- G-SIB buffer calculation
- TLAC (Total Loss-Absorbing Capacity)
- MREL (Minimum Requirement for own funds and Eligible Liabilities)

Reference: BCBS G-SIB framework, TLAC term sheet
"""

import math
from typing import Optional


# =============================================================================
# G-SIB Scoring Methodology (BCBS d445)
# =============================================================================

# G-SIB indicator categories and weights
GSIB_CATEGORIES = {
    "size": {
        "weight": 0.20,
        "indicators": {
            "total_exposures": 1.0,  # Total exposures (leverage ratio denominator)
        }
    },
    "interconnectedness": {
        "weight": 0.20,
        "indicators": {
            "intra_financial_assets": 1/3,
            "intra_financial_liabilities": 1/3,
            "securities_outstanding": 1/3,
        }
    },
    "substitutability": {
        "weight": 0.20,
        "indicators": {
            "payments_activity": 1/3,
            "assets_under_custody": 1/3,
            "underwriting_activity": 1/3,
        }
    },
    "complexity": {
        "weight": 0.20,
        "indicators": {
            "otc_derivatives_notional": 1/3,
            "level_3_assets": 1/3,
            "trading_securities": 1/3,
        }
    },
    "cross_jurisdictional": {
        "weight": 0.20,
        "indicators": {
            "cross_jurisdictional_claims": 0.5,
            "cross_jurisdictional_liabilities": 0.5,
        }
    },
}

# G-SIB buckets and buffer requirements
GSIB_BUCKETS = {
    1: {"score_range": (130, 229), "buffer": 0.010},   # 1.0%
    2: {"score_range": (230, 329), "buffer": 0.015},   # 1.5%
    3: {"score_range": (330, 429), "buffer": 0.020},   # 2.0%
    4: {"score_range": (430, 529), "buffer": 0.025},   # 2.5%
    5: {"score_range": (530, float('inf')), "buffer": 0.035},  # 3.5%
}

# Denominators (global aggregates) - these would be updated annually
# Using illustrative values
GSIB_DENOMINATORS = {
    "total_exposures": 100_000_000_000_000,  # 100 trillion
    "intra_financial_assets": 20_000_000_000_000,
    "intra_financial_liabilities": 20_000_000_000_000,
    "securities_outstanding": 15_000_000_000_000,
    "payments_activity": 500_000_000_000_000,
    "assets_under_custody": 150_000_000_000_000,
    "underwriting_activity": 10_000_000_000_000,
    "otc_derivatives_notional": 400_000_000_000_000,
    "level_3_assets": 2_000_000_000_000,
    "trading_securities": 20_000_000_000_000,
    "cross_jurisdictional_claims": 30_000_000_000_000,
    "cross_jurisdictional_liabilities": 25_000_000_000_000,
}


def calculate_gsib_indicator_score(
    indicator_value: float,
    indicator_name: str,
    denominator: float = None
) -> float:
    """
    Calculate score for a single G-SIB indicator.

    Score = (Bank's value / Global aggregate) × 10,000

    Parameters:
    -----------
    indicator_value : float
        Bank's value for this indicator
    indicator_name : str
        Name of indicator (for denominator lookup)
    denominator : float, optional
        Custom denominator (global aggregate)

    Returns:
    --------
    float
        Indicator score (basis points)
    """
    if denominator is None:
        denominator = GSIB_DENOMINATORS.get(indicator_name, 1)

    if denominator <= 0:
        return 0

    score = (indicator_value / denominator) * 10000
    return score


def calculate_gsib_category_score(
    category: str,
    indicator_values: dict
) -> dict:
    """
    Calculate score for a G-SIB category.

    Parameters:
    -----------
    category : str
        Category name (size, interconnectedness, etc.)
    indicator_values : dict
        {indicator_name: value}

    Returns:
    --------
    dict
        Category score details
    """
    if category not in GSIB_CATEGORIES:
        raise ValueError(f"Unknown category: {category}")

    category_config = GSIB_CATEGORIES[category]
    indicators = category_config["indicators"]

    indicator_scores = {}
    weighted_sum = 0

    for indicator_name, indicator_weight in indicators.items():
        value = indicator_values.get(indicator_name, 0)
        score = calculate_gsib_indicator_score(value, indicator_name)
        weighted_score = score * indicator_weight

        indicator_scores[indicator_name] = {
            "value": value,
            "score": score,
            "weight": indicator_weight,
            "weighted_score": weighted_score,
        }

        weighted_sum += weighted_score

    # Category score = weighted sum of indicator scores × category weight
    category_score = weighted_sum * category_config["weight"]

    return {
        "category": category,
        "category_weight": category_config["weight"],
        "indicator_scores": indicator_scores,
        "category_score": category_score,
    }


def calculate_gsib_score(bank_data: dict) -> dict:
    """
    Calculate total G-SIB score for a bank.

    Parameters:
    -----------
    bank_data : dict
        All indicator values for the bank

    Returns:
    --------
    dict
        Complete G-SIB score calculation
    """
    category_results = {}
    total_score = 0

    for category in GSIB_CATEGORIES.keys():
        result = calculate_gsib_category_score(category, bank_data)
        category_results[category] = result
        total_score += result["category_score"]

    # Determine bucket
    bucket = None
    buffer = 0

    for bucket_num, bucket_config in GSIB_BUCKETS.items():
        min_score, max_score = bucket_config["score_range"]
        if min_score <= total_score < max_score:
            bucket = bucket_num
            buffer = bucket_config["buffer"]
            break

    is_gsib = bucket is not None

    return {
        "total_score": total_score,
        "is_gsib": is_gsib,
        "bucket": bucket,
        "buffer_requirement": buffer,
        "buffer_requirement_pct": buffer * 100 if buffer else 0,
        "category_scores": category_results,
    }


# =============================================================================
# TLAC (Total Loss-Absorbing Capacity)
# =============================================================================

# TLAC minimum requirements
TLAC_MINIMUM_RWA = 0.18  # 18% of RWA
TLAC_MINIMUM_LEVERAGE = 0.0675  # 6.75% of leverage exposure


def calculate_tlac_requirement(
    rwa: float,
    leverage_exposure: float,
    gsib_buffer: float = 0
) -> dict:
    """
    Calculate TLAC requirement.

    TLAC minimum = max(18% RWA + buffers, 6.75% leverage exposure)

    Parameters:
    -----------
    rwa : float
        Risk-weighted assets
    leverage_exposure : float
        Leverage ratio exposure measure
    gsib_buffer : float
        G-SIB buffer rate

    Returns:
    --------
    dict
        TLAC requirement calculation
    """
    # RWA-based requirement
    rwa_requirement = TLAC_MINIMUM_RWA + gsib_buffer
    tlac_rwa = rwa * rwa_requirement

    # Leverage-based requirement
    tlac_leverage = leverage_exposure * TLAC_MINIMUM_LEVERAGE

    # Binding requirement is the higher
    tlac_requirement = max(tlac_rwa, tlac_leverage)
    binding_constraint = "RWA" if tlac_rwa >= tlac_leverage else "Leverage"

    return {
        "rwa": rwa,
        "leverage_exposure": leverage_exposure,
        "gsib_buffer": gsib_buffer,
        "rwa_requirement_pct": rwa_requirement * 100,
        "leverage_requirement_pct": TLAC_MINIMUM_LEVERAGE * 100,
        "tlac_rwa_based": tlac_rwa,
        "tlac_leverage_based": tlac_leverage,
        "tlac_requirement": tlac_requirement,
        "binding_constraint": binding_constraint,
    }


def calculate_tlac_ratio(
    tlac_resources: dict,
    rwa: float,
    leverage_exposure: float
) -> dict:
    """
    Calculate TLAC ratios.

    Parameters:
    -----------
    tlac_resources : dict
        TLAC-eligible instruments:
        - cet1: CET1 capital
        - at1: Additional Tier 1
        - tier2: Tier 2
        - senior_debt: TLAC-eligible senior debt
        - other_tlac: Other TLAC-eligible liabilities
    rwa : float
        Risk-weighted assets
    leverage_exposure : float
        Leverage ratio exposure measure

    Returns:
    --------
    dict
        TLAC ratio calculation
    """
    # Sum TLAC resources
    cet1 = tlac_resources.get("cet1", 0)
    at1 = tlac_resources.get("at1", 0)
    tier2 = tlac_resources.get("tier2", 0)
    senior_debt = tlac_resources.get("senior_debt", 0)
    other_tlac = tlac_resources.get("other_tlac", 0)

    total_tlac = cet1 + at1 + tier2 + senior_debt + other_tlac
    regulatory_capital = cet1 + at1 + tier2

    # Calculate ratios
    tlac_rwa_ratio = total_tlac / rwa if rwa > 0 else 0
    tlac_leverage_ratio = total_tlac / leverage_exposure if leverage_exposure > 0 else 0

    return {
        "tlac_resources": {
            "cet1": cet1,
            "at1": at1,
            "tier2": tier2,
            "senior_debt": senior_debt,
            "other_tlac": other_tlac,
            "total": total_tlac,
        },
        "regulatory_capital": regulatory_capital,
        "rwa": rwa,
        "leverage_exposure": leverage_exposure,
        "tlac_rwa_ratio": tlac_rwa_ratio,
        "tlac_rwa_ratio_pct": tlac_rwa_ratio * 100,
        "tlac_leverage_ratio": tlac_leverage_ratio,
        "tlac_leverage_ratio_pct": tlac_leverage_ratio * 100,
    }


def check_tlac_compliance(
    tlac_resources: dict,
    rwa: float,
    leverage_exposure: float,
    gsib_buffer: float = 0
) -> dict:
    """
    Check TLAC compliance.

    Parameters:
    -----------
    tlac_resources : dict
        TLAC-eligible instruments
    rwa : float
        Risk-weighted assets
    leverage_exposure : float
        Leverage ratio exposure measure
    gsib_buffer : float
        G-SIB buffer rate

    Returns:
    --------
    dict
        TLAC compliance check
    """
    requirement = calculate_tlac_requirement(rwa, leverage_exposure, gsib_buffer)
    ratio = calculate_tlac_ratio(tlac_resources, rwa, leverage_exposure)

    # Check compliance
    rwa_compliant = ratio["tlac_rwa_ratio"] >= (TLAC_MINIMUM_RWA + gsib_buffer)
    leverage_compliant = ratio["tlac_leverage_ratio"] >= TLAC_MINIMUM_LEVERAGE
    overall_compliant = rwa_compliant and leverage_compliant

    # Shortfall
    shortfall_rwa = max(requirement["tlac_rwa_based"] - ratio["tlac_resources"]["total"], 0)
    shortfall_leverage = max(requirement["tlac_leverage_based"] - ratio["tlac_resources"]["total"], 0)
    shortfall = max(shortfall_rwa, shortfall_leverage)

    return {
        "requirement": requirement,
        "ratio": ratio,
        "rwa_compliant": rwa_compliant,
        "leverage_compliant": leverage_compliant,
        "overall_compliant": overall_compliant,
        "shortfall": shortfall,
        "surplus": -shortfall if shortfall == 0 else ratio["tlac_resources"]["total"] - requirement["tlac_requirement"],
    }


# =============================================================================
# MREL (Minimum Requirement for own funds and Eligible Liabilities)
# =============================================================================

# MREL default requirements (EU framework - can vary by resolution authority)
MREL_DEFAULT_RWA = 0.08  # 8% of RWA (Pillar 1)
MREL_DEFAULT_LEVERAGE = 0.03  # 3% of leverage exposure


def calculate_mrel_requirement(
    rwa: float,
    leverage_exposure: float,
    pillar1_requirement: float = 0.08,
    pillar2_requirement: float = 0.02,
    combined_buffer: float = 0.025,
    resolution_authority_addon: float = 0
) -> dict:
    """
    Calculate MREL requirement.

    MREL is typically set by resolution authorities and can include:
    - Loss absorption amount (LAA)
    - Recapitalization amount (RCA)
    - Market confidence charge (MCC)

    Parameters:
    -----------
    rwa : float
        Risk-weighted assets
    leverage_exposure : float
        Leverage ratio exposure measure
    pillar1_requirement : float
        Pillar 1 capital requirement rate
    pillar2_requirement : float
        Pillar 2 capital requirement rate
    combined_buffer : float
        Combined buffer requirement rate
    resolution_authority_addon : float
        Additional requirement from resolution authority

    Returns:
    --------
    dict
        MREL requirement calculation
    """
    # Loss Absorption Amount (LAA) = Pillar 1 + Pillar 2
    laa_rate = pillar1_requirement + pillar2_requirement
    laa = rwa * laa_rate

    # Recapitalization Amount (RCA) = typically mirrors LAA
    rca_rate = pillar1_requirement + pillar2_requirement
    rca = rwa * rca_rate

    # Market Confidence Charge (MCC) = combined buffer - countercyclical (simplified)
    mcc_rate = combined_buffer
    mcc = rwa * mcc_rate

    # Total MREL (RWA-based)
    mrel_rwa_rate = laa_rate + rca_rate + mcc_rate + resolution_authority_addon
    mrel_rwa = rwa * mrel_rwa_rate

    # Leverage-based MREL (typically 3% + requirements)
    mrel_leverage_rate = MREL_DEFAULT_LEVERAGE * 2  # Simplified
    mrel_leverage = leverage_exposure * mrel_leverage_rate

    # Binding requirement
    mrel_requirement = max(mrel_rwa, mrel_leverage)
    binding_constraint = "RWA" if mrel_rwa >= mrel_leverage else "Leverage"

    return {
        "rwa": rwa,
        "leverage_exposure": leverage_exposure,
        "laa": laa,
        "laa_rate": laa_rate,
        "rca": rca,
        "rca_rate": rca_rate,
        "mcc": mcc,
        "mcc_rate": mcc_rate,
        "mrel_rwa_based": mrel_rwa,
        "mrel_rwa_rate": mrel_rwa_rate,
        "mrel_leverage_based": mrel_leverage,
        "mrel_leverage_rate": mrel_leverage_rate,
        "mrel_requirement": mrel_requirement,
        "binding_constraint": binding_constraint,
    }


def calculate_mrel_ratio(
    mrel_resources: dict,
    rwa: float,
    leverage_exposure: float
) -> dict:
    """
    Calculate MREL ratios.

    Parameters:
    -----------
    mrel_resources : dict
        MREL-eligible instruments (similar to TLAC)
    rwa : float
        Risk-weighted assets
    leverage_exposure : float
        Leverage ratio exposure measure

    Returns:
    --------
    dict
        MREL ratio calculation
    """
    # MREL resources (slightly different eligibility than TLAC)
    cet1 = mrel_resources.get("cet1", 0)
    at1 = mrel_resources.get("at1", 0)
    tier2 = mrel_resources.get("tier2", 0)
    senior_non_preferred = mrel_resources.get("senior_non_preferred", 0)
    senior_preferred = mrel_resources.get("senior_preferred", 0)  # With subordination
    other_eligible = mrel_resources.get("other_eligible", 0)

    total_mrel = cet1 + at1 + tier2 + senior_non_preferred + senior_preferred + other_eligible
    own_funds = cet1 + at1 + tier2

    # Calculate ratios
    mrel_rwa_ratio = total_mrel / rwa if rwa > 0 else 0
    mrel_leverage_ratio = total_mrel / leverage_exposure if leverage_exposure > 0 else 0

    return {
        "mrel_resources": {
            "cet1": cet1,
            "at1": at1,
            "tier2": tier2,
            "senior_non_preferred": senior_non_preferred,
            "senior_preferred": senior_preferred,
            "other_eligible": other_eligible,
            "total": total_mrel,
        },
        "own_funds": own_funds,
        "eligible_liabilities": total_mrel - own_funds,
        "rwa": rwa,
        "leverage_exposure": leverage_exposure,
        "mrel_rwa_ratio": mrel_rwa_ratio,
        "mrel_rwa_ratio_pct": mrel_rwa_ratio * 100,
        "mrel_leverage_ratio": mrel_leverage_ratio,
        "mrel_leverage_ratio_pct": mrel_leverage_ratio * 100,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("G-SIB Scoring")
    print("=" * 70)

    # Sample bank data (large global bank)
    bank_data = {
        "total_exposures": 2_500_000_000_000,  # 2.5 trillion
        "intra_financial_assets": 500_000_000_000,
        "intra_financial_liabilities": 400_000_000_000,
        "securities_outstanding": 300_000_000_000,
        "payments_activity": 15_000_000_000_000,
        "assets_under_custody": 5_000_000_000_000,
        "underwriting_activity": 200_000_000_000,
        "otc_derivatives_notional": 10_000_000_000_000,
        "level_3_assets": 50_000_000_000,
        "trading_securities": 400_000_000_000,
        "cross_jurisdictional_claims": 800_000_000_000,
        "cross_jurisdictional_liabilities": 600_000_000_000,
    }

    gsib_result = calculate_gsib_score(bank_data)

    print(f"\n  G-SIB Score:             {gsib_result['total_score']:.0f}")
    print(f"  Is G-SIB:                {gsib_result['is_gsib']}")
    print(f"  Bucket:                  {gsib_result['bucket']}")
    print(f"  Buffer Requirement:      {gsib_result['buffer_requirement_pct']:.1f}%")

    print("\n  Category Scores:")
    for cat, data in gsib_result['category_scores'].items():
        print(f"    {cat:<20}: {data['category_score']:.0f}")

    print("\n" + "=" * 70)
    print("TLAC Calculation")
    print("=" * 70)

    rwa = 1_500_000_000_000  # 1.5 trillion RWA
    leverage_exposure = 2_500_000_000_000  # 2.5 trillion

    tlac_resources = {
        "cet1": 150_000_000_000,
        "at1": 30_000_000_000,
        "tier2": 40_000_000_000,
        "senior_debt": 100_000_000_000,
        "other_tlac": 20_000_000_000,
    }

    tlac_compliance = check_tlac_compliance(
        tlac_resources, rwa, leverage_exposure,
        gsib_buffer=gsib_result['buffer_requirement']
    )

    print(f"\n  TLAC Resources:          ${tlac_compliance['ratio']['tlac_resources']['total']/1e9:.0f}bn")
    print(f"  TLAC/RWA:                {tlac_compliance['ratio']['tlac_rwa_ratio_pct']:.1f}%")
    print(f"  TLAC/Leverage:           {tlac_compliance['ratio']['tlac_leverage_ratio_pct']:.2f}%")
    print(f"  Requirement (RWA):       {tlac_compliance['requirement']['rwa_requirement_pct']:.1f}%")
    print(f"  Requirement (Leverage):  {tlac_compliance['requirement']['leverage_requirement_pct']:.2f}%")
    print(f"  Compliant:               {tlac_compliance['overall_compliant']}")
    print(f"  Surplus/Shortfall:       ${tlac_compliance['surplus']/1e9:.1f}bn")

    print("\n" + "=" * 70)
    print("MREL Calculation")
    print("=" * 70)

    mrel_req = calculate_mrel_requirement(
        rwa, leverage_exposure,
        pillar1_requirement=0.08,
        pillar2_requirement=0.02,
        combined_buffer=0.04
    )

    mrel_resources = {
        "cet1": 150_000_000_000,
        "at1": 30_000_000_000,
        "tier2": 40_000_000_000,
        "senior_non_preferred": 80_000_000_000,
        "senior_preferred": 50_000_000_000,
    }

    mrel_ratio = calculate_mrel_ratio(mrel_resources, rwa, leverage_exposure)

    print(f"\n  MREL Requirement:        ${mrel_req['mrel_requirement']/1e9:.0f}bn")
    print(f"  MREL Requirement Rate:   {mrel_req['mrel_rwa_rate']*100:.1f}% of RWA")
    print(f"  MREL Resources:          ${mrel_ratio['mrel_resources']['total']/1e9:.0f}bn")
    print(f"  MREL/RWA:                {mrel_ratio['mrel_rwa_ratio_pct']:.1f}%")
    print(f"  MREL/Leverage:           {mrel_ratio['mrel_leverage_ratio_pct']:.2f}%")
