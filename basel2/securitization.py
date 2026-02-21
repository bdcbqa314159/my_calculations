"""
Basel II Securitization Framework

Implements the Basel II approaches for securitization exposures:
1. Ratings-Based Approach (RBA)
2. Supervisory Formula Approach (SFA)
3. Internal Assessment Approach (IAA)

Key differences from Basel III:
- No STS (Simple, Transparent, Standardised) framework
- No SEC-SA/SEC-IRBA hierarchy
- Simpler risk weight tables
- Different floors and caps
"""

import math
from scipy.stats import norm
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# Ratings-Based Approach (RBA) - Para 611-618
# =============================================================================

# =============================================================================
# RE-SECURITISATION RW TABLE (Para 611-615, higher RWs for CDO-squared, etc.)
# =============================================================================

# RE-SECURITISATION: Rating Grade -> (Senior RW, Non-Senior RW)
# Higher RWs for CDO-squared, re-packaged securitisations, etc.
RESEC_RISK_WEIGHTS = {
    1:  (20, 30),     # AAA
    2:  (30, 40),     # AA
    3:  (40, 50),     # A+
    4:  (50, 65),     # A
    5:  (65, 85),     # A-
    6:  (85, 100),    # BBB+
    7:  (100, 125),   # BBB
    8:  (125, 150),   # BBB-
    9:  (425, 550),   # BB+
    10: (650, 850),   # BB
    11: (950, 1250),  # BB-
    12: (1250, 1250), # Below BB-
}

# Rating grade to label mapping
RESEC_RATING_LABELS = {
    1: "AAA", 2: "AA", 3: "A+", 4: "A", 5: "A-",
    6: "BBB+", 7: "BBB", 8: "BBB-",
    9: "BB+", 10: "BB", 11: "BB-", 12: "Below BB-",
}

# PD thresholds for rating grade mapping (for re-securitisation)
RESEC_PD_THRESHOLDS = [
    (0.0001, 1),   # <= 0.01%  -> AAA
    (0.0003, 2),   # <= 0.03%  -> AA
    (0.0005, 3),   # <= 0.05%  -> A+
    (0.0010, 4),   # <= 0.10%  -> A
    (0.0020, 5),   # <= 0.20%  -> A-
    (0.0035, 6),   # <= 0.35%  -> BBB+
    (0.0060, 7),   # <= 0.60%  -> BBB
    (0.0100, 8),   # <= 1.00%  -> BBB-
    (0.0200, 9),   # <= 2.00%  -> BB+
    (0.0400, 10),  # <= 4.00%  -> BB
    (0.0800, 11),  # <= 8.00%  -> BB-
    (1.0000, 12),  # > 8.00%   -> Below BB-
]


# RBA Risk Weights for long-term ratings (Para 615)
RBA_RISK_WEIGHTS_LONG_TERM = {
    # Senior tranches (thick)
    "senior_granular": {
        "AAA": 7, "AA": 8, "A+": 10, "A": 12, "A-": 20,
        "BBB+": 35, "BBB": 60, "BBB-": 100,
        "BB+": 250, "BB": 425, "BB-": 650,
        "below_BB-": "deduction",
    },
    # Senior tranches (non-granular)
    "senior_non_granular": {
        "AAA": 12, "AA": 15, "A+": 18, "A": 20, "A-": 35,
        "BBB+": 50, "BBB": 75, "BBB-": 100,
        "BB+": 250, "BB": 425, "BB-": 650,
        "below_BB-": "deduction",
    },
    # Non-senior tranches (granular)
    "non_senior_granular": {
        "AAA": 12, "AA": 15, "A+": 18, "A": 20, "A-": 35,
        "BBB+": 50, "BBB": 75, "BBB-": 100,
        "BB+": 250, "BB": 425, "BB-": 650,
        "below_BB-": "deduction",
    },
    # Non-senior tranches (non-granular)
    "non_senior_non_granular": {
        "AAA": 20, "AA": 25, "A+": 30, "A": 35, "A-": 40,
        "BBB+": 65, "BBB": 100, "BBB-": 150,
        "BB+": 300, "BB": 500, "BB-": 750,
        "below_BB-": "deduction",
    },
}

