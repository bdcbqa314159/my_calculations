"""
Basel II Internal Ratings-Based (IRB) Approach for Credit Risk

Implements the Basel II IRB approaches:
- Foundation IRB (F-IRB): Bank estimates PD, supervisor provides LGD, EAD, M
- Advanced IRB (A-IRB): Bank estimates all risk parameters

The IRB formula is fundamentally the same as Basel III, as it originated in Basel II.
Basel III made refinements to correlations and added the output floor.
"""

import math
from scipy.stats import norm
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Maturity Configuration
# =============================================================================

@dataclass
class MaturityConfig:
    """
    Flexible maturity configuration for IRB calculations.

    Allows overriding default maturity handling for different exposure types
    and regulatory treatments.

    Attributes:
    -----------
    effective_maturity : float
        The M value to use (if None, uses the maturity parameter directly)
    maturity_floor : float
        Minimum maturity in years (default: 1.0, but 0 for some repo-style)
    maturity_cap : float
        Maximum maturity in years (default: 5.0)
    apply_maturity_adjustment : bool
        Whether to apply the b(PD) maturity adjustment (False for retail)
    maturity_adjustment_override : float
        Direct override of the b factor (if None, calculated from PD)
    maturity_scaling_factor : float
        Multiplier on the maturity adjustment (default: 1.0)
    reference_maturity : float
        Reference maturity for adjustment formula (default: 2.5 years)
    """
    effective_maturity: Optional[float] = None
    maturity_floor: float = 1.0
    maturity_cap: float = 5.0
    apply_maturity_adjustment: bool = True
    maturity_adjustment_override: Optional[float] = None
    maturity_scaling_factor: float = 1.0
    reference_maturity: float = 2.5


# Pre-defined maturity configurations for common exposure types
MATURITY_CONFIGS = {
    # Standard corporate - uses default 1y floor, 5y cap
    "corporate": MaturityConfig(),

    # F-IRB fixed maturity at 2.5 years
    "firb_fixed": MaturityConfig(effective_maturity=2.5),

    # Repo-style transactions - can have 0 floor
    "repo_style": MaturityConfig(maturity_floor=0.0),

    # Short-term self-liquidating trade finance
    "trade_finance": MaturityConfig(maturity_floor=0.0, maturity_cap=1.0),

    # Retail - no maturity adjustment
    "retail": MaturityConfig(apply_maturity_adjustment=False),

    # SME with reduced maturity sensitivity
    "sme": MaturityConfig(maturity_scaling_factor=0.75),

    # Project finance - often longer maturities
    "project_finance": MaturityConfig(maturity_cap=7.0),

    # Revolving facilities
    "revolving": MaturityConfig(effective_maturity=2.5),
}


# =============================================================================
# Rating to PD Mapping
# =============================================================================

RATING_TO_PD = {
    "AAA": 0.0003,
    "AA+": 0.0005,
    "AA": 0.0007,
    "AA-": 0.0010,
    "A+": 0.0015,
    "A": 0.0025,
    "A-": 0.0040,
    "BBB+": 0.0060,
    "BBB": 0.0100,
    "BBB-": 0.0175,
    "BB+": 0.0275,
    "BB": 0.0450,
    "BB-": 0.0750,
    "B+": 0.1100,
    "B": 0.1500,
    "B-": 0.2000,
    "CCC+": 0.2500,
    "CCC": 0.3000,
    "CCC-": 0.3500,
    "D": 1.0000,
}

_PD_RATING_SORTED = sorted(RATING_TO_PD.items(), key=lambda x: x[1])


def get_rating_from_pd(pd: float) -> str:
    """Get the closest external rating for a given PD value."""
    if pd <= 0:
        return "AAA"
    if pd >= 1.0:
        return "D"

    best_rating = "BBB"
    min_distance = float("inf")

    for rating, rating_pd in _PD_RATING_SORTED:
        distance = abs(pd - rating_pd)
        if distance < min_distance:
            min_distance = distance
            best_rating = rating

    return best_rating


# =============================================================================
# F-IRB Supervisory Parameters (Para 287-296)
# =============================================================================

# LGD values for F-IRB (Para 287-288)
FIRB_LGD = {
    "senior_unsecured": 0.45,      # 45% for senior claims
    "subordinated": 0.75,           # 75% for subordinated claims
}

