"""
RWA Calculator - Multi-Approach Comparison

Calculates Risk-Weighted Assets using:
- SA-CR (KSA): Standardised Approach for Credit Risk
- IRB Foundation: PD estimated by bank, LGD prescribed by regulation
- ERBA: External Ratings Based Approach for securitizations

Allows comparison between approaches.
"""

import math
from scipy.stats import norm


# =============================================================================
# SA-CR / KSA (Standardised Approach for Credit Risk) - Basel III/IV
# =============================================================================

# Sovereign risk weights based on external ratings (CRE20.7)
SA_SOVEREIGN_RW = {
    "AAA": 0, "AA+": 0, "AA": 0, "AA-": 0,
    "A+": 20, "A": 20, "A-": 20,
    "BBB+": 50, "BBB": 50, "BBB-": 50,
    "BB+": 100, "BB": 100, "BB-": 100,
    "B+": 100, "B": 100, "B-": 100,
    "below_B-": 150,
    "unrated": 100,
}

# Bank risk weights - External Credit Risk Assessment (ECRA) approach (CRE20.16)
SA_BANK_ECRA_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 30, "A": 30, "A-": 30,
    "BBB+": 50, "BBB": 50, "BBB-": 50,
    "BB+": 100, "BB": 100, "BB-": 100,
    "B+": 100, "B": 100, "B-": 100,
    "below_B-": 150,
    "unrated": 50,  # Grade B under SCRA
}

# Bank risk weights - short-term exposures (maturity <= 3 months)
SA_BANK_ECRA_SHORT_TERM_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 20, "A": 20, "A-": 20,
    "BBB+": 20, "BBB": 20, "BBB-": 20,
    "BB+": 50, "BB": 50, "BB-": 50,
    "B+": 50, "B": 50, "B-": 50,
    "below_B-": 150,
    "unrated": 20,
}

# Bank risk weights - Standardised Credit Risk Assessment (SCRA) approach (CRE20.21)
SA_BANK_SCRA_RW = {
    "A": 40,   # Grade A: meets/exceeds regulatory requirements, CET1 >= 14%, Tier1 >= 15.5%
    "B": 75,   # Grade B: meets regulatory requirements
    "C": 150,  # Grade C: does not meet requirements
}

SA_BANK_SCRA_SHORT_TERM_RW = {
    "A": 20,
    "B": 50,
    "C": 150,
}

# Corporate risk weights based on external ratings (CRE20.25)
SA_CORPORATE_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 50, "A": 50, "A-": 50,
    "BBB+": 75, "BBB": 75, "BBB-": 75,
    "BB+": 100, "BB": 100, "BB-": 100,
    "below_BB-": 150,
    "unrated": 100,
}

# Retail risk weights (CRE20.47)
SA_RETAIL_RW = {
    "regulatory_retail": 75,        # General retail meeting criteria
    "transactor": 45,               # Credit card transactors (pay in full)
}

# Real estate risk weights based on LTV (CRE20.71-82) - Residential
SA_RESIDENTIAL_RE_RW = {
    # LTV bucket: (general, income_producing)
    "ltv_50": (20, 30),
    "ltv_60": (25, 35),
    "ltv_80": (30, 45),
    "ltv_90": (40, 60),
    "ltv_100": (50, 75),
    "ltv_above_100": (70, 105),
}

# Commercial real estate risk weights based on LTV (CRE20.85-90)
SA_COMMERCIAL_RE_RW = {
    "ltv_60": 70,
    "ltv_80": 90,
    "above_ltv_80": 110,  # or min(counterparty RW, 110%)
}

# Subordinated debt and equity (CRE20.52)
SA_SUBORDINATED_RW = 150
SA_EQUITY_RW = {
    "speculative_unlisted": 400,
    "other": 250,
    "banking_book_listed": 100,
}

# Defaulted exposures (CRE20.56)
SA_DEFAULTED_RW = {
    "unsecured": 150,
    "secured_residential": 100,  # if specific provisions >= 20%
}


def get_sa_sovereign_rw(rating: str = "unrated") -> float:
    """Get SA risk weight for sovereign exposures."""
    return SA_SOVEREIGN_RW.get(rating, SA_SOVEREIGN_RW.get("unrated", 100))


def get_sa_bank_rw(
    rating: str = "unrated",
    approach: str = "ECRA",
    scra_grade: str = "B",
    short_term: bool = False
) -> float:
    """
    Get SA risk weight for bank exposures.

    Parameters:
    -----------
    rating : str
        External rating (for ECRA approach)
    approach : str
        "ECRA" (external ratings) or "SCRA" (standardised assessment)
    scra_grade : str
        "A", "B", or "C" (for SCRA approach)
    short_term : bool
        True if maturity <= 3 months
    """
    if approach == "SCRA":
        if short_term:
            return SA_BANK_SCRA_SHORT_TERM_RW.get(scra_grade, 75)
        return SA_BANK_SCRA_RW.get(scra_grade, 75)
    else:  # ECRA
        if short_term:
            return SA_BANK_ECRA_SHORT_TERM_RW.get(rating, 50)
        return SA_BANK_ECRA_RW.get(rating, 50)


def get_sa_corporate_rw(
    rating: str = "unrated",
    is_sme: bool = False
) -> float:
    """
    Get SA risk weight for corporate exposures.

    Parameters:
    -----------
    rating : str
        External rating
    is_sme : bool
        True for SME corporates (applies 85% factor for unrated)
    """
    base_rw = SA_CORPORATE_RW.get(rating, 100)

    # SME supporting factor for unrated exposures
    if is_sme and rating == "unrated":
        return base_rw * 0.85  # 85% of standard RW
    return base_rw


def get_sa_retail_rw(retail_type: str = "regulatory_retail") -> float:
    """Get SA risk weight for retail exposures."""
    return SA_RETAIL_RW.get(retail_type, 75)


def get_sa_real_estate_rw(
    ltv: float,
    property_type: str = "residential",
    income_producing: bool = False
) -> float:
    """
    Get SA risk weight for real estate exposures based on LTV.

    Parameters:
    -----------
    ltv : float
        Loan-to-Value ratio (e.g., 0.75 for 75%)
    property_type : str
        "residential" or "commercial"
    income_producing : bool
        True if repayment depends on cash flows from property
    """
    ltv_pct = ltv * 100 if ltv <= 1 else ltv  # Handle both 0.75 and 75 formats

    if property_type == "residential":
        if ltv_pct <= 50:
            rw = SA_RESIDENTIAL_RE_RW["ltv_50"]
        elif ltv_pct <= 60:
            rw = SA_RESIDENTIAL_RE_RW["ltv_60"]
        elif ltv_pct <= 80:
            rw = SA_RESIDENTIAL_RE_RW["ltv_80"]
        elif ltv_pct <= 90:
            rw = SA_RESIDENTIAL_RE_RW["ltv_90"]
        elif ltv_pct <= 100:
            rw = SA_RESIDENTIAL_RE_RW["ltv_100"]
        else:
            rw = SA_RESIDENTIAL_RE_RW["ltv_above_100"]

        return rw[1] if income_producing else rw[0]

    else:  # commercial
        if ltv_pct <= 60:
            return SA_COMMERCIAL_RE_RW["ltv_60"]
        elif ltv_pct <= 80:
            return SA_COMMERCIAL_RE_RW["ltv_80"]
        else:
            return SA_COMMERCIAL_RE_RW["above_ltv_80"]


def calculate_sa_rwa(
    ead: float,
    exposure_class: str,
    rating: str = "unrated",
    **kwargs
) -> dict:
    """
    Calculate RWA using SA-CR (Standardised Approach).

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_class : str
        One of: "sovereign", "bank", "corporate", "retail", "residential_re",
        "commercial_re", "defaulted", "equity"
    rating : str
        External credit rating (where applicable)
    **kwargs : dict
        Additional parameters depending on exposure class:
        - bank: approach, scra_grade, short_term
        - corporate: is_sme
        - retail: retail_type
        - real_estate: ltv, income_producing

    Returns:
    --------
    dict
        Dictionary with RWA and intermediate values
    """
    if exposure_class == "sovereign":
        risk_weight = get_sa_sovereign_rw(rating)

    elif exposure_class == "bank":
        risk_weight = get_sa_bank_rw(
            rating=rating,
            approach=kwargs.get("approach", "ECRA"),
            scra_grade=kwargs.get("scra_grade", "B"),
            short_term=kwargs.get("short_term", False)
        )

    elif exposure_class == "corporate":
        risk_weight = get_sa_corporate_rw(
            rating=rating,
            is_sme=kwargs.get("is_sme", False)
        )

    elif exposure_class == "retail":
        risk_weight = get_sa_retail_rw(kwargs.get("retail_type", "regulatory_retail"))

    elif exposure_class == "residential_re":
        risk_weight = get_sa_real_estate_rw(
            ltv=kwargs.get("ltv", 0.80),
            property_type="residential",
            income_producing=kwargs.get("income_producing", False)
        )

    elif exposure_class == "commercial_re":
        risk_weight = get_sa_real_estate_rw(
            ltv=kwargs.get("ltv", 0.80),
            property_type="commercial"
        )

    elif exposure_class == "defaulted":
        if kwargs.get("secured_residential", False):
            risk_weight = SA_DEFAULTED_RW["secured_residential"]
        else:
            risk_weight = SA_DEFAULTED_RW["unsecured"]

    elif exposure_class == "equity":
        equity_type = kwargs.get("equity_type", "other")
        risk_weight = SA_EQUITY_RW.get(equity_type, 250)

    else:
        raise ValueError(f"Unknown exposure class: {exposure_class}")

    rwa = ead * risk_weight / 100

    return {
        "approach": "SA-CR",
        "ead": ead,
        "exposure_class": exposure_class,
        "rating": rating,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
        "parameters": kwargs,
    }


def calculate_batch_sa_rwa(exposures: list[dict]) -> dict:
    """
    Calculate SA-CR RWA for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict should have: ead, exposure_class, and optionally rating and class-specific params

    Returns:
    --------
    dict
        Aggregated results
    """
    results = []
    total_ead = 0
    total_rwa = 0

    for exp in exposures:
        # Extract standard params
        ead = exp["ead"]
        exposure_class = exp["exposure_class"]
        rating = exp.get("rating", "unrated")

        # Extract class-specific kwargs
        kwargs = {k: v for k, v in exp.items() if k not in ["ead", "exposure_class", "rating"]}

        result = calculate_sa_rwa(ead, exposure_class, rating, **kwargs)
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]

    return {
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "exposures": results,
    }