# RBA Risk Weights for short-term ratings (Para 616)
RBA_RISK_WEIGHTS_SHORT_TERM = {
    "senior": {
        "A-1/P-1": 7, "A-2/P-2": 12, "A-3/P-3": 60,
        "below_A-3": "deduction",
    },
    "non_senior": {
        "A-1/P-1": 12, "A-2/P-2": 20, "A-3/P-3": 75,
        "below_A-3": "deduction",
    },
}


def get_rba_risk_weight(
    rating: str,
    is_senior: bool = True,
    is_granular: bool = True,
    is_short_term: bool = False
) -> float | str:
    """
    Get RBA risk weight based on rating and tranche characteristics.

    Parameters:
    -----------
    rating : str
        External credit rating
    is_senior : bool
        Whether tranche is senior
    is_granular : bool
        Whether pool is granular (effective N >= 6)
    is_short_term : bool
        Whether using short-term ratings

    Returns:
    --------
    float or str
        Risk weight (%) or "deduction"
    """
    if is_short_term:
        table_key = "senior" if is_senior else "non_senior"
        return RBA_RISK_WEIGHTS_SHORT_TERM[table_key].get(rating, "deduction")
    else:
        if is_senior:
            table_key = "senior_granular" if is_granular else "senior_non_granular"
        else:
            table_key = "non_senior_granular" if is_granular else "non_senior_non_granular"

        # Normalize rating
        if rating in ["AA+", "AA", "AA-"]:
            rating_key = "AA"
        elif rating in ["AAA"]:
            rating_key = "AAA"
        elif rating in ["A+"]:
            rating_key = "A+"
        elif rating in ["A"]:
            rating_key = "A"
        elif rating in ["A-"]:
            rating_key = "A-"
        elif rating in ["BBB+"]:
            rating_key = "BBB+"
        elif rating in ["BBB"]:
            rating_key = "BBB"
        elif rating in ["BBB-"]:
            rating_key = "BBB-"
        elif rating in ["BB+"]:
            rating_key = "BB+"
        elif rating in ["BB"]:
            rating_key = "BB"
        elif rating in ["BB-"]:
            rating_key = "BB-"
        else:
            rating_key = "below_BB-"

        return RBA_RISK_WEIGHTS_LONG_TERM[table_key].get(rating_key, "deduction")


def calculate_rba_rwa(
    ead: float,
    rating: str,
    is_senior: bool = True,
    is_granular: bool = True,
    is_short_term: bool = False
) -> dict:
    """
    Calculate RWA using Ratings-Based Approach.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    rating : str
        External credit rating
    is_senior : bool
        Whether tranche is senior
    is_granular : bool
        Whether pool is granular
    is_short_term : bool
        Whether using short-term rating

    Returns:
    --------
    dict
        RBA calculation results
    """
    risk_weight = get_rba_risk_weight(rating, is_senior, is_granular, is_short_term)

    if risk_weight == "deduction":
        rwa = 0
        deduction = ead
        capital = ead
    else:
        rwa = ead * risk_weight / 100
        deduction = 0
        capital = rwa * 0.08

    return {
        "approach": "Basel II RBA",
        "ead": ead,
        "rating": rating,
        "is_senior": is_senior,
        "is_granular": is_granular,
        "is_short_term": is_short_term,
        "risk_weight_pct": risk_weight if risk_weight != "deduction" else 1250,
        "rwa": rwa,
        "deduction": deduction,
        "capital_requirement": capital,
    }


# =============================================================================
# RE-SECURITISATION (Para 611-615)
# =============================================================================

def pd_to_resec_grade(pd: float) -> tuple[int, str]:
    """
    Map PD to re-securitisation rating grade.

    Args:
        pd: Probability of Default as decimal

    Returns:
        Tuple of (grade, rating_label)
    """
    for threshold, grade in RESEC_PD_THRESHOLDS:
        if pd <= threshold:
            return grade, RESEC_RATING_LABELS[grade]
    return 12, RESEC_RATING_LABELS[12]