# Collateral haircuts for F-IRB LGD adjustment (Para 289-294)
FIRB_COLLATERAL_LGD = {
    "financial_collateral": 0.00,   # 0% after comprehensive approach
    "receivables": 0.35,            # 35% LGD
    "commercial_real_estate": 0.35, # 35% LGD
    "residential_real_estate": 0.35,# 35% LGD
    "other_physical": 0.40,         # 40% LGD
}

# Maturity for F-IRB (Para 318-320)
FIRB_MATURITY = 2.5  # Fixed at 2.5 years for most exposures


# =============================================================================
# Asset Correlation Functions (Para 271-273)
# =============================================================================

def calculate_correlation(pd: float, asset_class: str = "corporate") -> float:
    """
    Calculate asset correlation R for the IRB formula.

    Basel II correlation formulas (Para 271-273):
    - Corporate/Bank/Sovereign: R = 0.12 * f(PD) + 0.24 * (1 - f(PD))
    - SME with size adjustment
    - Retail: different correlations by sub-class

    Parameters:
    -----------
    pd : float
        Probability of Default
    asset_class : str
        Asset class for correlation

    Returns:
    --------
    float
        Asset correlation R
    """
    if asset_class in ["corporate", "bank", "sovereign"]:
        # Corporate correlation formula (Para 271)
        exp_factor = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
        r = 0.12 * exp_factor + 0.24 * (1 - exp_factor)
        return r

    elif asset_class == "sme_corporate":
        # SME size adjustment (Para 272) - S in millions EUR, 5 <= S <= 50
        # R = 0.12 * f(PD) + 0.24 * (1 - f(PD)) - 0.04 * (1 - (S-5)/45)
        exp_factor = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
        r = 0.12 * exp_factor + 0.24 * (1 - exp_factor)
        # Assume average SME size of 20M for adjustment
        size_adjustment = 0.04 * (1 - (20 - 5) / 45)
        return r - size_adjustment

    elif asset_class == "retail_mortgage":
        # Residential mortgage: fixed correlation (Para 328)
        return 0.15

    elif asset_class == "retail_revolving":
        # Qualifying revolving retail (Para 329)
        return 0.04

    elif asset_class == "retail_other":
        # Other retail (Para 330)
        exp_factor = (1 - math.exp(-35 * pd)) / (1 - math.exp(-35))
        r = 0.03 * exp_factor + 0.16 * (1 - exp_factor)
        return r

    else:
        # Default to corporate
        exp_factor = (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
        return 0.12 * exp_factor + 0.24 * (1 - exp_factor)


def calculate_maturity_adjustment(
    pd: float,
    config: MaturityConfig = None
) -> float:
    """
    Calculate maturity adjustment factor b(PD).

    b = (0.11852 - 0.05478 * ln(PD))^2  (Para 272)

    Parameters:
    -----------
    pd : float
        Probability of Default
    config : MaturityConfig
        Optional configuration for overrides

    Returns:
    --------
    float
        Maturity adjustment factor b
    """
    # Check for direct override
    if config and config.maturity_adjustment_override is not None:
        return config.maturity_adjustment_override

    pd = max(pd, 0.0003)  # Floor to avoid log issues
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2

    # Apply scaling factor if configured
    if config and config.maturity_scaling_factor != 1.0:
        b = b * config.maturity_scaling_factor

    return b


def get_effective_maturity(
    maturity: float,
    config: MaturityConfig = None
) -> float:
    """
    Get effective maturity after applying floor and cap.

    Parameters:
    -----------
    maturity : float
        Input maturity in years
    config : MaturityConfig
        Configuration with floor/cap settings

    Returns:
    --------
    float
        Effective maturity
    """
    if config is None:
        config = MaturityConfig()

    # Use override if specified
    if config.effective_maturity is not None:
        return config.effective_maturity

    # Apply floor and cap
    m = max(maturity, config.maturity_floor)
    m = min(m, config.maturity_cap)

    return m


# =============================================================================
# IRB Capital Requirement Formula (Para 272)
# =============================================================================

def calculate_capital_requirement(
    pd: float,
    lgd: float,
    maturity: float = 2.5,
    asset_class: str = "corporate",
    maturity_config: MaturityConfig = None
) -> float:
    """
    Calculate capital requirement K using the Basel II IRB formula.

    K = [LGD × N[(1-R)^(-0.5) × G(PD) + (R/(1-R))^0.5 × G(0.999)] - PD × LGD]
        × [(1-1.5×b)^(-1)] × [1 + (M-2.5) × b]

    Parameters:
    -----------
    pd : float
        Probability of Default
    lgd : float
        Loss Given Default
    maturity : float
        Effective maturity (years)
    asset_class : str
        Asset class for correlation
    maturity_config : MaturityConfig
        Optional maturity configuration for flexible handling

    Returns:
    --------
    float
        Capital requirement K (as decimal)
    """
    # Floor PD at 0.03% (Para 285)
    pd = max(pd, 0.0003)
    pd = min(pd, 1.0)

    # Get correlation
    r = calculate_correlation(pd, asset_class)

    # Calculate conditional PD at 99.9% confidence
    g_pd = norm.ppf(pd)
    g_conf = norm.ppf(0.999)

    conditional_pd = norm.cdf(
        (1 - r) ** (-0.5) * g_pd + (r / (1 - r)) ** 0.5 * g_conf
    )

    # Capital for unexpected loss
    k_base = lgd * conditional_pd - pd * lgd

    # Determine if maturity adjustment applies
    apply_adjustment = True
    if asset_class.startswith("retail"):
        apply_adjustment = False
    if maturity_config and not maturity_config.apply_maturity_adjustment:
        apply_adjustment = False

    if apply_adjustment:
        # Get effective maturity with floor/cap
        m = get_effective_maturity(maturity, maturity_config)

        # Get maturity adjustment factor
        b = calculate_maturity_adjustment(pd, maturity_config)

        # Reference maturity (default 2.5)
        m_ref = 2.5
        if maturity_config and maturity_config.reference_maturity:
            m_ref = maturity_config.reference_maturity

        maturity_factor = (1 + (m - m_ref) * b) / (1 - 1.5 * b)
        k = k_base * maturity_factor
    else:
        k = k_base

    return max(k, 0)


# =============================================================================
# RWA Calculation Functions
# =============================================================================

def calculate_irb_rwa(
    ead: float,
    pd: float,
    lgd: float,
    maturity: float = 2.5,
    asset_class: str = "corporate",
    maturity_config: MaturityConfig = None
) -> dict:
    """
    Calculate RWA using IRB approach (generic).

    RWA = K × 12.5 × EAD

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default
    lgd : float
        Loss Given Default
    maturity : float
        Effective maturity
    asset_class : str
        Asset class
    maturity_config : MaturityConfig
        Optional maturity configuration for flexible handling

    Returns:
    --------
    dict
        IRB calculation results
    """
    # Get effective maturity
    effective_m = get_effective_maturity(maturity, maturity_config)

    k = calculate_capital_requirement(pd, lgd, effective_m, asset_class, maturity_config)
    rwa = k * 12.5 * ead
    risk_weight = k * 12.5 * 100
    correlation = calculate_correlation(pd, asset_class)

    result = {
        "approach": "Basel II IRB",
        "ead": ead,
        "pd": pd,
        "lgd": lgd,
        "maturity": maturity,
        "effective_maturity": effective_m,
        "asset_class": asset_class,
        "correlation": correlation,
        "capital_requirement_k": k,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "expected_loss": pd * lgd * ead,
    }

    # Add maturity config details if provided
    if maturity_config:
        result["maturity_config"] = {
            "floor": maturity_config.maturity_floor,
            "cap": maturity_config.maturity_cap,
            "scaling_factor": maturity_config.maturity_scaling_factor,
            "adjustment_applied": maturity_config.apply_maturity_adjustment,
        }

    return result


def calculate_firb_rwa(
    ead: float,
    pd: float,
    seniority: str = "senior",
    collateral_type: str = None,
    asset_class: str = "corporate",
    maturity_config: MaturityConfig = None,
    override_fixed_maturity: bool = False
) -> dict:
    """
    Calculate RWA using Foundation IRB (F-IRB).

    In F-IRB, banks estimate PD while LGD, EAD, and M are prescribed.

    Parameters:
    -----------
    ead : float
        Exposure at Default (supervisory EAD for F-IRB)
    pd : float
        Bank-estimated PD
    seniority : str
        "senior" (45% LGD) or "subordinated" (75% LGD)
    collateral_type : str
        Type of collateral if secured
    asset_class : str
        Asset class
    maturity_config : MaturityConfig
        Optional maturity configuration (normally F-IRB uses fixed 2.5y)
    override_fixed_maturity : bool
        If True, allows maturity_config to override the fixed 2.5y maturity

    Returns:
    --------
    dict
        F-IRB calculation results
    """
    # Determine LGD
    if collateral_type:
        lgd = FIRB_COLLATERAL_LGD.get(collateral_type, 0.45)
    else:
        lgd = FIRB_LGD.get(f"{seniority}_unsecured", 0.45)

    # F-IRB normally uses fixed maturity
    if override_fixed_maturity and maturity_config:
        # Use provided config
        config = maturity_config
        maturity = maturity_config.effective_maturity or FIRB_MATURITY
    else:
        # Standard F-IRB: fixed 2.5 year maturity
        maturity = FIRB_MATURITY
        config = MATURITY_CONFIGS["firb_fixed"]

    result = calculate_irb_rwa(ead, pd, lgd, maturity, asset_class, config)
    result["approach"] = "Basel II F-IRB"
    result["seniority"] = seniority
    result["collateral_type"] = collateral_type
    result["fixed_maturity_used"] = not override_fixed_maturity

    return result


def calculate_airb_rwa(
    ead: float,
    pd: float,
    lgd: float,
    maturity: float = 2.5,
    asset_class: str = "corporate",
    lgd_downturn: float = None,
    maturity_config: MaturityConfig = None
) -> dict:
    """
    Calculate RWA using Advanced IRB (A-IRB).

    In A-IRB, banks estimate all risk parameters (PD, LGD, EAD, M).

    Parameters:
    -----------
    ead : float
        Bank-estimated EAD
    pd : float
        Bank-estimated PD
    lgd : float
        Bank-estimated LGD (should be downturn LGD)
    maturity : float
        Bank-estimated effective maturity
    asset_class : str
        Asset class
    lgd_downturn : float
        Explicit downturn LGD if different from lgd
    maturity_config : MaturityConfig
        Optional maturity configuration for flexible handling.
        Common presets available: MATURITY_CONFIGS["corporate"],
        MATURITY_CONFIGS["repo_style"], MATURITY_CONFIGS["sme"], etc.

    Returns:
    --------
    dict
        A-IRB calculation results
    """
    # Use downturn LGD if provided
    lgd_used = lgd_downturn if lgd_downturn is not None else lgd

    result = calculate_irb_rwa(ead, pd, lgd_used, maturity, asset_class, maturity_config)
    result["approach"] = "Basel II A-IRB"
    result["lgd_input"] = lgd
    result["lgd_downturn"] = lgd_used

    return result


def calculate_batch_irb_rwa(
    exposures: list[dict],
    approach: str = "F-IRB"
) -> dict:
    """
    Calculate IRB RWA for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict: ead, pd, and optionally lgd, maturity, asset_class
    approach : str
        "F-IRB" or "A-IRB"

    Returns:
    --------
    dict
        Aggregated results
    """
    results = []
    total_ead = 0
    total_rwa = 0
    total_el = 0

    for exp in exposures:
        if approach == "F-IRB":
            result = calculate_firb_rwa(
                ead=exp["ead"],
                pd=exp["pd"],
                seniority=exp.get("seniority", "senior"),
                collateral_type=exp.get("collateral_type"),
                asset_class=exp.get("asset_class", "corporate")
            )
        else:
            result = calculate_airb_rwa(
                ead=exp["ead"],
                pd=exp["pd"],
                lgd=exp.get("lgd", 0.45),
                maturity=exp.get("maturity", 2.5),
                asset_class=exp.get("asset_class", "corporate"),
                lgd_downturn=exp.get("lgd_downturn")
            )

        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]
        total_el += result["expected_loss"]

    return {
        "approach": f"Basel II {approach}",
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "total_expected_loss": total_el,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "total_capital_requirement": total_rwa * 0.08,
        "exposures": results,
    }