def compare_sa_vs_irb(
    ead: float,
    exposure_class: str,
    rating: str = "unrated",
    pd: float = None,
    lgd: float = 0.45,
    maturity: float = 2.5,
    **kwargs
) -> dict:
    """
    Compare SA-CR vs IRB-F for the same exposure.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_class : str
        SA exposure class
    rating : str
        External rating
    pd : float
        PD for IRB (if None, derived from rating)
    lgd : float
        LGD for IRB
    maturity : float
        Effective maturity for IRB
    **kwargs : dict
        Additional SA parameters

    Returns:
    --------
    dict
        Comparison results
    """
    # SA calculation
    sa_result = calculate_sa_rwa(ead, exposure_class, rating, **kwargs)

    # Map exposure class to IRB asset class
    irb_asset_class_map = {
        "sovereign": "corporate",
        "bank": "corporate",
        "corporate": "corporate",
        "retail": "retail_other",
        "residential_re": "retail_mortgage",
        "commercial_re": "corporate",
    }
    irb_asset_class = irb_asset_class_map.get(exposure_class, "corporate")

    # Get PD from rating if not provided
    if pd is None:
        pd = RATING_TO_PD.get(rating, 0.01)

    # IRB calculation
    irb_result = calculate_rwa(ead, pd, lgd, maturity, irb_asset_class)
    irb_result["approach"] = "IRB-F"

    # Calculate differences
    rwa_diff = irb_result["rwa"] - sa_result["rwa"]

    return {
        "ead": ead,
        "exposure_class": exposure_class,
        "rating": rating,
        "pd_used": pd,
        "sa": sa_result,
        "irb": irb_result,
        "rwa_difference": rwa_diff,
        "risk_weight_difference": irb_result["risk_weight_pct"] - sa_result["risk_weight_pct"],
        "more_conservative": "SA" if sa_result["rwa"] > irb_result["rwa"] else "IRB",
    }


def compare_all_approaches(
    ead: float,
    rating: str,
    exposure_class: str = "corporate",
    seniority: str = "senior",
    pd: float = None,
    lgd: float = 0.45,
    maturity: float = 2.5,
    **kwargs
) -> dict:
    """
    Compare all three approaches: SA-CR, IRB-F, and ERBA.

    Returns:
    --------
    dict
        Full comparison across all approaches
    """
    # SA calculation
    sa_result = calculate_sa_rwa(ead, exposure_class, rating, **kwargs)

    # IRB calculation
    if pd is None:
        pd = RATING_TO_PD.get(rating, 0.01)

    irb_asset_class_map = {
        "sovereign": "corporate",
        "bank": "corporate",
        "corporate": "corporate",
        "retail": "retail_other",
        "residential_re": "retail_mortgage",
    }
    irb_asset_class = irb_asset_class_map.get(exposure_class, "corporate")
    irb_result = calculate_rwa(ead, pd, lgd, maturity, irb_asset_class)
    irb_result["approach"] = "IRB-F"

    # ERBA calculation
    erba_result = calculate_erba_rwa(ead, rating, seniority, maturity)

    # Find most/least conservative
    approaches = [
        ("SA", sa_result["rwa"]),
        ("IRB", irb_result["rwa"]),
        ("ERBA", erba_result["rwa"]),
    ]
    approaches_sorted = sorted(approaches, key=lambda x: x[1], reverse=True)

    return {
        "ead": ead,
        "rating": rating,
        "pd_used": pd,
        "sa": sa_result,
        "irb": irb_result,
        "erba": erba_result,
        "most_conservative": approaches_sorted[0][0],
        "least_conservative": approaches_sorted[-1][0],
        "ranking": [a[0] for a in approaches_sorted],
    }


# =============================================================================
# ERBA (External Ratings Based Approach) - Basel III Securitization Framework
# =============================================================================

# ERBA Risk Weight Tables (Basel III, CRE40)
# Format: {rating: {senior: (short_term, long_term), non_senior: (short_term, long_term)}}
# Short-term: maturity <= 1 year, Long-term: maturity > 1 year (5 year interpolation)

ERBA_RISK_WEIGHTS = {
    "AAA": {"senior": (15, 20), "non_senior": (15, 70)},
    "AA+": {"senior": (15, 30), "non_senior": (15, 90)},
    "AA": {"senior": (25, 40), "non_senior": (30, 120)},
    "AA-": {"senior": (30, 45), "non_senior": (40, 140)},
    "A+": {"senior": (40, 50), "non_senior": (60, 160)},
    "A": {"senior": (50, 65), "non_senior": (80, 180)},
    "A-": {"senior": (60, 70), "non_senior": (120, 210)},
    "BBB+": {"senior": (75, 90), "non_senior": (170, 260)},
    "BBB": {"senior": (90, 120), "non_senior": (220, 310)},
    "BBB-": {"senior": (120, 140), "non_senior": (330, 420)},
    "BB+": {"senior": (140, 160), "non_senior": (470, 580)},
    "BB": {"senior": (160, 180), "non_senior": (620, 760)},
    "BB-": {"senior": (200, 225), "non_senior": (750, 860)},
    "B+": {"senior": (250, 280), "non_senior": (900, 950)},
    "B": {"senior": (310, 340), "non_senior": (1000, 1250)},
    "B-": {"senior": (380, 420), "non_senior": (1250, 1250)},
    "CCC+": {"senior": (460, 580), "non_senior": (1250, 1250)},
    "CCC": {"senior": (620, 760), "non_senior": (1250, 1250)},
    "CCC-": {"senior": (1250, 1250), "non_senior": (1250, 1250)},
    "below_CCC-": {"senior": (1250, 1250), "non_senior": (1250, 1250)},
}

# Approximate PD mapping from external ratings (based on historical default rates)
RATING_TO_PD = {
    "AAA": 0.0001,
    "AA+": 0.0002,
    "AA": 0.0003,
    "AA-": 0.0005,
    "A+": 0.0007,
    "A": 0.0009,
    "A-": 0.0015,
    "BBB+": 0.0025,
    "BBB": 0.0040,
    "BBB-": 0.0075,
    "BB+": 0.0125,
    "BB": 0.0200,
    "BB-": 0.0350,
    "B+": 0.0550,
    "B": 0.0900,
    "B-": 0.1400,
    "CCC+": 0.2000,
    "CCC": 0.2700,
    "CCC-": 0.3500,
    "below_CCC-": 0.5000,
}

# Sorted list for reverse lookup (PD -> Rating)
_PD_RATING_SORTED = sorted(RATING_TO_PD.items(), key=lambda x: x[1])


def get_rating_from_pd(pd: float) -> str:
    """
    Get the closest external rating for a given PD value.

    Uses the RATING_TO_PD mapping to find the rating whose PD is closest
    to the provided value. This enables using PD-based data with rating-based
    methodologies (SA-CR, ERBA, IAA).

    Parameters:
    -----------
    pd : float
        Probability of Default (e.g., 0.02 for 2%)

    Returns:
    --------
    str
        The closest external rating (e.g., "BB" for PD around 2%)

    Examples:
    ---------
    >>> get_rating_from_pd(0.02)
    'BB'
    >>> get_rating_from_pd(0.005)
    'BBB'
    >>> get_rating_from_pd(0.0001)
    'AAA'
    """
    if pd <= 0:
        return "AAA"
    if pd >= 0.5:
        return "below_CCC-"

    # Find the closest rating by PD
    best_rating = "BBB"  # Default
    min_distance = float("inf")

    for rating, rating_pd in _PD_RATING_SORTED:
        distance = abs(pd - rating_pd)
        if distance < min_distance:
            min_distance = distance
            best_rating = rating

    return best_rating


def get_pd_range_for_rating(rating: str) -> tuple[float, float]:
    """
    Get the PD range that maps to a given rating.

    Returns the midpoint boundaries between adjacent ratings.

    Parameters:
    -----------
    rating : str
        External credit rating

    Returns:
    --------
    tuple[float, float]
        (lower_bound, upper_bound) PD range for this rating
    """
    if rating not in RATING_TO_PD:
        raise ValueError(f"Unknown rating: {rating}")

    rating_pd = RATING_TO_PD[rating]
    idx = next(i for i, (r, _) in enumerate(_PD_RATING_SORTED) if r == rating)

    # Lower bound: midpoint with previous rating (or 0)
    if idx == 0:
        lower = 0.0
    else:
        prev_pd = _PD_RATING_SORTED[idx - 1][1]
        lower = (prev_pd + rating_pd) / 2

    # Upper bound: midpoint with next rating (or 1.0)
    if idx == len(_PD_RATING_SORTED) - 1:
        upper = 1.0
    else:
        next_pd = _PD_RATING_SORTED[idx + 1][1]
        upper = (rating_pd + next_pd) / 2

    return (lower, upper)


# =============================================================================
# Unified PD-Based Calculation Functions
# =============================================================================
# These functions accept PD/LGD directly and route to the appropriate methodology,
# converting PD to rating where needed.


def calculate_rwa_from_pd(
    ead: float,
    pd: float,
    lgd: float = 0.45,
    approach: str = "IRB-F",
    maturity: float = 2.5,
    exposure_class: str = "corporate",
    asset_class: str = None,
    **kwargs
) -> dict:
    """
    Unified RWA calculation from PD/LGD - routes to the appropriate methodology.

    This is the main entry point when you have PD and LGD data and want to
    calculate RWA using any available approach. The function automatically
    converts PD to rating where needed for rating-based approaches.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default (e.g., 0.02 for 2%)
    lgd : float
        Loss Given Default (e.g., 0.45 for 45%)
    approach : str
        Calculation approach. One of:
        - "IRB-F": Foundation IRB (uses PD directly)
        - "A-IRB": Advanced IRB (uses PD directly)
        - "SA-CR": Standardised Approach (converts PD to rating)
        - "ERBA": External Ratings Based Approach (converts PD to rating)
        - "IAA": Internal Assessment Approach (converts PD to rating)
    maturity : float
        Effective maturity in years
    exposure_class : str
        For SA-CR: sovereign, bank, corporate, retail, residential_re, etc.
    asset_class : str
        For IRB: corporate, retail_mortgage, retail_revolving, retail_other
        If None, defaults to "corporate"
    **kwargs : dict
        Additional parameters for specific approaches:
        - SA-CR: is_sme, approach (ECRA/SCRA), short_term, ltv, etc.
        - ERBA: seniority ("senior"/"non_senior")
        - IAA: is_liquidity_facility, facility_maturity

    Returns:
    --------
    dict
        RWA calculation results including derived_rating if applicable
    """
    # Default asset class
    if asset_class is None:
        asset_class = "corporate"

    # Get derived rating for rating-based approaches
    derived_rating = get_rating_from_pd(pd)

    if approach == "IRB-F":
        result = calculate_rwa(ead, pd, lgd, maturity, asset_class)
        result["approach"] = "IRB-F"
        result["derived_rating"] = derived_rating

    elif approach == "A-IRB":
        result = calculate_airb_rwa(
            ead=ead,
            pd=pd,
            lgd=lgd,
            maturity=maturity,
            asset_class=asset_class,
            lgd_downturn=kwargs.get("lgd_downturn")
        )
        result["derived_rating"] = derived_rating

    elif approach == "SA-CR":
        result = calculate_sa_rwa(
            ead=ead,
            exposure_class=exposure_class,
            rating=derived_rating,
            **kwargs
        )
        result["derived_rating"] = derived_rating
        result["pd_used"] = pd

    elif approach == "ERBA":
        seniority = kwargs.get("seniority", "senior")
        result = calculate_erba_rwa(
            ead=ead,
            rating=derived_rating,
            seniority=seniority,
            maturity=maturity
        )
        result["derived_rating"] = derived_rating
        result["pd_used"] = pd

    elif approach == "IAA":
        result = calculate_iaa_rwa(
            ead=ead,
            internal_rating=derived_rating,
            is_liquidity_facility=kwargs.get("is_liquidity_facility", False),
            facility_maturity=kwargs.get("facility_maturity", 1.0)
        )
        result["derived_rating"] = derived_rating
        result["pd_used"] = pd

    else:
        raise ValueError(
            f"Unknown approach: {approach}. "
            f"Valid approaches: IRB-F, A-IRB, SA-CR, ERBA, IAA"
        )

    return result