def get_resec_risk_weight(
    rating_grade: int,
    is_senior: bool = True
) -> float:
    """
    Get re-securitisation risk weight.

    Args:
        rating_grade: Rating grade 1-12
        is_senior: Whether tranche is senior

    Returns:
        Risk weight as percentage
    """
    grade = max(1, min(12, rating_grade))
    senior_rw, non_senior_rw = RESEC_RISK_WEIGHTS[grade]
    return senior_rw if is_senior else non_senior_rw


def calculate_resec_rwa(
    ead: float,
    rating_grade: int = None,
    pd: float = None,
    is_senior: bool = True
) -> dict:
    """
    Calculate RWA for re-securitisation exposures.

    Re-securitisation includes CDO-squared, re-packaged securitisations,
    and other structures where the underlying pool contains securitisation
    exposures.

    Args:
        ead: Exposure at Default
        rating_grade: Rating grade 1-12 (if known)
        pd: Probability of Default (used to derive rating if grade not provided)
        is_senior: Whether tranche is senior

    Returns:
        dict with RWA calculation
    """
    if rating_grade is None:
        if pd is None:
            raise ValueError("Must provide either rating_grade or pd")
        rating_grade, rating_label = pd_to_resec_grade(pd)
    else:
        rating_label = RESEC_RATING_LABELS.get(rating_grade, "N/A")

    risk_weight = get_resec_risk_weight(rating_grade, is_senior)

    if risk_weight >= 1250:
        rwa = 0
        deduction = ead
        capital = ead
    else:
        rwa = ead * risk_weight / 100
        deduction = 0
        capital = rwa * 0.08

    return {
        "approach": "Basel II RBA (Re-Securitisation)",
        "ead": ead,
        "rating_grade": rating_grade,
        "rating_label": rating_label,
        "is_senior": is_senior,
        "is_resec": True,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "deduction": deduction,
        "capital_requirement": capital,
    }


def compare_sec_vs_resec(
    ead: float,
    rating: str,
    is_senior: bool = True,
    is_granular: bool = True
) -> dict:
    """
    Compare standard securitisation vs re-securitisation RWA.

    Args:
        ead: Exposure at Default
        rating: External rating
        is_senior: Whether senior
        is_granular: Whether granular (for standard sec)

    Returns:
        dict with comparison
    """
    # Standard securitisation
    sec_result = calculate_rba_rwa(ead, rating, is_senior, is_granular)

    # Map rating to re-sec grade
    rating_to_grade = {
        "AAA": 1, "AA+": 2, "AA": 2, "AA-": 2,
        "A+": 3, "A": 4, "A-": 5,
        "BBB+": 6, "BBB": 7, "BBB-": 8,
        "BB+": 9, "BB": 10, "BB-": 11,
    }
    grade = rating_to_grade.get(rating, 12)

    # Re-securitisation
    resec_result = calculate_resec_rwa(ead, rating_grade=grade, is_senior=is_senior)

    return {
        "ead": ead,
        "rating": rating,
        "is_senior": is_senior,
        "standard_sec": {
            "risk_weight_pct": sec_result["risk_weight_pct"],
            "rwa": sec_result["rwa"],
            "capital": sec_result["capital_requirement"],
        },
        "resec": {
            "risk_weight_pct": resec_result["risk_weight_pct"],
            "rwa": resec_result["rwa"],
            "capital": resec_result["capital_requirement"],
        },
        "rw_difference_pct": resec_result["risk_weight_pct"] - sec_result["risk_weight_pct"],
        "capital_difference": resec_result["capital_requirement"] - sec_result["capital_requirement"],
    }


# =============================================================================
# Supervisory Formula Approach (SFA) - Para 619-636
# =============================================================================

