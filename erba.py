"""
CRR2 ERBA (External Ratings-Based Approach) for Securitisations
================================================================

This module implements the Basel III / CRR2 ERBA methodology for calculating
Risk-Weighted Assets (RWA) on securitisation exposures per CRR2 Articles 263-264.

Key Features:
- CQS (Credit Quality Step) 1-17 mapping
- Maturity adjustment: a + b × M_T
- Thickness adjustment: T^(-c) for non-senior tranches
- STS (Simple, Transparent, Standardised) support with reduced floors

Required Inputs:
    - CQS (Credit Quality Step) or PD (Probability of Default)
    - Seniority: "senior" or "non-senior"
    - M_T: Tranche maturity in years (floored at 1, capped at 5)
    - T: Tranche thickness = Detachment - Attachment (for non-senior only)
    - is_STS: Whether the securitisation qualifies as STS

Formulas:
    Senior:     RW = RW_base × (a + b × M_T)
    Non-Senior: RW = RW_base × (a + b × M_T) × T^(-c)

Reference: CRR2 Articles 263-264
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from ratings import RATING_TO_PD, get_rating_from_pd


# =============================================================================
# CONSTANTS AND LOOKUP TABLES
# =============================================================================

# RW_base table: CQS -> (Senior RW, Non-Senior RW)
RW_BASE_TABLE = {
    1:  (0.15, 0.15),
    2:  (0.15, 0.25),
    3:  (0.25, 0.40),
    4:  (0.30, 0.50),
    5:  (0.40, 0.65),
    6:  (0.45, 0.85),
    7:  (0.55, 1.05),
    8:  (0.75, 1.35),
    9:  (0.95, 1.70),
    10: (1.20, 2.25),
    11: (1.55, 2.80),
    12: (1.95, 3.40),
    13: (2.50, 4.15),
    14: (4.00, 5.00),
    15: (5.00, 6.25),
    16: (6.25, 7.50),
    17: (7.50, 8.25),
}

# Coefficients table: CQS -> (a, b, c)
# a, b: maturity adjustment coefficients (all tranches)
# c: thickness adjustment exponent (non-senior only)
COEFFICIENTS_TABLE = {
    1:  (0.01, 0.20, 0.40),
    2:  (0.01, 0.20, 0.40),
    3:  (0.03, 0.22, 0.40),
    4:  (0.05, 0.25, 0.35),
    5:  (0.05, 0.25, 0.35),
    6:  (0.05, 0.25, 0.35),
    7:  (0.09, 0.30, 0.30),
    8:  (0.09, 0.30, 0.30),
    9:  (0.09, 0.30, 0.30),
    10: (0.09, 0.30, 0.30),
    11: (0.09, 0.30, 0.30),
    12: (0.10, 0.35, 0.25),
    13: (0.10, 0.35, 0.25),
    14: (0.10, 0.35, 0.25),
    15: (0.10, 0.35, 0.25),
    16: (0.10, 0.35, 0.25),
    17: (0.10, 0.35, 0.25),
}

# PD thresholds for CQS mapping (upper bounds)
PD_TO_CQS_THRESHOLDS = [
    (0.0001, 1),   # <= 0.01%  -> CQS 1 (AAA)
    (0.0005, 2),   # <= 0.05%  -> CQS 2 (AA)
    (0.0010, 3),   # <= 0.10%  -> CQS 3 (A)
    (0.0020, 4),   # <= 0.20%  -> CQS 4 (BBB+)
    (0.0030, 5),   # <= 0.30%  -> CQS 5 (BBB)
    (0.0050, 6),   # <= 0.50%  -> CQS 6 (BBB-)
    (0.0080, 7),   # <= 0.80%  -> CQS 7 (BB+)
    (0.0130, 8),   # <= 1.30%  -> CQS 8 (BB)
    (0.0200, 9),   # <= 2.00%  -> CQS 9 (BB-)
    (0.0350, 10),  # <= 3.50%  -> CQS 10 (B+)
    (0.0550, 11),  # <= 5.50%  -> CQS 11 (B)
    (0.0800, 12),  # <= 8.00%  -> CQS 12 (B-)
    (0.1500, 13),  # <= 15.00% -> CQS 13 (CCC+)
    (0.2500, 14),  # <= 25.00% -> CQS 14 (CCC)
    (0.3500, 15),  # <= 35.00% -> CQS 15 (CCC-)
    (0.5000, 16),  # <= 50.00% -> CQS 16 (CC)
    (1.0000, 17),  # > 50.00%  -> CQS 17 (C/D)
]

# Rating equivalents for display
CQS_TO_RATING = {
    1: "AAA", 2: "AA", 3: "A", 4: "BBB+", 5: "BBB", 6: "BBB-",
    7: "BB+", 8: "BB", 9: "BB-", 10: "B+", 11: "B", 12: "B-",
    13: "CCC+", 14: "CCC", 15: "CCC-", 16: "CC", 17: "C/D"
}

RATING_TO_CQS = {v: k for k, v in CQS_TO_RATING.items()}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ERBAInputs:
    """Input parameters for ERBA calculation."""
    cqs: int                          # Credit Quality Step (1-17)
    seniority: str                    # "senior" or "non-senior"
    M_T: float                        # Tranche maturity in years
    T: Optional[float] = None         # Tranche thickness (non-senior only)
    is_STS: bool = False              # STS qualification
    exposure: Optional[float] = None  # Exposure amount for RWA calculation


@dataclass
class ERBAResult:
    """Output of ERBA calculation with intermediate steps."""
    # Inputs
    cqs: int
    rating: str
    seniority: str
    M_T: float
    T: Optional[float]
    is_STS: bool

    # Lookup values
    RW_base: float
    a: float
    b: float
    c: Optional[float]

    # Intermediate calculations
    maturity_factor: float
    thickness_factor: Optional[float]
    RW_unadjusted: float

    # Final result
    floor: float
    cap: float
    RW_final: float

    # RWA (if exposure provided)
    exposure: Optional[float] = None
    RWA: Optional[float] = None

    def __str__(self) -> str:
        """Pretty print the result."""
        lines = [
            "=" * 60,
            "ERBA CALCULATION RESULT",
            "=" * 60,
            "",
            "INPUTS:",
            f"  CQS:        {self.cqs} ({self.rating})",
            f"  Seniority:  {self.seniority}",
            f"  M_T:        {self.M_T} years",
            f"  T:          {self.T}" if self.T else "  T:          N/A (senior)",
            f"  STS:        {self.is_STS}",
            "",
            "LOOKUP VALUES:",
            f"  RW_base:    {self.RW_base:.2%}",
            f"  a:          {self.a}",
            f"  b:          {self.b}",
            f"  c:          {self.c}" if self.c else "  c:          N/A (senior)",
            "",
            "CALCULATION:",
            f"  Maturity factor (a + b * M_T):  {self.a} + {self.b} * {self.M_T} = {self.maturity_factor:.4f}",
        ]

        if self.seniority.lower() == "senior":
            lines.append(f"  RW = RW_base * maturity_factor")
            lines.append(f"     = {self.RW_base:.2%} * {self.maturity_factor:.4f}")
            lines.append(f"     = {self.RW_unadjusted:.2%}")
        else:
            lines.append(f"  Thickness factor (T^-c):        {self.T}^(-{self.c}) = {self.thickness_factor:.4f}")
            lines.append(f"  RW = RW_base * maturity_factor * thickness_factor")
            lines.append(f"     = {self.RW_base:.2%} * {self.maturity_factor:.4f} * {self.thickness_factor:.4f}")
            lines.append(f"     = {self.RW_unadjusted:.2%}")

        lines.extend([
            "",
            "FLOOR/CAP:",
            f"  Floor:      {self.floor:.2%}",
            f"  Cap:        {self.cap:.2%}",
            "",
            "FINAL RESULT:",
            f"  RW_final:   {self.RW_final:.2%}",
        ])

        if self.exposure is not None:
            lines.extend([
                "",
                f"  Exposure:   {self.exposure:,.2f}",
                f"  RWA:        {self.RWA:,.2f}",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def pd_to_cqs(pd: float) -> int:
    """
    Map Probability of Default to Credit Quality Step.

    Args:
        pd: Probability of Default as decimal (e.g., 0.0003 for 0.03%)

    Returns:
        CQS: Credit Quality Step (1-17)
    """
    for threshold, cqs in PD_TO_CQS_THRESHOLDS:
        if pd <= threshold:
            return cqs
    return 17


def rating_to_cqs(rating: str) -> int:
    """
    Map external rating to Credit Quality Step.

    Args:
        rating: External rating (e.g., "AA", "BBB+")

    Returns:
        CQS: Credit Quality Step (1-17)
    """
    # Direct mapping for exact matches
    if rating in RATING_TO_CQS:
        return RATING_TO_CQS[rating]

    # Handle rating modifiers (AA+, AA-)
    base_rating = rating.rstrip("+-")
    if base_rating in RATING_TO_CQS:
        cqs = RATING_TO_CQS[base_rating]
        if rating.endswith("+") and cqs > 1:
            return cqs - 1
        elif rating.endswith("-") and cqs < 17:
            return cqs + 1
        return cqs

    # Fallback: use PD mapping
    pd = RATING_TO_PD.get(rating, 0.10)
    return pd_to_cqs(pd)


def infer_seniority(pd: float, threshold: float = 0.0010) -> str:
    """
    Infer seniority from PD (heuristic when structural data unavailable).

    Args:
        pd: Probability of Default as decimal
        threshold: PD cutoff for senior classification (default 0.10%)

    Returns:
        "senior" or "non-senior"
    """
    return "senior" if pd <= threshold else "non-senior"


def get_rw_base(cqs: int, seniority: str) -> float:
    """
    Look up base risk weight from regulatory tables.

    Args:
        cqs: Credit Quality Step (1-17)
        seniority: "senior" or "non-senior"

    Returns:
        RW_base as decimal (e.g., 0.15 for 15%)
    """
    cqs = max(1, min(17, cqs))
    senior_rw, non_senior_rw = RW_BASE_TABLE[cqs]
    return senior_rw if seniority.lower() == "senior" else non_senior_rw


def get_coefficients(cqs: int) -> Tuple[float, float, float]:
    """
    Get adjustment coefficients for given CQS.

    Args:
        cqs: Credit Quality Step (1-17)

    Returns:
        Tuple of (a, b, c) where:
            a, b: maturity adjustment coefficients
            c: thickness adjustment exponent
    """
    cqs = max(1, min(17, cqs))
    return COEFFICIENTS_TABLE[cqs]


def calculate_maturity_factor(a: float, b: float, M_T: float) -> float:
    """
    Calculate maturity adjustment factor.

    Formula: maturity_factor = a + b * M_T

    Args:
        a: Intercept coefficient
        b: Slope coefficient
        M_T: Tranche maturity in years (will be floored at 1, capped at 5)

    Returns:
        Maturity adjustment factor
    """
    M_T = max(1.0, min(5.0, M_T))
    return a + b * M_T


def calculate_thickness_factor(T: float, c: float) -> float:
    """
    Calculate thickness adjustment factor (non-senior tranches only).

    Formula: thickness_factor = T^(-c)

    Args:
        T: Tranche thickness (Detachment - Attachment)
        c: Thickness exponent from coefficients table

    Returns:
        Thickness adjustment factor
    """
    if T <= 0:
        raise ValueError("Thickness T must be positive")
    return T ** (-c)


def get_floor(seniority: str, is_STS: bool) -> float:
    """
    Determine RW floor based on seniority and STS status.

    Args:
        seniority: "senior" or "non-senior"
        is_STS: Whether securitisation qualifies as STS

    Returns:
        Floor as decimal
    """
    if seniority.lower() == "senior" and is_STS:
        return 0.10  # 10% for senior STS
    return 0.15  # 15% otherwise


def calculate_erba_rw(
    cqs: int,
    seniority: str,
    M_T: float,
    T: Optional[float] = None,
    is_STS: bool = False,
    exposure: Optional[float] = None,
    verbose: bool = False
) -> ERBAResult:
    """
    Calculate ERBA Risk Weight with full breakdown.

    Args:
        cqs: Credit Quality Step (1-17)
        seniority: "senior" or "non-senior"
        M_T: Tranche maturity in years
        T: Tranche thickness (required for non-senior)
        is_STS: Whether securitisation qualifies as STS
        exposure: Optional exposure amount for RWA calculation
        verbose: If True, print detailed calculation

    Returns:
        ERBAResult with all intermediate values and final RW

    Formulas:
        Senior:     RW = RW_base * (a + b * M_T)
        Non-Senior: RW = RW_base * (a + b * M_T) * T^(-c)
    """
    seniority = seniority.lower()

    if seniority not in ("senior", "non-senior"):
        raise ValueError("Seniority must be 'senior' or 'non-senior'")

    if seniority == "non-senior" and T is None:
        raise ValueError("Thickness T required for non-senior tranches")

    # Cap/floor maturity
    M_T = max(1.0, min(5.0, M_T))

    # Step 1: Look up base RW
    RW_base = get_rw_base(cqs, seniority)

    # Step 2: Get coefficients
    a, b, c = get_coefficients(cqs)

    # Step 3: Calculate maturity factor
    maturity_factor = calculate_maturity_factor(a, b, M_T)

    # Step 4: Calculate RW
    if seniority == "senior":
        thickness_factor = None
        RW_unadjusted = RW_base * maturity_factor
    else:
        thickness_factor = calculate_thickness_factor(T, c)
        RW_unadjusted = RW_base * maturity_factor * thickness_factor

    # Step 5: Apply floor and cap
    floor = get_floor(seniority, is_STS)
    cap = 12.50  # 1250%
    RW_final = max(floor, min(cap, RW_unadjusted))

    # Step 6: Calculate RWA if exposure provided
    RWA = exposure * RW_final if exposure is not None else None

    result = ERBAResult(
        cqs=cqs,
        rating=CQS_TO_RATING.get(cqs, "N/A"),
        seniority=seniority,
        M_T=M_T,
        T=T,
        is_STS=is_STS,
        RW_base=RW_base,
        a=a,
        b=b,
        c=c if seniority == "non-senior" else None,
        maturity_factor=maturity_factor,
        thickness_factor=thickness_factor,
        RW_unadjusted=RW_unadjusted,
        floor=floor,
        cap=cap,
        RW_final=RW_final,
        exposure=exposure,
        RWA=RWA,
    )

    if verbose:
        print(result)

    return result


def calculate_erba_from_pd(
    pd: float,
    M_T: float = 3.0,
    T: float = 0.05,
    seniority: Optional[str] = None,
    is_STS: bool = False,
    exposure: Optional[float] = None,
    seniority_threshold: float = 0.0010,
    verbose: bool = False
) -> ERBAResult:
    """
    Calculate ERBA Risk Weight starting from PD.

    Args:
        pd: Probability of Default as decimal (e.g., 0.0003 for 0.03%)
        M_T: Tranche maturity in years (default: 3)
        T: Tranche thickness (default: 0.05)
        seniority: Override seniority instead of inferring from PD
        is_STS: Whether securitisation qualifies as STS
        exposure: Optional exposure amount for RWA calculation
        seniority_threshold: PD cutoff for senior classification (default: 0.10%)
        verbose: If True, print detailed calculation

    Returns:
        ERBAResult with all intermediate values and final RW
    """
    cqs = pd_to_cqs(pd)

    if seniority is None:
        seniority = infer_seniority(pd, seniority_threshold)

    # For senior tranches, T is not used
    if seniority.lower() == "senior":
        T = None

    return calculate_erba_rw(
        cqs=cqs,
        seniority=seniority,
        M_T=M_T,
        T=T,
        is_STS=is_STS,
        exposure=exposure,
        verbose=verbose
    )


def calculate_erba_from_rating(
    rating: str,
    seniority: str,
    M_T: float = 3.0,
    T: Optional[float] = None,
    is_STS: bool = False,
    exposure: Optional[float] = None,
    verbose: bool = False
) -> ERBAResult:
    """
    Calculate ERBA Risk Weight from external rating.

    Args:
        rating: External rating (e.g., "AA", "BBB+")
        seniority: "senior" or "non-senior"
        M_T: Tranche maturity in years
        T: Tranche thickness (required for non-senior)
        is_STS: Whether securitisation qualifies as STS
        exposure: Optional exposure amount for RWA calculation
        verbose: If True, print detailed calculation

    Returns:
        ERBAResult with all intermediate values and final RW
    """
    cqs = rating_to_cqs(rating)

    return calculate_erba_rw(
        cqs=cqs,
        seniority=seniority,
        M_T=M_T,
        T=T,
        is_STS=is_STS,
        exposure=exposure,
        verbose=verbose
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quick_erba_rw(
    pd: float = None,
    rating: str = None,
    cqs: int = None,
    seniority: str = "senior",
    M_T: float = 3.0,
    T: float = 0.05,
    is_STS: bool = False
) -> float:
    """
    Quick RW calculation with flexible inputs.

    Provide one of: pd, rating, or cqs.

    Args:
        pd: Probability of Default as decimal
        rating: External rating (e.g., "AA", "BBB+")
        cqs: Credit Quality Step (1-17)
        seniority: "senior" or "non-senior"
        M_T: Tranche maturity in years
        T: Tranche thickness (for non-senior)
        is_STS: Whether STS qualified

    Returns:
        Final Risk Weight as decimal
    """
    if cqs is not None:
        pass
    elif pd is not None:
        cqs = pd_to_cqs(pd)
    elif rating is not None:
        cqs = rating_to_cqs(rating)
    else:
        raise ValueError("Must provide one of: pd, rating, or cqs")

    result = calculate_erba_rw(
        cqs=cqs,
        seniority=seniority,
        M_T=M_T,
        T=T if seniority.lower() == "non-senior" else None,
        is_STS=is_STS
    )
    return result.RW_final


def calculate_erba_rwa(
    ead: float,
    rating: str = None,
    pd: float = None,
    cqs: int = None,
    seniority: str = "senior",
    maturity: float = 3.0,
    thickness: float = 0.05,
    is_sts: bool = False
) -> dict:
    """
    Calculate ERBA RWA - compatible interface with rwa_calc.py.

    Args:
        ead: Exposure at Default
        rating: External rating (e.g., "AA", "BBB+")
        pd: Probability of Default (alternative to rating)
        cqs: Credit Quality Step (alternative to rating/pd)
        seniority: "senior" or "non-senior"
        maturity: Tranche maturity in years
        thickness: Tranche thickness (detachment - attachment)
        is_sts: Whether STS qualified

    Returns:
        dict with calculation results
    """
    # Determine CQS from inputs
    if cqs is not None:
        pass
    elif rating is not None:
        cqs = rating_to_cqs(rating)
    elif pd is not None:
        cqs = pd_to_cqs(pd)
    else:
        raise ValueError("Must provide one of: rating, pd, or cqs")

    # Calculate ERBA
    T = thickness if seniority.lower() == "non-senior" else None
    result = calculate_erba_rw(
        cqs=cqs,
        seniority=seniority,
        M_T=maturity,
        T=T,
        is_STS=is_sts,
        exposure=ead
    )

    return {
        "approach": "CRR2 ERBA",
        "ead": ead,
        "rating": result.rating,
        "cqs": result.cqs,
        "seniority": seniority,
        "maturity": maturity,
        "thickness": thickness if seniority.lower() == "non-senior" else None,
        "is_sts": is_sts,
        "risk_weight_pct": result.RW_final * 100,
        "rwa": result.RWA,
        "capital_requirement_k": result.RW_final * 0.08,
    }


def print_erba_table(M_T: float = 3.0, T: float = 0.05):
    """Print a complete RW lookup table for given M_T and T."""
    print(f"\nERBA Risk Weight Table (M_T={M_T}, T={T})")
    print("=" * 70)
    print(f"{'CQS':<5} {'Rating':<8} {'Senior':<12} {'Non-Senior':<12} {'STS Senior':<12}")
    print("-" * 70)

    for cqs in range(1, 18):
        rating = CQS_TO_RATING[cqs]
        senior_rw = quick_erba_rw(cqs=cqs, seniority="senior", M_T=M_T)
        non_senior_rw = quick_erba_rw(cqs=cqs, seniority="non-senior", M_T=M_T, T=T)
        sts_rw = quick_erba_rw(cqs=cqs, seniority="senior", M_T=M_T, is_STS=True)
        print(f"{cqs:<5} {rating:<8} {senior_rw:>10.2%}   {non_senior_rw:>10.2%}   {sts_rw:>10.2%}")

    print("=" * 70)


def compare_erba_simple_vs_crr2(
    ead: float,
    rating: str,
    seniority: str,
    maturity: float = 3.0,
    thickness: float = 0.05
) -> dict:
    """
    Compare simple ERBA (rwa_calc.py) vs CRR2 ERBA.

    Args:
        ead: Exposure at Default
        rating: External rating
        seniority: "senior" or "non-senior"
        maturity: Tranche maturity
        thickness: Tranche thickness

    Returns:
        dict with both approaches' results
    """
    # CRR2 ERBA
    crr2_result = calculate_erba_rwa(
        ead=ead,
        rating=rating,
        seniority=seniority,
        maturity=maturity,
        thickness=thickness
    )

    # Import simple ERBA from rwa_calc for comparison
    try:
        from rwa_calc import calculate_erba_rwa as simple_erba
        simple_result = simple_erba(ead, rating, seniority, maturity)
        simple_rw = simple_result["risk_weight_pct"]
        simple_rwa = simple_result["rwa"]
    except ImportError:
        simple_rw = None
        simple_rwa = None

    return {
        "ead": ead,
        "rating": rating,
        "seniority": seniority,
        "maturity": maturity,
        "thickness": thickness,
        "crr2_erba": {
            "risk_weight_pct": crr2_result["risk_weight_pct"],
            "rwa": crr2_result["rwa"],
        },
        "simple_erba": {
            "risk_weight_pct": simple_rw,
            "rwa": simple_rwa,
        } if simple_rw else None,
    }


# =============================================================================
# MAIN - EXAMPLES
# =============================================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("CRR2 ERBA MODULE - EXAMPLES")
    print("=" * 70)

    # Example 1: Full calculation with all inputs
    print("\n--- Example 1: Full ERBA calculation (non-senior) ---")
    result = calculate_erba_rw(
        cqs=5,
        seniority="non-senior",
        M_T=3.0,
        T=0.07,
        is_STS=False,
        exposure=1_000_000,
        verbose=True
    )

    # Example 2: From PD with defaults
    print("\n--- Example 2: ERBA from PD (senior) ---")
    result = calculate_erba_from_pd(
        pd=0.0003,  # 0.03%
        M_T=4.0,
        verbose=True
    )

    # Example 3: From rating
    print("\n--- Example 3: ERBA from rating ---")
    result = calculate_erba_from_rating(
        rating="BBB",
        seniority="senior",
        M_T=2.5,
        is_STS=True,
        verbose=True
    )

    # Example 4: Quick RW lookups
    print("\n--- Example 4: Quick RW lookups ---")
    test_cases = [
        {"pd": 0.0001, "seniority": "senior"},
        {"rating": "AA", "seniority": "senior"},
        {"cqs": 5, "seniority": "non-senior", "T": 0.10},
        {"rating": "BBB-", "seniority": "senior", "is_STS": True},
    ]
    for case in test_cases:
        rw = quick_erba_rw(**case)
        label = ", ".join(f"{k}={v}" for k, v in case.items())
        print(f"  {label} -> RW={rw:.2%}")

    # Example 5: RWA calculation (compatible interface)
    print("\n--- Example 5: RWA calculation ---")
    rwa_result = calculate_erba_rwa(
        ead=10_000_000,
        rating="A",
        seniority="senior",
        maturity=4.0,
        is_sts=True
    )
    print(f"  EAD:     ${rwa_result['ead']:,.0f}")
    print(f"  Rating:  {rwa_result['rating']} (CQS {rwa_result['cqs']})")
    print(f"  RW:      {rwa_result['risk_weight_pct']:.1f}%")
    print(f"  RWA:     ${rwa_result['rwa']:,.0f}")

    # Example 6: Full table
    print("\n--- Example 6: Complete RW Table ---")
    print_erba_table(M_T=3.0, T=0.05)