def calculate_securitization_rwa_from_pd(
    ead: float,
    attachment: float,
    detachment: float,
    pool_exposures: list[dict],
    approach: str = "SEC-IRBA",
    n: int = None,
    lgd: float = 0.50,
    is_sts: bool = False,
    **kwargs
) -> dict:
    """
    Calculate securitization RWA using PD/LGD data for the underlying pool.

    This function handles the conversion of pool-level PD/LGD data to
    Ksa (for SEC-SA) or Kirb (for SEC-IRBA), then calculates tranche RWA.

    Parameters:
    -----------
    ead : float
        Exposure at Default of the tranche
    attachment : float
        Attachment point (e.g., 0.05 for 5%)
    detachment : float
        Detachment point (e.g., 0.15 for 15%)
    pool_exposures : list of dict
        Underlying pool exposures. Each dict should have:
        - ead: float (required)
        - pd: float (required)
        - lgd: float (optional, defaults to 0.45)
        - maturity: float (optional, defaults to 2.5)
        - exposure_class: str (optional, for SA conversion)
        - asset_class: str (optional, for IRB)
    approach : str
        "SEC-SA" or "SEC-IRBA"
    n : int, optional
        Effective number of exposures. If None, calculated from pool.
    lgd : float
        Average pool LGD (used in supervisory formula)
    is_sts : bool
        Whether this is an STS (Simple, Transparent, Standardised) securitization
    **kwargs : dict
        Additional parameters:
        - w: float - ratio of delinquent exposures (for SEC-SA)

    Returns:
    --------
    dict
        Securitization RWA results including pool statistics
    """
    if not pool_exposures:
        raise ValueError("pool_exposures cannot be empty")

    # Calculate effective number of exposures if not provided
    if n is None:
        # N = (sum(EAD))^2 / sum(EAD^2)  - Herfindahl approximation
        total_ead = sum(exp["ead"] for exp in pool_exposures)
        sum_ead_sq = sum(exp["ead"] ** 2 for exp in pool_exposures)
        n = int((total_ead ** 2) / sum_ead_sq) if sum_ead_sq > 0 else len(pool_exposures)
        n = max(n, 1)

    if approach == "SEC-IRBA":
        # Calculate Kirb from pool IRB capital
        kirb = calculate_sec_irba_kirb(pool_exposures)

        result = calculate_sec_irba_rwa(
            ead=ead,
            attachment=attachment,
            detachment=detachment,
            kirb=kirb,
            n=n,
            lgd=lgd,
            is_sts=is_sts
        )

    elif approach == "SEC-SA":
        # Convert pool to SA exposures (need to derive ratings from PD)
        sa_exposures = []
        for exp in pool_exposures:
            pd = exp["pd"]
            derived_rating = get_rating_from_pd(pd)
            sa_exp = {
                "ead": exp["ead"],
                "exposure_class": exp.get("exposure_class", "corporate"),
                "rating": derived_rating,
            }
            # Pass through any additional SA parameters
            for key in ["is_sme", "approach", "short_term", "ltv", "income_producing"]:
                if key in exp:
                    sa_exp[key] = exp[key]
            sa_exposures.append(sa_exp)

        # Calculate Ksa from SA RWA
        ksa = calculate_sec_sa_ksa(sa_exposures)

        result = calculate_sec_sa_rwa(
            ead=ead,
            attachment=attachment,
            detachment=detachment,
            ksa=ksa,
            n=n,
            lgd=lgd,
            w=kwargs.get("w", 0.0),
            is_sts=is_sts
        )

    else:
        raise ValueError(f"Unknown approach: {approach}. Valid: SEC-SA, SEC-IRBA")

    # Add pool statistics
    total_pool_ead = sum(exp["ead"] for exp in pool_exposures)
    avg_pool_pd = sum(exp["pd"] * exp["ead"] for exp in pool_exposures) / total_pool_ead
    avg_pool_lgd = sum(exp.get("lgd", 0.45) * exp["ead"] for exp in pool_exposures) / total_pool_ead

    result["pool_statistics"] = {
        "total_ead": total_pool_ead,
        "n_exposures": len(pool_exposures),
        "effective_n": n,
        "avg_pd": avg_pool_pd,
        "avg_lgd": avg_pool_lgd,
    }

    return result


def compare_all_approaches_from_pd(
    ead: float,
    pd: float,
    lgd: float = 0.45,
    maturity: float = 2.5,
    exposure_class: str = "corporate",
    seniority: str = "senior"
) -> dict:
    """
    Compare all credit risk approaches using PD/LGD as input.

    Calculates RWA using SA-CR, IRB-F, A-IRB, and ERBA, automatically
    deriving the rating from PD for rating-based approaches.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default
    lgd : float
        Loss Given Default
    maturity : float
        Effective maturity in years
    exposure_class : str
        SA exposure class
    seniority : str
        ERBA seniority ("senior" or "non_senior")

    Returns:
    --------
    dict
        Full comparison across all approaches with ranking
    """
    derived_rating = get_rating_from_pd(pd)

    # Calculate all approaches
    sa_result = calculate_rwa_from_pd(ead, pd, lgd, "SA-CR", maturity, exposure_class)
    irb_f_result = calculate_rwa_from_pd(ead, pd, lgd, "IRB-F", maturity, exposure_class)
    airb_result = calculate_rwa_from_pd(ead, pd, lgd, "A-IRB", maturity, exposure_class)
    erba_result = calculate_rwa_from_pd(ead, pd, lgd, "ERBA", maturity, seniority=seniority)

    # Rank by RWA
    approaches = [
        ("SA-CR", sa_result["rwa"], sa_result["risk_weight_pct"]),
        ("IRB-F", irb_f_result["rwa"], irb_f_result["risk_weight_pct"]),
        ("A-IRB", airb_result["rwa"], airb_result["risk_weight_pct"]),
        ("ERBA", erba_result["rwa"], erba_result["risk_weight_pct"]),
    ]
    approaches_sorted = sorted(approaches, key=lambda x: x[1], reverse=True)

    return {
        "ead": ead,
        "pd": pd,
        "lgd": lgd,
        "maturity": maturity,
        "derived_rating": derived_rating,
        "sa": sa_result,
        "irb_f": irb_f_result,
        "airb": airb_result,
        "erba": erba_result,
        "most_conservative": approaches_sorted[0][0],
        "least_conservative": approaches_sorted[-1][0],
        "ranking": [a[0] for a in approaches_sorted],
        "rwa_range": (approaches_sorted[-1][1], approaches_sorted[0][1]),
    }


def calculate_batch_rwa_from_pd(
    exposures: list[dict],
    approach: str = "IRB-F"
) -> dict:
    """
    Calculate RWA for a batch of exposures using PD/LGD data.

    Parameters:
    -----------
    exposures : list of dict
        Each dict should have:
        - ead: float (required)
        - pd: float (required)
        - lgd: float (optional, defaults to 0.45)
        - maturity: float (optional, defaults to 2.5)
        - exposure_class: str (optional, for SA-CR)
        - asset_class: str (optional, for IRB)
        Additional kwargs depending on approach
    approach : str
        Calculation approach (IRB-F, A-IRB, SA-CR, ERBA, IAA)

    Returns:
    --------
    dict
        Aggregated results with individual exposure details
    """
    results = []
    total_ead = 0
    total_rwa = 0
    total_el = 0

    for exp in exposures:
        # Extract standard params
        ead = exp["ead"]
        pd = exp["pd"]
        lgd = exp.get("lgd", 0.45)
        maturity = exp.get("maturity", 2.5)
        exposure_class = exp.get("exposure_class", "corporate")
        asset_class = exp.get("asset_class", "corporate")

        # Extract additional kwargs
        kwargs = {
            k: v for k, v in exp.items()
            if k not in ["ead", "pd", "lgd", "maturity", "exposure_class", "asset_class"]
        }

        result = calculate_rwa_from_pd(
            ead=ead,
            pd=pd,
            lgd=lgd,
            approach=approach,
            maturity=maturity,
            exposure_class=exposure_class,
            asset_class=asset_class,
            **kwargs
        )
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]
        if "expected_loss" in result:
            total_el += result["expected_loss"]
        else:
            total_el += pd * lgd * ead

    return {
        "approach": approach,
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "total_expected_loss": total_el,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "exposure_count": len(results),
        "exposures": results,
    }


def get_erba_risk_weight(
    rating: str,
    seniority: str = "senior",
    maturity: float = 5.0
) -> float:
    """
    Get ERBA risk weight based on rating, seniority, and maturity.

    Parameters:
    -----------
    rating : str
        External credit rating (e.g., "AAA", "BB+", "B-")
    seniority : str
        "senior" or "non_senior"
    maturity : float
        Effective maturity in years

    Returns:
    --------
    float
        Risk weight as percentage (e.g., 20 for 20%)
    """
    if rating not in ERBA_RISK_WEIGHTS:
        raise ValueError(f"Unknown rating: {rating}. Valid ratings: {list(ERBA_RISK_WEIGHTS.keys())}")

    if seniority not in ["senior", "non_senior"]:
        raise ValueError(f"Seniority must be 'senior' or 'non_senior', got: {seniority}")

    rw_short, rw_long = ERBA_RISK_WEIGHTS[rating][seniority]

    # Linear interpolation between 1 year and 5 years
    if maturity <= 1:
        return rw_short
    elif maturity >= 5:
        return rw_long
    else:
        # Interpolate
        return rw_short + (rw_long - rw_short) * (maturity - 1) / 4


