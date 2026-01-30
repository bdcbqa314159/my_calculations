"""
RWA Calculator - IRB Foundation Approach & ERBA Comparison

Calculates Risk-Weighted Assets using:
- IRB Foundation: PD estimated by bank, LGD prescribed by regulation
- ERBA: External Ratings Based Approach for securitizations

Allows comparison between approaches.
"""

import math
from scipy.stats import norm


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


# Example usage
if __name__ == "__main__":
    # Single exposure example
    print("=" * 60)
    print("IRB Foundation RWA Calculator")
    print("=" * 60)

    # Example: Corporate exposure
    result = calculate_rwa(
        ead=1_000_000,
        pd=0.02,  # 2% PD
        lgd=0.45,  # 45% LGD (F-IRB standard for senior unsecured)
        maturity=3.0,
        asset_class="corporate"
    )

    print("\nSingle Exposure Example:")
    print(f"  EAD:                  ${result['ead']:,.2f}")
    print(f"  PD:                   {result['pd']*100:.2f}%")
    print(f"  LGD:                  {result['lgd']*100:.2f}%")
    print(f"  Maturity:             {result['maturity']:.1f} years")
    print(f"  Asset Class:          {result['asset_class']}")
    print(f"  Correlation (R):      {result['correlation']:.4f}")
    print(f"  Capital Req (K):      {result['capital_requirement_k']*100:.2f}%")
    print(f"  Risk Weight:          {result['risk_weight_pct']:.2f}%")
    print(f"  RWA:                  ${result['rwa']:,.2f}")
    print(f"  Expected Loss:        ${result['expected_loss']:,.2f}")

    # ERBA vs IRB Comparison
    print("\n" + "=" * 60)
    print("ERBA vs IRB Comparison")
    print("=" * 60)

    comparison = compare_erba_vs_irb(
        ead=1_000_000,
        rating="BBB",
        seniority="senior",
        maturity=3.0,
        lgd=0.45,
        asset_class="corporate"
    )

    print(f"\n  Exposure: ${comparison['ead']:,.0f}, Rating: {comparison['rating']}, PD: {comparison['pd_used']*100:.2f}%")
    print(f"\n  {'Approach':<10} {'Risk Weight':>12} {'RWA':>15} {'Capital K':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*15} {'-'*12}")
    print(f"  {'ERBA':<10} {comparison['erba']['risk_weight_pct']:>11.1f}% ${comparison['erba']['rwa']:>13,.0f} {comparison['erba']['capital_requirement_k']*100:>11.2f}%")
    print(f"  {'IRB-F':<10} {comparison['irb']['risk_weight_pct']:>11.1f}% ${comparison['irb']['rwa']:>13,.0f} {comparison['irb']['capital_requirement_k']*100:>11.2f}%")
    print(f"\n  More conservative: {comparison['more_conservative']} (diff: ${abs(comparison['rwa_difference']):,.0f})")

    # Batch ERBA vs IRB comparison
    print("\n" + "=" * 60)
    print("Batch ERBA vs IRB Comparison")
    print("=" * 60)

    exposures = [
        {"ead": 500_000, "rating": "A", "seniority": "senior", "maturity": 2.5},
        {"ead": 300_000, "rating": "BBB", "seniority": "senior", "maturity": 3.0},
        {"ead": 200_000, "rating": "BB", "seniority": "non_senior", "maturity": 4.0},
    ]

    batch_comparison = compare_batch_erba_vs_irb(exposures)

    print(f"\n  Total EAD:            ${batch_comparison['total_ead']:,.0f}")
    print(f"  Total ERBA RWA:       ${batch_comparison['total_erba_rwa']:,.0f} (avg RW: {batch_comparison['erba_avg_risk_weight']:.1f}%)")
    print(f"  Total IRB RWA:        ${batch_comparison['total_irb_rwa']:,.0f} (avg RW: {batch_comparison['irb_avg_risk_weight']:.1f}%)")
    print(f"  RWA Difference:       ${batch_comparison['total_rwa_difference']:,.0f}")
    print(f"  More conservative:    {batch_comparison['more_conservative_overall']}")

    print("\n  Individual Exposures:")
    print(f"  {'Rating':<6} {'ERBA RW':>10} {'IRB RW':>10} {'Winner':>10}")
    print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*10}")
    for exp in batch_comparison['exposures']:
        print(f"  {exp['rating']:<6} {exp['erba']['risk_weight_pct']:>9.1f}% {exp['irb']['risk_weight_pct']:>9.1f}% {exp['more_conservative']:>10}")