def compare_firb_vs_airb(
    ead: float,
    pd: float,
    airb_lgd: float,
    airb_maturity: float = 2.5,
    seniority: str = "senior",
    asset_class: str = "corporate"
) -> dict:
    """
    Compare F-IRB vs A-IRB for the same exposure.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default
    airb_lgd : float
        Bank-estimated LGD for A-IRB
    airb_maturity : float
        Bank-estimated maturity for A-IRB
    seniority : str
        Seniority for F-IRB LGD
    asset_class : str
        Asset class

    Returns:
    --------
    dict
        Comparison results
    """
    firb_result = calculate_firb_rwa(ead, pd, seniority, asset_class=asset_class)
    airb_result = calculate_airb_rwa(ead, pd, airb_lgd, airb_maturity, asset_class)

    rwa_diff = airb_result["rwa"] - firb_result["rwa"]
    firb_lgd = firb_result["lgd"]

    return {
        "ead": ead,
        "pd": pd,
        "firb_lgd": firb_lgd,
        "airb_lgd": airb_lgd,
        "firb_maturity": FIRB_MATURITY,
        "airb_maturity": airb_maturity,
        "firb": firb_result,
        "airb": airb_result,
        "rwa_difference": rwa_diff,
        "rwa_difference_pct": (rwa_diff / firb_result["rwa"] * 100) if firb_result["rwa"] > 0 else 0,
        "more_conservative": "F-IRB" if firb_result["rwa"] > airb_result["rwa"] else "A-IRB",
    }