def calculate_erba_rwa(
    ead: float,
    rating: str,
    seniority: str = "senior",
    maturity: float = 5.0
) -> dict:
    """
    Calculate RWA using ERBA (External Ratings Based Approach).

    Parameters:
    -----------
    ead : float
        Exposure at Default
    rating : str
        External credit rating
    seniority : str
        "senior" or "non_senior"
    maturity : float
        Effective maturity in years

    Returns:
    --------
    dict
        Dictionary with RWA and intermediate values
    """
    risk_weight = get_erba_risk_weight(rating, seniority, maturity)
    rwa = ead * risk_weight / 100

    return {
        "approach": "ERBA",
        "ead": ead,
        "rating": rating,
        "seniority": seniority,
        "maturity": maturity,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
    }


# =============================================================================
# SEC-SA (Standardised Approach for Securitizations) - Basel III CRE40
# =============================================================================

def calculate_sec_sa_ksa(
    exposures: list[dict],
    delinquent_pct: float = 0.0
) -> float:
    """
    Calculate Ksa - the capital charge of the underlying pool under SA-CR.

    Parameters:
    -----------
    exposures : list of dict
        Underlying pool exposures with ead, exposure_class, rating, etc.
    delinquent_pct : float
        Percentage of pool that is delinquent (for W calculation)

    Returns:
    --------
    float
        Ksa as a decimal (capital / pool exposure)
    """
    if not exposures:
        return 0.08  # Default 8% if no data

    batch_result = calculate_batch_sa_rwa(exposures)
    total_ead = batch_result["total_ead"]
    total_rwa = batch_result["total_rwa"]

    if total_ead == 0:
        return 0.08

    # Ksa = RWA * 8% / EAD = (RWA/EAD) * 0.08
    ksa = (total_rwa / total_ead) * 0.08

    return ksa


def calculate_sec_sa_p(n: int, lgd: float = 0.50) -> float:
    """
    Calculate supervisory parameter p for SEC-SA.

    p = max(0.3, 0.5 * [1 - LGD])  for N >= 25
    p = max(0.3, 0.5 * [1 - LGD] + 0.5/N * LGD) for N < 25

    Parameters:
    -----------
    n : int
        Effective number of exposures in pool
    lgd : float
        Average LGD of pool (default 50%)

    Returns:
    --------
    float
        Supervisory parameter p
    """
    if n >= 25:
        p = max(0.3, 0.5 * (1 - lgd))
    else:
        p = max(0.3, 0.5 * (1 - lgd) + 0.5 / n * lgd)

    return p


def calculate_sec_sa_rw(
    ksa: float,
    attachment: float,
    detachment: float,
    n: int = 25,
    lgd: float = 0.50,
    w: float = 0.0,
    is_sts: bool = False
) -> float:
    """
    Calculate SEC-SA risk weight for a securitization tranche.

    Based on the supervisory formula approach (SFA) in CRE40.

    Parameters:
    -----------
    ksa : float
        Capital charge of underlying pool under SA (as decimal)
    attachment : float
        Attachment point A (e.g., 0.05 for 5%)
    detachment : float
        Detachment point D (e.g., 0.15 for 15%)
    n : int
        Effective number of exposures in pool
    lgd : float
        Average LGD of pool
    w : float
        Ratio of delinquent exposures in pool
    is_sts : bool
        True if Simple, Transparent, Standardised securitization (lower floor)

    Returns:
    --------
    float
        Risk weight as percentage
    """
    # Adjust Ksa for delinquencies
    ksa_adj = ksa * (1 - w)

    # Supervisory parameter
    p = calculate_sec_sa_p(n, lgd)

    # Calculate a and u parameters
    a = -(1 / (p * ksa_adj))
    u = detachment - ksa_adj
    l = max(attachment - ksa_adj, 0)

    # Supervisory formula
    if detachment <= ksa_adj:
        # Tranche is entirely within first-loss piece
        k_ssfa = detachment - attachment
    elif attachment >= ksa_adj:
        # Tranche is entirely above Ksa
        k_ssfa = ksa_adj * (math.exp(a * u) - math.exp(a * l)) / (a * (detachment - attachment))
    else:
        # Tranche spans Ksa
        k_ssfa = (ksa_adj - attachment + ksa_adj * (math.exp(a * u) - 1) / (a * (detachment - attachment)))

    # Convert to risk weight (K * 12.5 * 100)
    risk_weight = k_ssfa * 12.5 * 100

    # Apply floors
    if is_sts:
        floor = 10  # STS floor
    else:
        floor = 15  # Non-STS floor

    # Cap at 1250%
    risk_weight = min(max(risk_weight, floor), 1250)

    return risk_weight


def calculate_sec_sa_rwa(
    ead: float,
    attachment: float,
    detachment: float,
    ksa: float = None,
    underlying_exposures: list[dict] = None,
    n: int = 25,
    lgd: float = 0.50,
    w: float = 0.0,
    is_sts: bool = False
) -> dict:
    """
    Calculate RWA using SEC-SA (Standardised Approach for Securitizations).

    Parameters:
    -----------
    ead : float
        Exposure at Default of the tranche
    attachment : float
        Attachment point A (e.g., 0.05 for 5%)
    detachment : float
        Detachment point D (e.g., 0.15 for 15%)
    ksa : float, optional
        Pre-calculated Ksa (if None, calculated from underlying_exposures)
    underlying_exposures : list of dict, optional
        Underlying pool for Ksa calculation
    n : int
        Effective number of exposures in pool
    lgd : float
        Average LGD of pool
    w : float
        Ratio of delinquent exposures
    is_sts : bool
        True if STS securitization

    Returns:
    --------
    dict
        Dictionary with RWA and intermediate values
    """
    # Calculate Ksa if not provided
    if ksa is None:
        if underlying_exposures:
            ksa = calculate_sec_sa_ksa(underlying_exposures)
        else:
            ksa = 0.08  # Default assumption

    # Calculate risk weight
    risk_weight = calculate_sec_sa_rw(
        ksa=ksa,
        attachment=attachment,
        detachment=detachment,
        n=n,
        lgd=lgd,
        w=w,
        is_sts=is_sts
    )

    # Calculate RWA
    rwa = ead * risk_weight / 100

    # Tranche thickness
    thickness = detachment - attachment

    return {
        "approach": "SEC-SA",
        "ead": ead,
        "attachment": attachment,
        "detachment": detachment,
        "thickness": thickness,
        "ksa": ksa,
        "n": n,
        "lgd": lgd,
        "w": w,
        "is_sts": is_sts,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
    }


# =============================================================================
# SEC-IRBA (IRB Approach for Securitizations) - CRE40
# =============================================================================

def calculate_sec_irba_kirb(
    exposures: list[dict]
) -> float:
    """
    Calculate Kirb - the IRB capital charge of the underlying pool.

    Kirb = sum(K_i * EAD_i) / sum(EAD_i)

    Parameters:
    -----------
    exposures : list of dict
        Underlying pool with pd, lgd, ead, maturity, asset_class

    Returns:
    --------
    float
        Kirb as a decimal
    """
    if not exposures:
        return 0.08  # Default

    total_k_ead = 0
    total_ead = 0

    for exp in exposures:
        ead = exp.get("ead", 0)
        pd = exp.get("pd", 0.01)
        lgd = exp.get("lgd", 0.45)
        maturity = exp.get("maturity", 2.5)
        asset_class = exp.get("asset_class", "corporate")

        k = calculate_capital_requirement(pd, lgd, maturity, asset_class)
        total_k_ead += k * ead
        total_ead += ead

    kirb = total_k_ead / total_ead if total_ead > 0 else 0.08
    return kirb


def calculate_sec_irba_rw(
    kirb: float,
    attachment: float,
    detachment: float,
    n: int = 25,
    lgd: float = 0.50,
    is_sts: bool = False
) -> float:
    """
    Calculate SEC-IRBA risk weight using the supervisory formula.

    Same formula as SEC-SA but using Kirb instead of Ksa.
    """
    # Supervisory parameter p
    p = calculate_sec_sa_p(n, lgd)

    # Use same formula as SEC-SA with Kirb
    a = -(1 / (p * kirb)) if kirb > 0 else -100
    u = detachment - kirb
    l_val = max(attachment - kirb, 0)

    if detachment <= kirb:
        k_ssfa = detachment - attachment
    elif attachment >= kirb:
        if a * (detachment - attachment) != 0:
            k_ssfa = kirb * (math.exp(a * u) - math.exp(a * l_val)) / (a * (detachment - attachment))
        else:
            k_ssfa = kirb
    else:
        if a * (detachment - attachment) != 0:
            k_ssfa = (kirb - attachment + kirb * (math.exp(a * u) - 1) / (a * (detachment - attachment)))
        else:
            k_ssfa = kirb - attachment

    risk_weight = k_ssfa * 12.5 * 100

    # Floors
    if is_sts:
        floor = 10
    else:
        floor = 15

    return min(max(risk_weight, floor), 1250)


def calculate_sec_irba_rwa(
    ead: float,
    attachment: float,
    detachment: float,
    kirb: float = None,
    underlying_exposures: list[dict] = None,
    n: int = 25,
    lgd: float = 0.50,
    is_sts: bool = False
) -> dict:
    """
    Calculate RWA using SEC-IRBA (IRB Approach for Securitizations).

    Parameters:
    -----------
    ead : float
        Exposure at Default of the tranche
    attachment : float
        Attachment point
    detachment : float
        Detachment point
    kirb : float, optional
        Pre-calculated Kirb
    underlying_exposures : list of dict, optional
        Underlying pool for Kirb calculation
    n : int
        Effective number of exposures
    lgd : float
        Average LGD of pool
    is_sts : bool
        Whether STS securitization

    Returns:
    --------
    dict
        SEC-IRBA calculation results
    """
    # Calculate Kirb if not provided
    if kirb is None:
        if underlying_exposures:
            kirb = calculate_sec_irba_kirb(underlying_exposures)
        else:
            kirb = 0.06  # Default IRB assumption (lower than SA)

    # Calculate risk weight
    risk_weight = calculate_sec_irba_rw(kirb, attachment, detachment, n, lgd, is_sts)

    # Calculate RWA
    rwa = ead * risk_weight / 100

    return {
        "approach": "SEC-IRBA",
        "ead": ead,
        "attachment": attachment,
        "detachment": detachment,
        "thickness": detachment - attachment,
        "kirb": kirb,
        "n": n,
        "lgd": lgd,
        "is_sts": is_sts,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
    }


# =============================================================================
# IAA (Internal Assessment Approach) - CRE40.74-84
# =============================================================================