def calculate_sfa_kirb(
    underlying_exposures: list[dict]
) -> float:
    """
    Calculate Kirb - the IRB capital charge for the underlying pool.

    Kirb = sum(K_i * EAD_i) / sum(EAD_i)

    Parameters:
    -----------
    underlying_exposures : list of dict
        Each with: ead, pd, lgd, maturity

    Returns:
    --------
    float
        Kirb as a decimal
    """
    if not underlying_exposures:
        return 0.08

    total_k_ead = 0
    total_ead = 0

    for exp in underlying_exposures:
        ead = exp.get("ead", 0)
        pd = max(exp.get("pd", 0.01), 0.0003)
        lgd = exp.get("lgd", 0.45)
        maturity = exp.get("maturity", 2.5)

        # Basel II IRB formula (simplified)
        r = 0.12 * (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)) + \
            0.24 * (1 - (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)))

        g_pd = norm.ppf(pd)
        g_conf = norm.ppf(0.999)
        conditional_pd = norm.cdf((1 - r) ** (-0.5) * g_pd + (r / (1 - r)) ** 0.5 * g_conf)

        k_base = lgd * conditional_pd - pd * lgd

        # Maturity adjustment
        b = (0.11852 - 0.05478 * math.log(pd)) ** 2
        k = k_base * (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)

        total_k_ead += k * ead
        total_ead += ead

    return total_k_ead / total_ead if total_ead > 0 else 0.08


def calculate_sfa_rw(
    kirb: float,
    l: float,  # Credit enhancement level (attachment)
    t: float,  # Tranche thickness
    n: int = 25,
    lgd_pool: float = 0.45,
    tau: float = 1000  # Number of pool exposures
) -> float:
    """
    Calculate SFA risk weight using the supervisory formula.

    Parameters:
    -----------
    kirb : float
        Pool IRB capital charge
    l : float
        Credit enhancement level (attachment point)
    t : float
        Tranche thickness (detachment - attachment)
    n : int
        Effective number of exposures
    lgd_pool : float
        Pool average LGD
    tau : float
        Number of exposures in pool

    Returns:
    --------
    float
        Risk weight (%) or 1250 for deduction
    """
    if kirb <= 0:
        return 7  # Minimum

    # Omega parameter
    omega = 20

    # Calculate supervisory parameters
    h = (1 - kirb / lgd_pool) ** n

    # Beta function approximation
    v = (lgd_pool - kirb) * kirb + 0.25 * (1 - lgd_pool) * kirb
    if v > 0:
        f = (v + kirb ** 2) / (1 - h)
    else:
        f = kirb

    # Capital requirement for tranche
    beta = kirb / lgd_pool
    a = (1 - beta) / (1 - kirb)

    # S(L) function
    if l < kirb:
        s_l = l
    else:
        k = (1 + omega * (kirb - l)) * math.exp(-omega * (kirb - l))
        s_l = kirb + (l - kirb) * k

    # S(L+T) function
    l_plus_t = l + t
    if l_plus_t < kirb:
        s_l_t = l_plus_t
    else:
        k = (1 + omega * (kirb - l_plus_t)) * math.exp(-omega * (kirb - l_plus_t))
        s_l_t = kirb + (l_plus_t - kirb) * k

    # Capital for tranche
    k_tranche = (s_l_t - s_l) / t if t > 0 else 0

    # Convert to risk weight
    risk_weight = k_tranche * 12.5 * 100

    # Floor at 7%, cap at 1250%
    return max(7, min(1250, risk_weight))