# =============================================================================
# Specialized Asset Classes
# =============================================================================

def calculate_slotting_rwa(
    ead: float,
    category: str,
    remaining_maturity: float = 2.5
) -> dict:
    """
    Calculate RWA using Supervisory Slotting for specialized lending.

    Categories: Strong, Good, Satisfactory, Weak, Default
    Used for: Project Finance, Object Finance, Commodities Finance, IPRE

    Parameters:
    -----------
    ead : float
        Exposure at Default
    category : str
        Slotting category
    remaining_maturity : float
        Remaining maturity (< 2.5 years gets lower RW)
    """
    # Slotting risk weights (Para 275)
    slotting_rw = {
        "strong": {"short": 50, "long": 70},
        "good": {"short": 70, "long": 90},
        "satisfactory": {"short": 115, "long": 115},
        "weak": {"short": 250, "long": 250},
        "default": {"short": 0, "long": 0},  # Deduction
    }

    category_lower = category.lower()
    if category_lower not in slotting_rw:
        raise ValueError(f"Unknown slotting category: {category}")

    term = "short" if remaining_maturity < 2.5 else "long"
    risk_weight = slotting_rw[category_lower][term]

    if category_lower == "default":
        # Subject to deduction treatment
        rwa = 0
        deduction = ead
    else:
        rwa = ead * risk_weight / 100
        deduction = 0

    return {
        "approach": "Basel II Slotting",
        "ead": ead,
        "category": category,
        "remaining_maturity": remaining_maturity,
        "term": term,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "deduction": deduction,
        "capital_requirement": rwa * 0.08 + deduction,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II IRB Approach - Credit Risk")
    print("=" * 70)

    # F-IRB examples
    print("\n  Foundation IRB (F-IRB):")
    print(f"\n  {'PD':>8} {'LGD':>8} {'RW':>10} {'RWA':>15}")
    print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*15}")

    pds = [0.003, 0.01, 0.03, 0.05, 0.10]
    for pd in pds:
        result = calculate_firb_rwa(1_000_000, pd, "senior")
        print(f"  {pd*100:>7.2f}% {result['lgd']*100:>7.0f}% "
              f"{result['risk_weight_pct']:>9.1f}% ${result['rwa']:>13,.0f}")

    # F-IRB vs A-IRB comparison
    print("\n" + "=" * 70)
    print("F-IRB vs A-IRB Comparison")
    print("=" * 70)

    comp = compare_firb_vs_airb(
        ead=1_000_000,
        pd=0.02,
        airb_lgd=0.30,  # Lower bank-estimated LGD
        airb_maturity=3.0
    )

    print(f"\n  PD: {comp['pd']*100:.1f}%")
    print(f"  F-IRB LGD: {comp['firb_lgd']*100:.0f}%, A-IRB LGD: {comp['airb_lgd']*100:.0f}%")
    print(f"  F-IRB M: {comp['firb_maturity']} years, A-IRB M: {comp['airb_maturity']} years")
    print(f"\n  {'Approach':<10} {'RW':>10} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*10} {'-'*15}")
    print(f"  {'F-IRB':<10} {comp['firb']['risk_weight_pct']:>9.1f}% ${comp['firb']['rwa']:>13,.0f}")
    print(f"  {'A-IRB':<10} {comp['airb']['risk_weight_pct']:>9.1f}% ${comp['airb']['rwa']:>13,.0f}")
    print(f"\n  RWA benefit from A-IRB: {comp['rwa_difference_pct']:.1f}%")

    # Slotting example
    print("\n" + "=" * 70)
    print("Supervisory Slotting - Specialized Lending")
    print("=" * 70)

    print(f"\n  {'Category':<15} {'RW':>8} {'RWA':>15}")
    print(f"  {'-'*15} {'-'*8} {'-'*15}")

    for cat in ["Strong", "Good", "Satisfactory", "Weak"]:
        result = calculate_slotting_rwa(1_000_000, cat)
        print(f"  {cat:<15} {result['risk_weight_pct']:>7.0f}% ${result['rwa']:>13,.0f}")