# IAA rating mapping to risk weights (for ABCP)
IAA_RISK_WEIGHTS = {
    "AAA": 15,
    "AA+": 15,
    "AA": 15,
    "AA-": 20,
    "A+": 30,
    "A": 50,
    "A-": 75,
    "BBB+": 100,
    "BBB": 150,
    "BBB-": 200,
    "below_BBB-": 1250,
}


def calculate_iaa_rwa(
    ead: float,
    internal_rating: str,
    is_liquidity_facility: bool = False,
    facility_maturity: float = 1.0
) -> dict:
    """
    Calculate RWA using IAA (Internal Assessment Approach).

    Used for unrated ABCP exposures where bank has internal assessment.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    internal_rating : str
        Bank's internal rating equivalent to external scale
    is_liquidity_facility : bool
        Whether this is a liquidity facility (eligible for lower RW)
    facility_maturity : float
        Maturity for liquidity facilities

    Returns:
    --------
    dict
        IAA calculation results
    """
    # Get base risk weight
    risk_weight = IAA_RISK_WEIGHTS.get(internal_rating, IAA_RISK_WEIGHTS["below_BBB-"])

    # Liquidity facility adjustment (if eligible)
    if is_liquidity_facility and internal_rating in ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-"]:
        # Short-term liquidity facilities may get favorable treatment
        if facility_maturity <= 1:
            risk_weight = min(risk_weight, 50)  # Cap at 50% for short-term

    # Calculate RWA
    rwa = ead * risk_weight / 100

    return {
        "approach": "IAA",
        "ead": ead,
        "internal_rating": internal_rating,
        "is_liquidity_facility": is_liquidity_facility,
        "facility_maturity": facility_maturity,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
    }


def compare_securitization_approaches(
    ead: float,
    attachment: float,
    detachment: float,
    rating: str,
    ksa: float = 0.08,
    kirb: float = 0.06,
    n: int = 25,
    seniority: str = "senior",
    maturity: float = 5.0,
    is_sts: bool = False
) -> dict:
    """
    Compare all securitization approaches: SEC-SA, SEC-IRBA, ERBA, IAA.

    Returns:
    --------
    dict
        Full comparison across approaches
    """
    # SEC-SA
    sec_sa = calculate_sec_sa_rwa(ead, attachment, detachment, ksa=ksa, n=n, is_sts=is_sts)

    # SEC-IRBA
    sec_irba = calculate_sec_irba_rwa(ead, attachment, detachment, kirb=kirb, n=n, is_sts=is_sts)

    # ERBA
    erba = calculate_erba_rwa(ead, rating, seniority, maturity)

    # IAA
    iaa = calculate_iaa_rwa(ead, rating)

    # Rank by RWA
    approaches = [
        ("SEC-SA", sec_sa["rwa"], sec_sa["risk_weight_pct"]),
        ("SEC-IRBA", sec_irba["rwa"], sec_irba["risk_weight_pct"]),
        ("ERBA", erba["rwa"], erba["risk_weight_pct"]),
        ("IAA", iaa["rwa"], iaa["risk_weight_pct"]),
    ]
    approaches_sorted = sorted(approaches, key=lambda x: x[1], reverse=True)

    return {
        "ead": ead,
        "attachment": attachment,
        "detachment": detachment,
        "rating": rating,
        "sec_sa": sec_sa,
        "sec_irba": sec_irba,
        "erba": erba,
        "iaa": iaa,
        "most_conservative": approaches_sorted[0][0],
        "least_conservative": approaches_sorted[-1][0],
        "ranking": [a[0] for a in approaches_sorted],
    }


def compare_sec_sa_vs_erba(
    ead: float,
    attachment: float,
    detachment: float,
    rating: str,
    ksa: float = 0.08,
    n: int = 25,
    seniority: str = "senior",
    maturity: float = 5.0,
    is_sts: bool = False
) -> dict:
    """
    Compare SEC-SA vs ERBA for a securitization tranche.

    Returns:
    --------
    dict
        Comparison results
    """
    # SEC-SA calculation
    sec_sa_result = calculate_sec_sa_rwa(
        ead=ead,
        attachment=attachment,
        detachment=detachment,
        ksa=ksa,
        n=n,
        is_sts=is_sts
    )

    # ERBA calculation
    erba_result = calculate_erba_rwa(ead, rating, seniority, maturity)

    # Calculate differences
    rwa_diff = sec_sa_result["rwa"] - erba_result["rwa"]

    return {
        "ead": ead,
        "attachment": attachment,
        "detachment": detachment,
        "rating": rating,
        "sec_sa": sec_sa_result,
        "erba": erba_result,
        "rwa_difference": rwa_diff,
        "more_conservative": "SEC-SA" if sec_sa_result["rwa"] > erba_result["rwa"] else "ERBA",
    }


def compare_erba_vs_irb(
    ead: float,
    rating: str,
    seniority: str = "senior",
    maturity: float = 2.5,
    lgd: float = 0.45,
    asset_class: str = "corporate",
    custom_pd: float = None
) -> dict:
    """
    Compare ERBA and IRB approaches for the same exposure.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    rating : str
        External credit rating (used for ERBA and to derive PD for IRB)
    seniority : str
        "senior" or "non_senior" (for ERBA)
    maturity : float
        Effective maturity in years
    lgd : float
        Loss Given Default (for IRB)
    asset_class : str
        Asset class (for IRB)
    custom_pd : float, optional
        Override the rating-derived PD with a custom value

    Returns:
    --------
    dict
        Comparison results with both approaches
    """
    # ERBA calculation
    erba_result = calculate_erba_rwa(ead, rating, seniority, maturity)

    # IRB calculation - use rating-mapped PD or custom PD
    pd = custom_pd if custom_pd is not None else RATING_TO_PD.get(rating, 0.01)
    irb_result = calculate_rwa(ead, pd, lgd, maturity, asset_class)
    irb_result["approach"] = "IRB-F"

    # Calculate differences
    rwa_diff = irb_result["rwa"] - erba_result["rwa"]
    rw_diff = irb_result["risk_weight_pct"] - erba_result["risk_weight_pct"]

    return {
        "ead": ead,
        "rating": rating,
        "pd_used": pd,
        "erba": erba_result,
        "irb": irb_result,
        "rwa_difference": rwa_diff,
        "rwa_difference_pct": (rwa_diff / erba_result["rwa"] * 100) if erba_result["rwa"] > 0 else 0,
        "risk_weight_difference": rw_diff,
        "more_conservative": "ERBA" if erba_result["rwa"] > irb_result["rwa"] else "IRB",
    }


def compare_batch_erba_vs_irb(exposures: list[dict]) -> dict:
    """
    Compare ERBA vs IRB for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict should have: ead, rating, and optionally seniority, maturity, lgd, asset_class, custom_pd

    Returns:
    --------
    dict
        Aggregated comparison results
    """
    results = []
    total_ead = 0
    total_erba_rwa = 0
    total_irb_rwa = 0

    for exp in exposures:
        result = compare_erba_vs_irb(
            ead=exp["ead"],
            rating=exp["rating"],
            seniority=exp.get("seniority", "senior"),
            maturity=exp.get("maturity", 2.5),
            lgd=exp.get("lgd", 0.45),
            asset_class=exp.get("asset_class", "corporate"),
            custom_pd=exp.get("custom_pd")
        )
        results.append(result)
        total_ead += result["ead"]
        total_erba_rwa += result["erba"]["rwa"]
        total_irb_rwa += result["irb"]["rwa"]

    return {
        "total_ead": total_ead,
        "total_erba_rwa": total_erba_rwa,
        "total_irb_rwa": total_irb_rwa,
        "erba_avg_risk_weight": (total_erba_rwa / total_ead * 100) if total_ead > 0 else 0,
        "irb_avg_risk_weight": (total_irb_rwa / total_ead * 100) if total_ead > 0 else 0,
        "total_rwa_difference": total_irb_rwa - total_erba_rwa,
        "more_conservative_overall": "ERBA" if total_erba_rwa > total_irb_rwa else "IRB",
        "exposures": results,
    }


def calculate_correlation(pd: float, asset_class: str = "corporate") -> float:
    """
    Calculate the asset correlation factor R based on PD and asset class.

    Basel II/III correlation formula for corporate exposures:
    R = 0.12 * (1 - exp(-50*PD)) / (1 - exp(-50)) + 0.24 * [1 - (1 - exp(-50*PD)) / (1 - exp(-50))]
    """
    if asset_class == "corporate":
        # Corporate, bank, sovereign exposures
        r_min, r_max = 0.12, 0.24
        k = 50
    elif asset_class == "retail_mortgage":
        # Residential mortgage
        return 0.15  # Fixed correlation for mortgages
    elif asset_class == "retail_revolving":
        # Qualifying revolving retail (e.g., credit cards)
        return 0.04  # Fixed correlation
    elif asset_class == "retail_other":
        # Other retail
        r_min, r_max = 0.03, 0.16
        k = 35
    else:
        raise ValueError(f"Unknown asset class: {asset_class}")

    # Basel correlation formula
    exp_factor = (1 - math.exp(-k * pd)) / (1 - math.exp(-k))
    correlation = r_min * exp_factor + r_max * (1 - exp_factor)

    return correlation


def calculate_maturity_adjustment(pd: float) -> float:
    """
    Calculate the maturity adjustment factor b(PD).

    b = (0.11852 - 0.05478 * ln(PD))^2
    """
    # Floor PD to avoid log(0)
    pd = max(pd, 0.0001)
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    return b


def calculate_capital_requirement(
    pd: float,
    lgd: float,
    maturity: float = 2.5,
    asset_class: str = "corporate"
) -> float:
    """
    Calculate the capital requirement K using the IRB formula.

    K = [LGD × N[(1-R)^(-0.5) × G(PD) + (R/(1-R))^0.5 × G(0.999)] - PD × LGD]
        × [(1-1.5×b)^(-1)] × [1 + (M-2.5) × b]

    Parameters:
    -----------
    pd : float
        Probability of Default (e.g., 0.01 for 1%)
    lgd : float
        Loss Given Default (e.g., 0.45 for 45%)
    maturity : float
        Effective maturity in years (default 2.5)
    asset_class : str
        Asset class for correlation calculation

    Returns:
    --------
    float
        Capital requirement K as a decimal
    """
    # Floor and cap PD per Basel requirements
    pd = max(pd, 0.0003)  # 3 basis points floor
    pd = min(pd, 1.0)

    # Get correlation
    r = calculate_correlation(pd, asset_class)

    # Calculate the conditional PD at 99.9% confidence
    # G(x) = inverse normal CDF
    g_pd = norm.ppf(pd)
    g_confidence = norm.ppf(0.999)

    conditional_pd = norm.cdf(
        (1 - r) ** (-0.5) * g_pd + (r / (1 - r)) ** 0.5 * g_confidence
    )

    # Expected loss
    expected_loss = pd * lgd

    # Unexpected loss (capital for UL)
    unexpected_loss = lgd * conditional_pd - expected_loss

    # Maturity adjustment (only for non-retail)
    if asset_class.startswith("retail"):
        k = unexpected_loss
    else:
        b = calculate_maturity_adjustment(pd)
        maturity_factor = (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)
        k = unexpected_loss * maturity_factor

    return max(k, 0)