def calculate_sfa_rwa(
    ead: float,
    attachment: float,
    detachment: float,
    kirb: float = None,
    underlying_exposures: list[dict] = None,
    n: int = 25,
    lgd_pool: float = 0.45
) -> dict:
    """
    Calculate RWA using Supervisory Formula Approach.

    Parameters:
    -----------
    ead : float
        Tranche exposure
    attachment : float
        Attachment point (e.g., 0.05 for 5%)
    detachment : float
        Detachment point (e.g., 0.15 for 15%)
    kirb : float
        Pre-calculated Kirb (if None, calculated from exposures)
    underlying_exposures : list of dict
        Underlying pool for Kirb calculation
    n : int
        Effective number of exposures
    lgd_pool : float
        Pool average LGD

    Returns:
    --------
    dict
        SFA calculation results
    """
    # Calculate Kirb if not provided
    if kirb is None:
        if underlying_exposures:
            kirb = calculate_sfa_kirb(underlying_exposures)
        else:
            kirb = 0.06  # Default assumption

    # Tranche parameters
    l = attachment  # Credit enhancement
    t = detachment - attachment  # Thickness

    # Calculate risk weight
    risk_weight = calculate_sfa_rw(kirb, l, t, n, lgd_pool)

    if risk_weight >= 1250:
        rwa = 0
        deduction = ead
        capital = ead
    else:
        rwa = ead * risk_weight / 100
        deduction = 0
        capital = rwa * 0.08

    return {
        "approach": "Basel II SFA",
        "ead": ead,
        "attachment": attachment,
        "detachment": detachment,
        "thickness": t,
        "credit_enhancement": l,
        "kirb": kirb,
        "n": n,
        "lgd_pool": lgd_pool,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "deduction": deduction,
        "capital_requirement": capital,
    }


# =============================================================================
# Internal Assessment Approach (IAA) - Para 619
# =============================================================================

# IAA uses internal ratings mapped to RBA risk weights
IAA_RATING_MAPPING = {
    # Internal grade : Equivalent external rating
    1: "AAA",
    2: "AA",
    3: "A+",
    4: "A",
    5: "A-",
    6: "BBB+",
    7: "BBB",
    8: "BBB-",
    9: "BB+",
    10: "BB",
    11: "BB-",
    12: "below_BB-",
}


def calculate_iaa_rwa(
    ead: float,
    internal_grade: int,
    is_senior: bool = True,
    is_granular: bool = True
) -> dict:
    """
    Calculate RWA using Internal Assessment Approach.

    IAA allows banks to use internal ratings for unrated ABCP exposures,
    mapping to RBA risk weights.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    internal_grade : int
        Bank's internal grade (1-12, where 1 = best)
    is_senior : bool
        Whether tranche is senior
    is_granular : bool
        Whether pool is granular

    Returns:
    --------
    dict
        IAA calculation results
    """
    # Map internal grade to external rating
    rating = IAA_RATING_MAPPING.get(internal_grade, "below_BB-")

    # Get RBA risk weight for the mapped rating
    risk_weight = get_rba_risk_weight(rating, is_senior, is_granular, is_short_term=False)

    if risk_weight == "deduction":
        rwa = 0
        deduction = ead
        capital = ead
    else:
        rwa = ead * risk_weight / 100
        deduction = 0
        capital = rwa * 0.08

    return {
        "approach": "Basel II IAA",
        "ead": ead,
        "internal_grade": internal_grade,
        "mapped_rating": rating,
        "is_senior": is_senior,
        "is_granular": is_granular,
        "risk_weight_pct": risk_weight if risk_weight != "deduction" else 1250,
        "rwa": rwa,
        "deduction": deduction,
        "capital_requirement": capital,
    }


# =============================================================================
# Comparison Functions
# =============================================================================

def compare_securitization_approaches(
    ead: float,
    rating: str,
    attachment: float,
    detachment: float,
    kirb: float = 0.06,
    is_senior: bool = True,
    is_granular: bool = True,
    n: int = 25,
    internal_grade: int = None
) -> dict:
    """
    Compare all three Basel II securitization approaches.

    Parameters:
    -----------
    ead : float
        Tranche exposure
    rating : str
        External rating (for RBA)
    attachment : float
        Attachment point (for SFA)
    detachment : float
        Detachment point (for SFA)
    kirb : float
        Pool Kirb (for SFA)
    is_senior : bool
        Whether senior
    is_granular : bool
        Whether granular
    n : int
        Effective N (for SFA)
    internal_grade : int
        Internal rating (for IAA)

    Returns:
    --------
    dict
        Comparison results
    """
    # RBA
    rba = calculate_rba_rwa(ead, rating, is_senior, is_granular)

    # SFA
    sfa = calculate_sfa_rwa(ead, attachment, detachment, kirb=kirb, n=n)

    # IAA (if internal grade provided)
    if internal_grade:
        iaa = calculate_iaa_rwa(ead, internal_grade, is_senior, is_granular)
    else:
        iaa = None

    # Compare
    results = [
        ("RBA", rba["capital_requirement"]),
        ("SFA", sfa["capital_requirement"]),
    ]
    if iaa:
        results.append(("IAA", iaa["capital_requirement"]))

    results_sorted = sorted(results, key=lambda x: x[1], reverse=True)

    return {
        "ead": ead,
        "rating": rating,
        "attachment": attachment,
        "detachment": detachment,
        "rba": rba,
        "sfa": sfa,
        "iaa": iaa,
        "most_conservative": results_sorted[0][0],
        "least_conservative": results_sorted[-1][0],
        "ranking": [r[0] for r in results_sorted],
    }


