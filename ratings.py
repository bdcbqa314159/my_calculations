"""
Ratings and PD Mapping Module

Single source of truth for:
- Rating to PD mapping
- PD to rating conversion
- Rating normalization (AA+, BBB- -> AA, BBB)
- Common resolve functions for rating/PD inputs

Used by: irc, var, frtb_ima, cds_rwa, repo_rwa, trs_rwa, loan_rwa, etc.
"""

import math
from typing import Optional


# =============================================================================
# Rating to PD Mapping
# =============================================================================

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
    "CC": 0.4000,
    "C": 0.4500,
    "D": 1.0000,
    "below_CCC-": 0.5000,
}

# Sorted list for reverse lookup (PD -> Rating)
_PD_RATING_SORTED = sorted(RATING_TO_PD.items(), key=lambda x: x[1])


# =============================================================================
# Rating Normalization
# =============================================================================

# Map notched ratings to base ratings (for transition matrices, etc.)
_RATING_NORMALIZATION = {
    "AA+": "AA", "AA-": "AA",
    "A+": "A", "A-": "A",
    "BBB+": "BBB", "BBB-": "BBB",
    "BB+": "BB", "BB-": "BB",
    "B+": "B", "B-": "B",
    "CCC+": "CCC", "CCC-": "CCC",
    "below_CCC-": "CCC",
}


def normalize_rating(rating: str) -> str:
    """
    Normalize a notched rating to its base rating.

    Examples:
        "AA+" -> "AA"
        "BBB-" -> "BBB"
        "A" -> "A" (unchanged)

    Parameters
    ----------
    rating : str
        Credit rating (e.g., "AA+", "BBB-", "A")

    Returns
    -------
    str
        Base rating without notches
    """
    if not rating:
        return "BBB"
    rating_upper = rating.upper().strip()
    return _RATING_NORMALIZATION.get(rating_upper, rating_upper)


# =============================================================================
# PD <-> Rating Conversion
# =============================================================================

def get_rating_from_pd(pd: float) -> str:
    """
    Get the closest external rating for a given PD value.

    Uses the RATING_TO_PD mapping to find the rating whose PD is closest
    to the provided value. This enables using PD-based data with rating-based
    methodologies (SA-CR, ERBA, IAA).

    Parameters
    ----------
    pd : float
        Probability of Default (e.g., 0.02 for 2%)

    Returns
    -------
    str
        The closest external rating (e.g., "BB" for PD around 2%)

    Examples
    --------
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
    if pd >= 1.0:
        return "D"

    # Find the closest rating by PD
    best_rating = "BBB"  # Default
    min_distance = float("inf")

    for rating, rating_pd in _PD_RATING_SORTED:
        distance = abs(pd - rating_pd)
        if distance < min_distance:
            min_distance = distance
            best_rating = rating

    return best_rating


def get_pd_range_for_rating(rating: str) -> tuple:
    """
    Get the PD range that maps to a given rating.

    Returns the midpoint boundaries between adjacent ratings.

    Parameters
    ----------
    rating : str
        External credit rating

    Returns
    -------
    tuple
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
# Resolve Functions (Rating/PD from various inputs)
# =============================================================================

def resolve_pd(
    pd: Optional[float] = None,
    rating: Optional[str] = None,
    default_pd: float = 0.004,
) -> float:
    """
    Resolve PD from explicit value or rating lookup.

    Parameters
    ----------
    pd : float, optional
        Explicit probability of default
    rating : str, optional
        Credit rating to convert to PD
    default_pd : float
        Default PD if neither provided (default: 0.004 ~ BBB)

    Returns
    -------
    float
        Resolved probability of default

    Examples
    --------
    >>> resolve_pd(pd=0.02)
    0.02
    >>> resolve_pd(rating="BB")
    0.02
    >>> resolve_pd()
    0.004
    """
    if pd is not None:
        return pd
    if rating is not None and rating.upper() not in ("UNRATED", "NR", ""):
        return RATING_TO_PD.get(rating, RATING_TO_PD.get(normalize_rating(rating), default_pd))
    return default_pd