def calculate_rwa(
    ead: float,
    pd: float,
    lgd: float = 0.45,
    maturity: float = 2.5,
    asset_class: str = "corporate"
) -> dict:
    """
    Calculate Risk-Weighted Assets using IRB Foundation approach.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default (e.g., 0.01 for 1%)
    lgd : float
        Loss Given Default (default 0.45 for senior unsecured under F-IRB)
    maturity : float
        Effective maturity in years (default 2.5)
    asset_class : str
        Asset class: "corporate", "retail_mortgage", "retail_revolving", "retail_other"

    Returns:
    --------
    dict
        Dictionary with RWA, capital requirement, risk weight, and intermediate values
    """
    # Calculate capital requirement
    k = calculate_capital_requirement(pd, lgd, maturity, asset_class)

    # RWA = K × 12.5 × EAD
    rwa = k * 12.5 * ead

    # Risk weight as percentage
    risk_weight = k * 12.5 * 100  # as percentage

    # Correlation used
    correlation = calculate_correlation(pd, asset_class)

    return {
        "ead": ead,
        "pd": pd,
        "lgd": lgd,
        "maturity": maturity,
        "asset_class": asset_class,
        "correlation": correlation,
        "capital_requirement_k": k,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "expected_loss": pd * lgd * ead,
    }


def calculate_batch_rwa(exposures: list[dict]) -> dict:
    """
    Calculate RWA for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict should have: ead, pd, and optionally lgd, maturity, asset_class

    Returns:
    --------
    dict
        Aggregated results and individual exposure results
    """
    results = []
    total_ead = 0
    total_rwa = 0
    total_el = 0

    for exp in exposures:
        result = calculate_rwa(
            ead=exp["ead"],
            pd=exp["pd"],
            lgd=exp.get("lgd", 0.45),
            maturity=exp.get("maturity", 2.5),
            asset_class=exp.get("asset_class", "corporate")
        )
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]
        total_el += result["expected_loss"]

    return {
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "total_expected_loss": total_el,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "exposures": results,
    }


# =============================================================================
# A-IRB (Advanced IRB) - Bank estimates PD, LGD, and EAD
# =============================================================================

# Typical A-IRB LGD ranges by collateral type
AIRB_LGD_BENCHMARKS = {
    "unsecured": (0.40, 0.50),           # 40-50% typical
    "senior_secured": (0.25, 0.35),      # 25-35% with collateral
    "real_estate": (0.15, 0.25),         # 15-25% for RE secured
    "financial_collateral": (0.05, 0.15), # 5-15% for cash/securities
    "receivables": (0.30, 0.40),         # 30-40% for receivables
    "retail_mortgage": (0.10, 0.20),     # 10-20% for residential mortgages
    "retail_revolving": (0.60, 0.80),    # 60-80% for credit cards
    "retail_other": (0.30, 0.50),        # 30-50% for other retail
}

# F-IRB prescribed LGD values for comparison
FIRB_LGD = {
    "senior_unsecured": 0.45,
    "subordinated": 0.75,
    "senior_secured_re": 0.35,           # With eligible RE collateral
    "senior_secured_other": 0.40,        # With other eligible collateral
    "senior_secured_financial": 0.00,    # Adjusted via haircuts
}


def calculate_airb_rwa(
    ead: float,
    pd: float,
    lgd: float,
    maturity: float = 2.5,
    asset_class: str = "corporate",
    lgd_downturn: float = None
) -> dict:
    """
    Calculate RWA using A-IRB (Advanced IRB) approach.

    In A-IRB, the bank estimates its own PD, LGD, and EAD (for certain exposures).
    The formula is identical to F-IRB but with bank-estimated LGD.

    Parameters:
    -----------
    ead : float
        Bank-estimated Exposure at Default
    pd : float
        Bank-estimated Probability of Default
    lgd : float
        Bank-estimated Loss Given Default (downturn LGD should be used)
    maturity : float
        Effective maturity in years
    asset_class : str
        Asset class for correlation calculation
    lgd_downturn : float, optional
        Explicit downturn LGD (if different from lgd parameter)

    Returns:
    --------
    dict
        Dictionary with RWA and intermediate values
    """
    # Use downturn LGD if provided, otherwise assume lgd is already downturn
    lgd_used = lgd_downturn if lgd_downturn is not None else lgd

    # Calculate capital requirement (same formula as F-IRB)
    k = calculate_capital_requirement(pd, lgd_used, maturity, asset_class)

    # RWA = K × 12.5 × EAD
    rwa = k * 12.5 * ead

    # Risk weight as percentage
    risk_weight = k * 12.5 * 100

    # Correlation used
    correlation = calculate_correlation(pd, asset_class)

    return {
        "approach": "A-IRB",
        "ead": ead,
        "pd": pd,
        "lgd": lgd,
        "lgd_downturn": lgd_used,
        "maturity": maturity,
        "asset_class": asset_class,
        "correlation": correlation,
        "capital_requirement_k": k,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "expected_loss": pd * lgd_used * ead,
    }


def calculate_batch_airb_rwa(exposures: list[dict]) -> dict:
    """
    Calculate A-IRB RWA for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict should have: ead, pd, lgd, and optionally maturity, asset_class, lgd_downturn

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
        result = calculate_airb_rwa(
            ead=exp["ead"],
            pd=exp["pd"],
            lgd=exp["lgd"],
            maturity=exp.get("maturity", 2.5),
            asset_class=exp.get("asset_class", "corporate"),
            lgd_downturn=exp.get("lgd_downturn")
        )
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]
        total_el += result["expected_loss"]

    return {
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "total_expected_loss": total_el,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "exposures": results,
    }


def compare_firb_vs_airb(
    ead: float,
    pd: float,
    airb_lgd: float,
    firb_lgd: float = 0.45,
    maturity: float = 2.5,
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
    firb_lgd : float
        Regulatory LGD for F-IRB (default 45%)
    maturity : float
        Effective maturity
    asset_class : str
        Asset class

    Returns:
    --------
    dict
        Comparison results
    """
    # F-IRB calculation
    firb_result = calculate_rwa(ead, pd, firb_lgd, maturity, asset_class)
    firb_result["approach"] = "F-IRB"

    # A-IRB calculation
    airb_result = calculate_airb_rwa(ead, pd, airb_lgd, maturity, asset_class)

    # Calculate differences
    rwa_diff = airb_result["rwa"] - firb_result["rwa"]
    rw_diff = airb_result["risk_weight_pct"] - firb_result["risk_weight_pct"]

    # LGD benefit
    lgd_diff = airb_lgd - firb_lgd
    lgd_benefit_pct = (lgd_diff / firb_lgd * 100) if firb_lgd > 0 else 0

    return {
        "ead": ead,
        "pd": pd,
        "firb_lgd": firb_lgd,
        "airb_lgd": airb_lgd,
        "lgd_difference": lgd_diff,
        "lgd_benefit_pct": lgd_benefit_pct,
        "firb": firb_result,
        "airb": airb_result,
        "rwa_difference": rwa_diff,
        "rwa_benefit_pct": (rwa_diff / firb_result["rwa"] * 100) if firb_result["rwa"] > 0 else 0,
        "risk_weight_difference": rw_diff,
        "more_conservative": "F-IRB" if firb_result["rwa"] > airb_result["rwa"] else "A-IRB",
    }


def compare_all_irb_approaches(
    ead: float,
    pd: float,
    airb_lgd: float,
    firb_lgd: float = 0.45,
    maturity: float = 2.5,
    asset_class: str = "corporate",
    rating: str = "BBB",
    exposure_class: str = "corporate"
) -> dict:
    """
    Compare all approaches: SA-CR, F-IRB, A-IRB for the same exposure.

    Returns:
    --------
    dict
        Full comparison across approaches
    """
    # SA-CR calculation
    sa_result = calculate_sa_rwa(ead, exposure_class, rating)

    # F-IRB calculation
    firb_result = calculate_rwa(ead, pd, firb_lgd, maturity, asset_class)
    firb_result["approach"] = "F-IRB"

    # A-IRB calculation
    airb_result = calculate_airb_rwa(ead, pd, airb_lgd, maturity, asset_class)

    # Rank by RWA (most conservative first)
    approaches = [
        ("SA-CR", sa_result["rwa"], sa_result["risk_weight_pct"]),
        ("F-IRB", firb_result["rwa"], firb_result["risk_weight_pct"]),
        ("A-IRB", airb_result["rwa"], airb_result["risk_weight_pct"]),
    ]
    approaches_sorted = sorted(approaches, key=lambda x: x[1], reverse=True)

    return {
        "ead": ead,
        "pd": pd,
        "rating": rating,
        "firb_lgd": firb_lgd,
        "airb_lgd": airb_lgd,
        "sa": sa_result,
        "firb": firb_result,
        "airb": airb_result,
        "most_conservative": approaches_sorted[0][0],
        "least_conservative": approaches_sorted[-1][0],
        "ranking": [a[0] for a in approaches_sorted],
        "rwa_range": (approaches_sorted[-1][1], approaches_sorted[0][1]),
        "rw_range": (approaches_sorted[-1][2], approaches_sorted[0][2]),
    }