# =============================================================================
# PD-Based Wrappers
# =============================================================================

# Import rating mapping from IRB module
from .credit_risk_irb import get_rating_from_pd, RATING_TO_PD


def calculate_rba_rwa_from_pd(
    ead: float,
    pd: float,
    is_senior: bool = True,
    is_granular: bool = True
) -> dict:
    """
    Calculate RBA RWA using PD instead of rating.

    Parameters:
    -----------
    ead : float
        Tranche exposure
    pd : float
        Probability of Default (e.g., 0.02 for 2%)
    is_senior : bool
        Whether tranche is senior
    is_granular : bool
        Whether pool is granular

    Returns:
    --------
    dict
        RBA calculation with derived rating
    """
    # Derive rating from PD
    derived_rating = get_rating_from_pd(pd)

    # Calculate using standard RBA function
    result = calculate_rba_rwa(ead, derived_rating, is_senior, is_granular)

    # Add PD-related fields
    result["input_pd"] = pd
    result["derived_rating"] = derived_rating
    result["rating_pd"] = RATING_TO_PD.get(derived_rating, pd)

    return result


def calculate_iaa_rwa_from_pd(
    ead: float,
    pd: float,
    is_senior: bool = True,
    is_granular: bool = True
) -> dict:
    """
    Calculate IAA RWA using PD to derive internal grade.

    Maps PD to internal grade (1-12) based on rating thresholds.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default
    is_senior : bool
        Whether tranche is senior
    is_granular : bool
        Whether pool is granular

    Returns:
    --------
    dict
        IAA calculation with derived internal grade
    """
    # Derive rating from PD
    derived_rating = get_rating_from_pd(pd)

    # Map rating to internal grade
    rating_to_grade = {
        "AAA": 1, "AA+": 2, "AA": 2, "AA-": 2,
        "A+": 3, "A": 4, "A-": 5,
        "BBB+": 6, "BBB": 7, "BBB-": 8,
        "BB+": 9, "BB": 10, "BB-": 11,
    }
    internal_grade = rating_to_grade.get(derived_rating, 12)

    # Calculate using standard IAA function
    result = calculate_iaa_rwa(ead, internal_grade, is_senior, is_granular)

    # Add PD-related fields
    result["input_pd"] = pd
    result["derived_rating"] = derived_rating
    result["rating_pd"] = RATING_TO_PD.get(derived_rating, pd)

    return result