def resolve_rating(
    rating: Optional[str] = None,
    pd: Optional[float] = None,
    default_rating: str = "BBB",
) -> str:
    """
    Resolve rating from explicit value or PD-based estimation.

    Parameters
    ----------
    rating : str, optional
        Explicit credit rating
    pd : float, optional
        PD to convert to rating
    default_rating : str
        Default rating if neither provided (default: "BBB")

    Returns
    -------
    str
        Resolved credit rating

    Examples
    --------
    >>> resolve_rating(rating="A")
    'A'
    >>> resolve_rating(pd=0.02)
    'BB'
    >>> resolve_rating()
    'BBB'
    """
    if rating is not None and rating.upper() not in ("UNRATED", "NR", ""):
        return rating
    if pd is not None:
        return get_rating_from_pd(pd)
    return default_rating


def resolve_rating_log_scale(
    rating: Optional[str] = None,
    pd: Optional[float] = None,
    default_rating: str = "unrated",
) -> str:
    """
    Resolve rating using log-scale distance for better PD matching.

    Uses logarithmic distance for more accurate PD-to-rating mapping,
    especially for low PD values where linear distance is skewed.

    Parameters
    ----------
    rating : str, optional
        Explicit credit rating
    pd : float, optional
        PD to convert to rating
    default_rating : str
        Default rating if neither provided

    Returns
    -------
    str
        Resolved credit rating
    """
    if rating is not None:
        return rating
    if pd is not None:
        best, best_dist = default_rating, float("inf")
        for r, rpd in RATING_TO_PD.items():
            d = abs(math.log(max(pd, 1e-8)) - math.log(max(rpd, 1e-8)))
            if d < best_dist:
                best, best_dist = r, d
        return best
    return default_rating


# =============================================================================
# Investment Grade Classification
# =============================================================================

IG_RATINGS = frozenset({
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"
})

HY_RATINGS = frozenset({
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"
})


def is_investment_grade(rating: str) -> bool:
    """Check if a rating is investment grade (BBB- or better)."""
    return rating in IG_RATINGS


def is_high_yield(rating: str) -> bool:
    """Check if a rating is high yield (BB+ or worse)."""
    return rating in HY_RATINGS or rating.startswith("below")


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Ratings Module - Rating/PD Mapping")
    print("=" * 60)

    print("\nRATING_TO_PD Mapping:")
    print(f"  {'Rating':<12} {'PD':>10} {'IG/HY':>8}")
    print(f"  {'-'*32}")
    for rating, pd in _PD_RATING_SORTED:
        grade = "IG" if is_investment_grade(rating) else "HY"
        print(f"  {rating:<12} {pd:>9.4%} {grade:>8}")

    print("\n" + "-" * 60)
    print("resolve_pd() Examples:")
    print(f"  resolve_pd(pd=0.02)           = {resolve_pd(pd=0.02):.4f}")
    print(f"  resolve_pd(rating='BB')       = {resolve_pd(rating='BB'):.4f}")
    print(f"  resolve_pd(rating='BBB-')     = {resolve_pd(rating='BBB-'):.4f}")
    print(f"  resolve_pd()                  = {resolve_pd():.4f}")

    print("\n" + "-" * 60)
    print("resolve_rating() Examples:")
    print(f"  resolve_rating(rating='A')    = {resolve_rating(rating='A')}")
    print(f"  resolve_rating(pd=0.02)       = {resolve_rating(pd=0.02)}")
    print(f"  resolve_rating(pd=0.005)      = {resolve_rating(pd=0.005)}")
    print(f"  resolve_rating()              = {resolve_rating()}")

    print("\n" + "-" * 60)
    print("normalize_rating() Examples:")
    print(f"  normalize_rating('AA+')       = {normalize_rating('AA+')}")
    print(f"  normalize_rating('BBB-')      = {normalize_rating('BBB-')}")
    print(f"  normalize_rating('A')         = {normalize_rating('A')}")

    print("\n" + "-" * 60)
    print("get_pd_range_for_rating() Examples:")
    for r in ["AAA", "BBB", "BB", "CCC"]:
        low, high = get_pd_range_for_rating(r)
        print(f"  {r:<6} -> ({low:.6f}, {high:.6f})")

    print("\n" + "=" * 60)