# Example usage
if __name__ == "__main__":
    # ==========================================================================
    # SA-CR (Standardised Approach) Examples
    # ==========================================================================
    print("=" * 70)
    print("SA-CR (KSA) - Standardised Approach for Credit Risk")
    print("=" * 70)

    # Various exposure classes
    sa_examples = [
        {"ead": 1_000_000, "exposure_class": "sovereign", "rating": "AA"},
        {"ead": 1_000_000, "exposure_class": "bank", "rating": "A", "approach": "ECRA"},
        {"ead": 1_000_000, "exposure_class": "corporate", "rating": "BBB"},
        {"ead": 1_000_000, "exposure_class": "corporate", "rating": "unrated", "is_sme": True},
        {"ead": 1_000_000, "exposure_class": "retail", "retail_type": "regulatory_retail"},
        {"ead": 1_000_000, "exposure_class": "residential_re", "ltv": 0.75},
        {"ead": 1_000_000, "exposure_class": "commercial_re", "ltv": 0.65},
    ]

    print(f"\n  {'Exposure Class':<18} {'Rating':<10} {'RW':>8} {'RWA':>15}")
    print(f"  {'-'*18} {'-'*10} {'-'*8} {'-'*15}")

    for exp in sa_examples:
        result = calculate_sa_rwa(**exp)
        label = exp["exposure_class"]
        if exp.get("is_sme"):
            label += " (SME)"
        if exp.get("ltv"):
            label += f" LTV={exp['ltv']*100:.0f}%"
        print(f"  {label:<18} {result['rating']:<10} {result['risk_weight_pct']:>7.0f}% ${result['rwa']:>13,.0f}")

    # ==========================================================================
    # SA vs IRB Comparison
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SA-CR vs IRB-F Comparison")
    print("=" * 70)

    comparison = compare_sa_vs_irb(
        ead=1_000_000,
        exposure_class="corporate",
        rating="BBB",
        lgd=0.45,
        maturity=2.5
    )

    print(f"\n  Corporate Exposure: ${comparison['ead']:,.0f}, Rating: {comparison['rating']}")
    print(f"  IRB PD (from rating): {comparison['pd_used']*100:.2f}%")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*12} {'-'*15}")
    print(f"  {'SA-CR':<10} {comparison['sa']['risk_weight_pct']:>11.0f}% ${comparison['sa']['rwa']:>13,.0f}")
    print(f"  {'IRB-F':<10} {comparison['irb']['risk_weight_pct']:>11.1f}% ${comparison['irb']['rwa']:>13,.0f}")
    print(f"\n  More conservative: {comparison['more_conservative']} (diff: ${abs(comparison['rwa_difference']):,.0f})")

    # ==========================================================================
    # Full Three-Way Comparison (SA vs IRB vs ERBA)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Full Comparison: SA-CR vs IRB-F vs ERBA")
    print("=" * 70)

    full_comp = compare_all_approaches(
        ead=1_000_000,
        rating="BBB",
        exposure_class="corporate",
        seniority="senior",
        maturity=3.0,
        lgd=0.45
    )

    print(f"\n  Exposure: ${full_comp['ead']:,.0f}, Rating: {full_comp['rating']}, PD: {full_comp['pd_used']*100:.2f}%")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15} {'Capital K':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*15} {'-'*12}")
    print(f"  {'SA-CR':<10} {full_comp['sa']['risk_weight_pct']:>11.0f}% ${full_comp['sa']['rwa']:>13,.0f} {full_comp['sa']['capital_requirement_k']*100:>11.2f}%")
    print(f"  {'IRB-F':<10} {full_comp['irb']['risk_weight_pct']:>11.1f}% ${full_comp['irb']['rwa']:>13,.0f} {full_comp['irb']['capital_requirement_k']*100:>11.2f}%")
    print(f"  {'ERBA':<10} {full_comp['erba']['risk_weight_pct']:>11.1f}% ${full_comp['erba']['rwa']:>13,.0f} {full_comp['erba']['capital_requirement_k']*100:>11.2f}%")
    print(f"\n  Ranking (most to least conservative): {' > '.join(full_comp['ranking'])}")

    # ==========================================================================
    # Batch Comparison Across Ratings
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Comparison Across Rating Spectrum")
    print("=" * 70)

    ratings_to_compare = ["AAA", "A", "BBB", "BB", "B"]
    print(f"\n  {'Rating':<8} {'SA-CR':>10} {'IRB-F':>10} {'ERBA':>10} {'Best':>10}")
    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for rating in ratings_to_compare:
        comp = compare_all_approaches(
            ead=1_000_000,
            rating=rating,
            exposure_class="corporate",
            seniority="senior",
            maturity=2.5
        )
        print(f"  {rating:<8} {comp['sa']['risk_weight_pct']:>9.0f}% {comp['irb']['risk_weight_pct']:>9.1f}% {comp['erba']['risk_weight_pct']:>9.1f}% {comp['least_conservative']:>10}")

    # ==========================================================================
    # A-IRB vs F-IRB Comparison
    # ==========================================================================
    print("\n" + "=" * 70)
    print("A-IRB vs F-IRB Comparison (LGD Impact)")
    print("=" * 70)

    print("\n  Same exposure with different LGD estimates:")
    print(f"  PD = 2%, Maturity = 2.5 years, EAD = $1,000,000")

    lgd_scenarios = [
        ("F-IRB (regulatory)", 0.45),
        ("A-IRB (unsecured)", 0.40),
        ("A-IRB (secured RE)", 0.25),
        ("A-IRB (financial coll.)", 0.10),
    ]

    print(f"\n  {'Scenario':<25} {'LGD':>8} {'RW':>10} {'RWA':>15} {'vs F-IRB':>12}")
    print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*15} {'-'*12}")

    firb_base = calculate_rwa(1_000_000, 0.02, 0.45, 2.5, "corporate")

    for label, lgd in lgd_scenarios:
        if lgd == 0.45:
            result = firb_base
            diff = 0
        else:
            result = calculate_airb_rwa(1_000_000, 0.02, lgd, 2.5, "corporate")
            diff = result["rwa"] - firb_base["rwa"]
        diff_pct = (diff / firb_base["rwa"] * 100) if firb_base["rwa"] > 0 else 0
        print(f"  {label:<25} {lgd*100:>7.0f}% {result['risk_weight_pct']:>9.1f}% ${result['rwa']:>13,.0f} {diff_pct:>+11.1f}%")

    # F-IRB vs A-IRB detailed comparison
    print("\n  Detailed F-IRB vs A-IRB comparison (secured corporate loan):")
    irb_comp = compare_firb_vs_airb(
        ead=1_000_000,
        pd=0.015,  # 1.5% PD
        airb_lgd=0.30,  # Bank estimate with collateral
        firb_lgd=0.45,  # Regulatory
        maturity=3.0
    )

    print(f"\n  PD: {irb_comp['pd']*100:.2f}%, F-IRB LGD: {irb_comp['firb_lgd']*100:.0f}%, A-IRB LGD: {irb_comp['airb_lgd']*100:.0f}%")
    print(f"  LGD reduction: {abs(irb_comp['lgd_benefit_pct']):.1f}%")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15} {'EL':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*15} {'-'*12}")
    print(f"  {'F-IRB':<10} {irb_comp['firb']['risk_weight_pct']:>11.1f}% ${irb_comp['firb']['rwa']:>13,.0f} ${irb_comp['firb']['expected_loss']:>10,.0f}")
    print(f"  {'A-IRB':<10} {irb_comp['airb']['risk_weight_pct']:>11.1f}% ${irb_comp['airb']['rwa']:>13,.0f} ${irb_comp['airb']['expected_loss']:>10,.0f}")
    print(f"\n  RWA benefit from A-IRB: ${abs(irb_comp['rwa_difference']):,.0f} ({irb_comp['rwa_benefit_pct']:.1f}%)")

    # ==========================================================================
    # Full SA vs F-IRB vs A-IRB Comparison
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Full Comparison: SA-CR vs F-IRB vs A-IRB")
    print("=" * 70)

    full_irb = compare_all_irb_approaches(
        ead=1_000_000,
        pd=0.02,
        airb_lgd=0.30,
        firb_lgd=0.45,
        maturity=2.5,
        rating="BBB"
    )

    print(f"\n  Exposure: ${full_irb['ead']:,.0f}, Rating: {full_irb['rating']}, PD: {full_irb['pd']*100:.1f}%")
    print(f"  F-IRB LGD: {full_irb['firb_lgd']*100:.0f}%, A-IRB LGD: {full_irb['airb_lgd']*100:.0f}%")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*12} {'-'*15}")
    print(f"  {'SA-CR':<10} {full_irb['sa']['risk_weight_pct']:>11.0f}% ${full_irb['sa']['rwa']:>13,.0f}")
    print(f"  {'F-IRB':<10} {full_irb['firb']['risk_weight_pct']:>11.1f}% ${full_irb['firb']['rwa']:>13,.0f}")
    print(f"  {'A-IRB':<10} {full_irb['airb']['risk_weight_pct']:>11.1f}% ${full_irb['airb']['rwa']:>13,.0f}")
    print(f"\n  Ranking: {' > '.join(full_irb['ranking'])}")
    print(f"  RWA range: ${full_irb['rwa_range'][0]:,.0f} - ${full_irb['rwa_range'][1]:,.0f}")

    # ==========================================================================
    # SEC-SA (Securitization Standardised Approach)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("SEC-SA - Standardised Approach for Securitizations")
    print("=" * 70)

    # Example tranches of a securitization
    tranches = [
        {"name": "Senior AAA", "attachment": 0.15, "detachment": 1.00, "rating": "AAA"},
        {"name": "Mezzanine A", "attachment": 0.08, "detachment": 0.15, "rating": "A"},
        {"name": "Mezzanine BBB", "attachment": 0.04, "detachment": 0.08, "rating": "BBB"},
        {"name": "Junior BB", "attachment": 0.01, "detachment": 0.04, "rating": "BB"},
        {"name": "First Loss", "attachment": 0.00, "detachment": 0.01, "rating": "below_CCC-"},
    ]

    print(f"\n  Pool: Ksa = 8%, N = 50 exposures, LGD = 50%")
    print(f"\n  {'Tranche':<15} {'A-D':>10} {'Thick':>8} {'SEC-SA RW':>12} {'ERBA RW':>10}")
    print(f"  {'-'*15} {'-'*10} {'-'*8} {'-'*12} {'-'*10}")

    for t in tranches:
        sec_sa = calculate_sec_sa_rwa(
            ead=1_000_000,
            attachment=t["attachment"],
            detachment=t["detachment"],
            ksa=0.08,
            n=50,
            lgd=0.50
        )
        erba = calculate_erba_rwa(1_000_000, t["rating"], "senior", 5.0)

        a_d = f"{t['attachment']*100:.0f}%-{t['detachment']*100:.0f}%"
        thick = f"{(t['detachment']-t['attachment'])*100:.0f}%"
        print(f"  {t['name']:<15} {a_d:>10} {thick:>8} {sec_sa['risk_weight_pct']:>11.1f}% {erba['risk_weight_pct']:>9.1f}%")

    # SEC-SA vs ERBA comparison
    print("\n  SEC-SA vs ERBA comparison for mezzanine tranche:")
    sec_comp = compare_sec_sa_vs_erba(
        ead=1_000_000,
        attachment=0.05,
        detachment=0.10,
        rating="BBB",
        ksa=0.08,
        n=50,
        seniority="senior",
        maturity=5.0
    )

    print(f"\n  Tranche: {sec_comp['attachment']*100:.0f}%-{sec_comp['detachment']*100:.0f}%, Rating: {sec_comp['rating']}")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*12} {'-'*15}")
    print(f"  {'SEC-SA':<10} {sec_comp['sec_sa']['risk_weight_pct']:>11.1f}% ${sec_comp['sec_sa']['rwa']:>13,.0f}")
    print(f"  {'ERBA':<10} {sec_comp['erba']['risk_weight_pct']:>11.1f}% ${sec_comp['erba']['rwa']:>13,.0f}")
    print(f"\n  More conservative: {sec_comp['more_conservative']}")

    # ==========================================================================
    # Full Securitization Comparison (SEC-SA vs SEC-IRBA vs ERBA vs IAA)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Full Securitization Comparison: All Four Approaches")
    print("=" * 70)

    print(f"\n  Mezzanine tranche: 5%-10%, Rating: BBB")
    print(f"  Ksa = 8%, Kirb = 6%, N = 50")

    full_sec = compare_securitization_approaches(
        ead=1_000_000,
        attachment=0.05,
        detachment=0.10,
        rating="BBB",
        ksa=0.08,
        kirb=0.06,
        n=50,
        seniority="senior",
        maturity=5.0
    )

    print(f"\n  {'Approach':<12} {'Risk Weight':>12} {'RWA':>15}")
    print(f"  {'-'*12} {'-'*12} {'-'*15}")
    print(f"  {'SEC-SA':<12} {full_sec['sec_sa']['risk_weight_pct']:>11.1f}% ${full_sec['sec_sa']['rwa']:>13,.0f}")
    print(f"  {'SEC-IRBA':<12} {full_sec['sec_irba']['risk_weight_pct']:>11.1f}% ${full_sec['sec_irba']['rwa']:>13,.0f}")
    print(f"  {'ERBA':<12} {full_sec['erba']['risk_weight_pct']:>11.1f}% ${full_sec['erba']['rwa']:>13,.0f}")
    print(f"  {'IAA':<12} {full_sec['iaa']['risk_weight_pct']:>11.1f}% ${full_sec['iaa']['rwa']:>13,.0f}")
    print(f"\n  Ranking: {' > '.join(full_sec['ranking'])}")
    print(f"  Most conservative:  {full_sec['most_conservative']}")
    print(f"  Least conservative: {full_sec['least_conservative']}")

    # Compare across tranche seniority
    print("\n  Comparison by tranche (Kirb=6% vs Ksa=8%):")
    print(f"\n  {'Tranche':<15} {'SEC-SA':>10} {'SEC-IRBA':>10} {'ERBA':>10} {'Best':>12}")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*12}")

    tranche_compare = [
        {"name": "Senior (15-100%)", "a": 0.15, "d": 1.00, "rating": "AAA"},
        {"name": "Mezz A (8-15%)", "a": 0.08, "d": 0.15, "rating": "A"},
        {"name": "Mezz BBB (4-8%)", "a": 0.04, "d": 0.08, "rating": "BBB"},
        {"name": "Junior (1-4%)", "a": 0.01, "d": 0.04, "rating": "BB"},
    ]

    for t in tranche_compare:
        comp = compare_securitization_approaches(
            ead=1_000_000, attachment=t["a"], detachment=t["d"],
            rating=t["rating"], ksa=0.08, kirb=0.06, n=50
        )
        print(f"  {t['name']:<15} {comp['sec_sa']['risk_weight_pct']:>9.1f}% {comp['sec_irba']['risk_weight_pct']:>9.1f}% {comp['erba']['risk_weight_pct']:>9.1f}% {comp['least_conservative']:>12}")

    # ==========================================================================
    # PD-to-Rating Mapping Examples
    # ==========================================================================
    print("\n" + "=" * 70)
    print("PD-to-Rating Mapping - Use PD/LGD Data with Any Methodology")
    print("=" * 70)

    # Demonstrate PD to Rating mapping
    print("\n  PD -> Rating Mapping:")
    print(f"\n  {'PD':>8} {'Derived Rating':<15} {'Rating PD':>10}")
    print(f"  {'-'*8} {'-'*15} {'-'*10}")

    test_pds = [0.0001, 0.0005, 0.002, 0.005, 0.015, 0.03, 0.08, 0.15, 0.25]
    for test_pd in test_pds:
        rating = get_rating_from_pd(test_pd)
        rating_pd = RATING_TO_PD[rating]
        print(f"  {test_pd*100:>7.2f}% {rating:<15} {rating_pd*100:>9.2f}%")

    # ==========================================================================
    # Unified PD-Based Calculation (All Approaches)
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Unified RWA Calculation from PD/LGD")
    print("=" * 70)

    print("\n  Example: Corporate loan with PD=2.5%, LGD=40%")
    print("  Calculating RWA across all approaches:")

    pd_example = 0.025
    lgd_example = 0.40

    pd_comp = compare_all_approaches_from_pd(
        ead=1_000_000,
        pd=pd_example,
        lgd=lgd_example,
        maturity=3.0,
        exposure_class="corporate",
        seniority="senior"
    )

    print(f"\n  PD: {pd_example*100:.1f}%, LGD: {lgd_example*100:.0f}%")
    print(f"  Derived Rating: {pd_comp['derived_rating']}")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*12} {'-'*15}")
    print(f"  {'SA-CR':<10} {pd_comp['sa']['risk_weight_pct']:>11.0f}% ${pd_comp['sa']['rwa']:>13,.0f}")
    print(f"  {'IRB-F':<10} {pd_comp['irb_f']['risk_weight_pct']:>11.1f}% ${pd_comp['irb_f']['rwa']:>13,.0f}")
    print(f"  {'A-IRB':<10} {pd_comp['airb']['risk_weight_pct']:>11.1f}% ${pd_comp['airb']['rwa']:>13,.0f}")
    print(f"  {'ERBA':<10} {pd_comp['erba']['risk_weight_pct']:>11.1f}% ${pd_comp['erba']['rwa']:>13,.0f}")
    print(f"\n  Ranking: {' > '.join(pd_comp['ranking'])}")

    # ==========================================================================
    # Batch Processing with PD/LGD Data
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Batch RWA Calculation from PD/LGD Portfolio")
    print("=" * 70)

    # Sample portfolio with only PD/LGD data
    portfolio = [
        {"ead": 500_000, "pd": 0.005, "lgd": 0.45, "maturity": 2.0},   # Investment grade
        {"ead": 750_000, "pd": 0.015, "lgd": 0.40, "maturity": 3.0},   # BBB-ish
        {"ead": 300_000, "pd": 0.035, "lgd": 0.50, "maturity": 2.5},   # BB-ish
        {"ead": 200_000, "pd": 0.08, "lgd": 0.55, "maturity": 1.5},    # B-ish
        {"ead": 250_000, "pd": 0.02, "lgd": 0.35, "maturity": 4.0},    # Secured
    ]

    print("\n  Portfolio (PD/LGD based):")
    print(f"\n  {'EAD':>12} {'PD':>8} {'LGD':>8} {'Mat':>6} {'Derived':>10}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*6} {'-'*10}")
    for exp in portfolio:
        rating = get_rating_from_pd(exp["pd"])
        print(f"  ${exp['ead']:>11,.0f} {exp['pd']*100:>7.2f}% {exp['lgd']*100:>7.0f}% {exp['maturity']:>5.1f}y {rating:>10}")

    # Calculate across different approaches
    print("\n  RWA by Approach:")
    print(f"\n  {'Approach':<10} {'Total RWA':>15} {'Avg RW':>10}")
    print(f"  {'-'*10} {'-'*15} {'-'*10}")

    for approach in ["IRB-F", "A-IRB", "SA-CR", "ERBA"]:
        batch = calculate_batch_rwa_from_pd(portfolio, approach)
        print(f"  {approach:<10} ${batch['total_rwa']:>14,.0f} {batch['average_risk_weight_pct']:>9.1f}%")

    # ==========================================================================
    # Securitization with PD/LGD Pool Data
    # ==========================================================================
    print("\n" + "=" * 70)
    print("Securitization RWA from Pool PD/LGD Data")
    print("=" * 70)

    # Underlying pool with PD/LGD data (no ratings)
    underlying_pool = [
        {"ead": 100_000, "pd": 0.008, "lgd": 0.45},
        {"ead": 150_000, "pd": 0.012, "lgd": 0.45},
        {"ead": 80_000, "pd": 0.020, "lgd": 0.50},
        {"ead": 120_000, "pd": 0.015, "lgd": 0.40},
        {"ead": 200_000, "pd": 0.005, "lgd": 0.45},
        {"ead": 90_000, "pd": 0.025, "lgd": 0.55},
        {"ead": 110_000, "pd": 0.010, "lgd": 0.45},
        {"ead": 75_000, "pd": 0.030, "lgd": 0.50},
    ]

    print(f"\n  Underlying pool: {len(underlying_pool)} exposures")
    total_pool = sum(e["ead"] for e in underlying_pool)
    avg_pd = sum(e["pd"] * e["ead"] for e in underlying_pool) / total_pool
    print(f"  Total pool EAD: ${total_pool:,.0f}")
    print(f"  Weighted average PD: {avg_pd*100:.2f}%")

    # Calculate SEC-IRBA for mezzanine tranche
    print("\n  SEC-IRBA for mezzanine tranche (5%-12%):")
    sec_irba_result = calculate_securitization_rwa_from_pd(
        ead=70_000,  # 7% of pool
        attachment=0.05,
        detachment=0.12,
        pool_exposures=underlying_pool,
        approach="SEC-IRBA",
        is_sts=False
    )

    print(f"\n  Kirb (calculated): {sec_irba_result['kirb']*100:.2f}%")
    print(f"  Effective N: {sec_irba_result['pool_statistics']['effective_n']}")
    print(f"  Risk Weight: {sec_irba_result['risk_weight_pct']:.1f}%")
    print(f"  RWA: ${sec_irba_result['rwa']:,.0f}")

    # Compare SEC-SA vs SEC-IRBA
    print("\n  SEC-SA vs SEC-IRBA comparison:")
    sec_sa_result = calculate_securitization_rwa_from_pd(
        ead=70_000,
        attachment=0.05,
        detachment=0.12,
        pool_exposures=underlying_pool,
        approach="SEC-SA",
        is_sts=False
    )

    print(f"\n  {'Approach':<12} {'K (pool)':>10} {'Tranche RW':>12} {'RWA':>12}")
    print(f"  {'-'*12} {'-'*10} {'-'*12} {'-'*12}")
    print(f"  {'SEC-IRBA':<12} {sec_irba_result['kirb']*100:>9.2f}% {sec_irba_result['risk_weight_pct']:>11.1f}% ${sec_irba_result['rwa']:>10,.0f}")
    print(f"  {'SEC-SA':<12} {sec_sa_result['ksa']*100:>9.2f}% {sec_sa_result['risk_weight_pct']:>11.1f}% ${sec_sa_result['rwa']:>10,.0f}")