def compare_securitization_approaches_from_pd(
    ead: float,
    pd: float,
    attachment: float,
    detachment: float,
    kirb: float = 0.06,
    is_senior: bool = True,
    is_granular: bool = True,
    n: int = 25
) -> dict:
    """
    Compare all securitization approaches using PD instead of rating.

    Parameters:
    -----------
    ead : float
        Tranche exposure
    pd : float
        Probability of Default for rating derivation
    attachment : float
        Attachment point (for SFA)
    detachment : float
        Detachment point (for SFA)
    kirb : float
        Pool Kirb (for SFA)
    is_senior : bool
        Whether senior
    is_granular : bool
        Whether granular
    n : int
        Effective N (for SFA)

    Returns:
    --------
    dict
        Comparison results
    """
    # Derive rating from PD
    derived_rating = get_rating_from_pd(pd)

    # Use standard comparison with derived rating
    result = compare_securitization_approaches(
        ead=ead,
        rating=derived_rating,
        attachment=attachment,
        detachment=detachment,
        kirb=kirb,
        is_senior=is_senior,
        is_granular=is_granular,
        n=n,
        internal_grade=None  # Will be calculated from rating
    )

    # Add PD-related fields
    result["input_pd"] = pd
    result["derived_rating"] = derived_rating

    return result


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Securitization Framework")
    print("=" * 70)

    # RBA Examples
    print("\n  Ratings-Based Approach (RBA):")
    print(f"\n  {'Rating':<10} {'Senior':>10} {'Non-Senior':>12} {'RW (Sr)':>10} {'RW (NS)':>10}")
    print(f"  {'-'*10} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")

    for rating in ["AAA", "AA", "A", "BBB", "BB", "B"]:
        rw_sr = get_rba_risk_weight(rating, is_senior=True, is_granular=True)
        rw_ns = get_rba_risk_weight(rating, is_senior=False, is_granular=True)
        print(f"  {rating:<10} {'Yes':>10} {'No':>12} "
              f"{rw_sr if rw_sr != 'deduction' else 'Ded.':>9}% "
              f"{rw_ns if rw_ns != 'deduction' else 'Ded.':>9}%")

    # SFA Example
    print("\n" + "=" * 70)
    print("Supervisory Formula Approach (SFA)")
    print("=" * 70)

    tranches = [
        {"name": "Senior (15-100%)", "a": 0.15, "d": 1.00},
        {"name": "Mezzanine (8-15%)", "a": 0.08, "d": 0.15},
        {"name": "Mezz BBB (4-8%)", "a": 0.04, "d": 0.08},
        {"name": "Junior (1-4%)", "a": 0.01, "d": 0.04},
        {"name": "First Loss (0-1%)", "a": 0.00, "d": 0.01},
    ]

    print(f"\n  Kirb = 6%, N = 50, LGD = 45%")
    print(f"\n  {'Tranche':<20} {'Attach':>8} {'Detach':>8} {'RW':>10} {'Capital':>12}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*10} {'-'*12}")

    for t in tranches:
        sfa = calculate_sfa_rwa(
            ead=1_000_000,
            attachment=t["a"],
            detachment=t["d"],
            kirb=0.06,
            n=50,
            lgd_pool=0.45
        )
        rw_str = f"{sfa['risk_weight_pct']:.0f}%" if sfa['risk_weight_pct'] < 1250 else "Deduct"
        print(f"  {t['name']:<20} {t['a']*100:>7.0f}% {t['d']*100:>7.0f}% "
              f"{rw_str:>10} ${sfa['capital_requirement']:>10,.0f}")

    # Comparison
    print("\n" + "=" * 70)
    print("Approach Comparison (Senior BBB tranche, 5%-10%)")
    print("=" * 70)

    comp = compare_securitization_approaches(
        ead=1_000_000,
        rating="BBB",
        attachment=0.05,
        detachment=0.10,
        kirb=0.06,
        is_senior=True,
        internal_grade=7  # Equivalent to BBB
    )

    print(f"\n  {'Approach':<10} {'RW':>10} {'RWA':>15} {'Capital':>12}")
    print(f"  {'-'*10} {'-'*10} {'-'*15} {'-'*12}")
    print(f"  {'RBA':<10} {comp['rba']['risk_weight_pct']:>9.0f}% "
          f"${comp['rba']['rwa']:>13,.0f} ${comp['rba']['capital_requirement']:>10,.0f}")
    print(f"  {'SFA':<10} {comp['sfa']['risk_weight_pct']:>9.0f}% "
          f"${comp['sfa']['rwa']:>13,.0f} ${comp['sfa']['capital_requirement']:>10,.0f}")
    print(f"  {'IAA':<10} {comp['iaa']['risk_weight_pct']:>9.0f}% "
          f"${comp['iaa']['rwa']:>13,.0f} ${comp['iaa']['capital_requirement']:>10,.0f}")
    print(f"\n  Most conservative: {comp['most_conservative']}")
