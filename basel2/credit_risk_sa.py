"""
Basel II Standardised Approach for Credit Risk

Implements the Basel II (2004) Standardised Approach for credit risk,
which uses external credit ratings to determine risk weights.

Key differences from Basel III SA-CR:
- Different risk weight tables
- No SME supporting factor
- Different real estate treatment
- Simpler off-balance sheet CCFs
"""

# =============================================================================
# Risk Weight Tables (Basel II - Paragraph 53 onwards)
# =============================================================================

# Sovereign risk weights (Para 53)
SA_SOVEREIGN_RW = {
    "AAA": 0, "AA+": 0, "AA": 0, "AA-": 0,
    "A+": 20, "A": 20, "A-": 20,
    "BBB+": 50, "BBB": 50, "BBB-": 50,
    "BB+": 100, "BB": 100, "BB-": 100,
    "B+": 100, "B": 100, "B-": 100,
    "below_B-": 150,
    "unrated": 100,
}

# Bank risk weights - Option 1: Based on sovereign rating (Para 63)
SA_BANK_OPTION1_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 50, "A": 50, "A-": 50,
    "BBB+": 100, "BBB": 100, "BBB-": 100,
    "BB+": 100, "BB": 100, "BB-": 100,
    "B+": 100, "B": 100, "B-": 100,
    "below_B-": 150,
    "unrated": 100,
}

# Bank risk weights - Option 2: Based on bank's own rating (Para 63)
SA_BANK_OPTION2_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 50, "A": 50, "A-": 50,
    "BBB+": 50, "BBB": 50, "BBB-": 50,
    "BB+": 100, "BB": 100, "BB-": 100,
    "B+": 100, "B": 100, "B-": 100,
    "below_B-": 150,
    "unrated": 50,
}

# Bank risk weights - Option 2 short-term claims (Para 64)
SA_BANK_OPTION2_SHORT_TERM_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 20, "A": 20, "A-": 20,
    "BBB+": 20, "BBB": 20, "BBB-": 20,
    "BB+": 50, "BB": 50, "BB-": 50,
    "B+": 50, "B": 50, "B-": 50,
    "below_B-": 150,
    "unrated": 20,
}

# Corporate risk weights (Para 66)
SA_CORPORATE_RW = {
    "AAA": 20, "AA+": 20, "AA": 20, "AA-": 20,
    "A+": 50, "A": 50, "A-": 50,
    "BBB+": 100, "BBB": 100, "BBB-": 100,
    "BB+": 100, "BB": 100, "BB-": 100,  # Basel II: BB- to BB+ is 100%
    "below_BB-": 150,
    "unrated": 100,
}

# Retail risk weights (Para 69-71)
SA_RETAIL_RW = {
    "regulatory_retail": 75,  # Qualifying retail
}

# Real estate risk weights (Para 72-73)
SA_REAL_ESTATE_RW = {
    "residential_mortgage": 35,  # Fully secured by residential property
    "commercial_mortgage": 100,  # Commercial real estate (national discretion for 50%)
}

# Past due loans (Para 75)
SA_PAST_DUE_RW = {
    "unsecured": 150,  # Specific provisions < 20%
    "unsecured_provisioned": 100,  # Specific provisions >= 20%
    "secured_residential": 100,  # Secured by residential property
    "secured_residential_provisioned": 50,  # With provisions >= 50%
}

# Higher risk categories (Para 79-80)
SA_HIGHER_RISK_RW = {
    "venture_capital": 150,
    "private_equity": 150,
    "securitization_unrated_below_bb-": 350,  # Deduction for below BB-
}

# Other assets (Para 81)
SA_OTHER_RW = {
    "cash": 0,
    "gold_bullion": 0,
    "other": 100,
}


def get_sovereign_rw(rating: str = "unrated") -> float:
    """Get Basel II risk weight for sovereign exposures."""
    return SA_SOVEREIGN_RW.get(rating, SA_SOVEREIGN_RW.get("unrated", 100))


def get_bank_rw(
    rating: str = "unrated",
    option: int = 2,
    short_term: bool = False,
    sovereign_rating: str = None
) -> float:
    """
    Get Basel II risk weight for bank exposures.

    Parameters:
    -----------
    rating : str
        Bank's external rating (for Option 2)
    option : int
        1 = Based on sovereign rating, 2 = Based on bank's own rating
    short_term : bool
        True if maturity <= 3 months (Option 2 only)
    sovereign_rating : str
        Sovereign rating (required for Option 1)

    Returns:
    --------
    float
        Risk weight percentage
    """
    if option == 1:
        # Option 1: one category less favorable than sovereign
        sov_rating = sovereign_rating or rating
        sov_rw = get_sovereign_rw(sov_rating)
        # Map sovereign RW to bank RW (one notch worse)
        mapping = {0: 20, 20: 50, 50: 100, 100: 100, 150: 150}
        return mapping.get(sov_rw, 100)
    else:
        # Option 2: based on bank's own rating
        if short_term:
            return SA_BANK_OPTION2_SHORT_TERM_RW.get(rating, 20)
        return SA_BANK_OPTION2_RW.get(rating, 50)


def get_corporate_rw(rating: str = "unrated") -> float:
    """Get Basel II risk weight for corporate exposures."""
    return SA_CORPORATE_RW.get(rating, 100)


def get_retail_rw() -> float:
    """
    Get Basel II risk weight for regulatory retail exposures.

    Requirements for regulatory retail (Para 70):
    - Orientation: exposure to individual or small business
    - Product: revolving credits, lines of credit, personal loans, leases,
               small business facilities
    - Granularity: no aggregate exposure to one counterparty > 0.2% of portfolio
    - Low value: max aggregated retail exposure to counterparty <= EUR 1 million
    """
    return SA_RETAIL_RW["regulatory_retail"]


def get_real_estate_rw(
    property_type: str = "residential",
    fully_secured: bool = True
) -> float:
    """
    Get Basel II risk weight for real estate exposures.

    Parameters:
    -----------
    property_type : str
        "residential" or "commercial"
    fully_secured : bool
        Whether loan is fully secured by the property

    Returns:
    --------
    float
        Risk weight percentage
    """
    if not fully_secured:
        return 100  # Unsecured portion treated as corporate

    if property_type == "residential":
        return SA_REAL_ESTATE_RW["residential_mortgage"]
    else:
        return SA_REAL_ESTATE_RW["commercial_mortgage"]


def get_past_due_rw(
    secured_by_residential: bool = False,
    specific_provision_pct: float = 0.0
) -> float:
    """
    Get Basel II risk weight for past due loans (> 90 days).

    Parameters:
    -----------
    secured_by_residential : bool
        Secured by residential property
    specific_provision_pct : float
        Specific provisions as % of outstanding (e.g., 0.20 for 20%)
    """
    if secured_by_residential:
        if specific_provision_pct >= 0.50:
            return SA_PAST_DUE_RW["secured_residential_provisioned"]
        return SA_PAST_DUE_RW["secured_residential"]
    else:
        if specific_provision_pct >= 0.20:
            return SA_PAST_DUE_RW["unsecured_provisioned"]
        return SA_PAST_DUE_RW["unsecured"]


def calculate_sa_rwa(
    ead: float,
    exposure_class: str,
    rating: str = "unrated",
    **kwargs
) -> dict:
    """
    Calculate RWA using Basel II Standardised Approach.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    exposure_class : str
        One of: "sovereign", "bank", "corporate", "retail",
        "residential_mortgage", "commercial_mortgage", "past_due", "other"
    rating : str
        External credit rating
    **kwargs : dict
        Additional parameters:
        - bank: option (1 or 2), short_term, sovereign_rating
        - real_estate: fully_secured
        - past_due: secured_by_residential, specific_provision_pct

    Returns:
    --------
    dict
        RWA calculation results
    """
    if exposure_class == "sovereign":
        risk_weight = get_sovereign_rw(rating)

    elif exposure_class == "bank":
        risk_weight = get_bank_rw(
            rating=rating,
            option=kwargs.get("option", 2),
            short_term=kwargs.get("short_term", False),
            sovereign_rating=kwargs.get("sovereign_rating")
        )

    elif exposure_class == "corporate":
        risk_weight = get_corporate_rw(rating)

    elif exposure_class == "retail":
        risk_weight = get_retail_rw()

    elif exposure_class == "residential_mortgage":
        risk_weight = get_real_estate_rw(
            property_type="residential",
            fully_secured=kwargs.get("fully_secured", True)
        )

    elif exposure_class == "commercial_mortgage":
        risk_weight = get_real_estate_rw(
            property_type="commercial",
            fully_secured=kwargs.get("fully_secured", True)
        )

    elif exposure_class == "past_due":
        risk_weight = get_past_due_rw(
            secured_by_residential=kwargs.get("secured_by_residential", False),
            specific_provision_pct=kwargs.get("specific_provision_pct", 0.0)
        )

    elif exposure_class == "other":
        risk_weight = SA_OTHER_RW.get(kwargs.get("asset_type", "other"), 100)

    else:
        raise ValueError(f"Unknown exposure class: {exposure_class}")

    rwa = ead * risk_weight / 100

    return {
        "approach": "Basel II SA",
        "ead": ead,
        "exposure_class": exposure_class,
        "rating": rating,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement": rwa * 0.08,
        "parameters": kwargs,
    }


def calculate_batch_sa_rwa(exposures: list[dict]) -> dict:
    """
    Calculate Basel II SA RWA for a batch of exposures.

    Parameters:
    -----------
    exposures : list of dict
        Each dict: ead, exposure_class, rating, and class-specific params

    Returns:
    --------
    dict
        Aggregated results
    """
    results = []
    total_ead = 0
    total_rwa = 0

    for exp in exposures:
        ead = exp["ead"]
        exposure_class = exp["exposure_class"]
        rating = exp.get("rating", "unrated")
        kwargs = {k: v for k, v in exp.items()
                  if k not in ["ead", "exposure_class", "rating"]}

        result = calculate_sa_rwa(ead, exposure_class, rating, **kwargs)
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]

    return {
        "approach": "Basel II SA",
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "total_capital_requirement": total_rwa * 0.08,
        "exposures": results,
    }


# =============================================================================
# Credit Conversion Factors (CCF) for Off-Balance Sheet (Para 82-89)
# =============================================================================

CCF_FACTORS = {
    "direct_credit_substitute": 1.00,  # 100% CCF
    "transaction_related_contingent": 0.50,  # 50% CCF
    "short_term_self_liquidating": 0.20,  # 20% CCF
    "commitments_over_1y": 0.50,  # 50% CCF (original maturity > 1 year)
    "commitments_up_to_1y": 0.20,  # 20% CCF (original maturity <= 1 year)
    "unconditionally_cancellable": 0.00,  # 0% CCF
    "nif_ruf": 0.50,  # Note issuance facilities
    "repo_style": 1.00,  # Repo-style transactions
}


def calculate_off_balance_sheet_ead(
    notional: float,
    commitment_type: str,
    drawn_amount: float = 0
) -> dict:
    """
    Calculate EAD for off-balance sheet exposures using Basel II CCFs.

    Parameters:
    -----------
    notional : float
        Total commitment amount
    commitment_type : str
        Type of commitment (see CCF_FACTORS)
    drawn_amount : float
        Amount already drawn

    Returns:
    --------
    dict
        EAD calculation with CCF applied
    """
    ccf = CCF_FACTORS.get(commitment_type, 1.00)
    undrawn = notional - drawn_amount
    ead = drawn_amount + (undrawn * ccf)

    return {
        "notional": notional,
        "drawn_amount": drawn_amount,
        "undrawn_amount": undrawn,
        "commitment_type": commitment_type,
        "ccf": ccf,
        "ead": ead,
    }


# =============================================================================
# PD-Based Wrappers (for users with PD data instead of ratings)
# =============================================================================

# Import rating mapping from IRB module
from .credit_risk_irb import get_rating_from_pd, RATING_TO_PD


def calculate_sa_rwa_from_pd(
    ead: float,
    pd: float,
    exposure_class: str,
    **kwargs
) -> dict:
    """
    Calculate Basel II SA RWA using PD instead of rating.

    Automatically derives the closest rating from PD, then applies
    the standard SA risk weights.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    pd : float
        Probability of Default (e.g., 0.02 for 2%)
    exposure_class : str
        Exposure class (sovereign, bank, corporate, etc.)
    **kwargs : dict
        Additional class-specific parameters

    Returns:
    --------
    dict
        SA RWA calculation with derived rating
    """
    # Derive rating from PD
    derived_rating = get_rating_from_pd(pd)

    # Calculate using standard SA function
    result = calculate_sa_rwa(ead, exposure_class, derived_rating, **kwargs)

    # Add PD-related fields
    result["input_pd"] = pd
    result["derived_rating"] = derived_rating
    result["rating_pd"] = RATING_TO_PD.get(derived_rating, pd)

    return result


def calculate_batch_sa_rwa_from_pd(exposures: list[dict]) -> dict:
    """
    Calculate Basel II SA RWA for a batch of exposures using PD.

    Each exposure should have 'pd' instead of 'rating'.

    Parameters:
    -----------
    exposures : list of dict
        Each dict: ead, pd, exposure_class, and class-specific params

    Returns:
    --------
    dict
        Aggregated results with derived ratings
    """
    results = []
    total_ead = 0
    total_rwa = 0

    for exp in exposures:
        ead = exp["ead"]
        pd = exp.get("pd", 0.01)  # Default 1% if not specified
        exposure_class = exp["exposure_class"]
        kwargs = {k: v for k, v in exp.items()
                  if k not in ["ead", "pd", "exposure_class"]}

        result = calculate_sa_rwa_from_pd(ead, pd, exposure_class, **kwargs)
        results.append(result)
        total_ead += result["ead"]
        total_rwa += result["rwa"]

    return {
        "approach": "Basel II SA (PD-based)",
        "total_ead": total_ead,
        "total_rwa": total_rwa,
        "average_risk_weight_pct": (total_rwa / total_ead * 100) if total_ead > 0 else 0,
        "total_capital_requirement": total_rwa * 0.08,
        "exposures": results,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Standardised Approach - Credit Risk")
    print("=" * 70)

    # Example exposures
    exposures = [
        {"ead": 1_000_000, "exposure_class": "sovereign", "rating": "AA"},
        {"ead": 1_000_000, "exposure_class": "bank", "rating": "A", "option": 2},
        {"ead": 1_000_000, "exposure_class": "corporate", "rating": "BBB"},
        {"ead": 1_000_000, "exposure_class": "corporate", "rating": "unrated"},
        {"ead": 1_000_000, "exposure_class": "retail"},
        {"ead": 1_000_000, "exposure_class": "residential_mortgage"},
        {"ead": 1_000_000, "exposure_class": "commercial_mortgage"},
    ]

    print(f"\n  {'Exposure Class':<22} {'Rating':<10} {'RW':>8} {'RWA':>15}")
    print(f"  {'-'*22} {'-'*10} {'-'*8} {'-'*15}")

    for exp in exposures:
        result = calculate_sa_rwa(**exp)
        rating = exp.get("rating", "-")
        print(f"  {result['exposure_class']:<22} {rating:<10} "
              f"{result['risk_weight_pct']:>7.0f}% ${result['rwa']:>13,.0f}")

    # Batch calculation
    batch = calculate_batch_sa_rwa(exposures)
    print(f"\n  {'Total':<22} {'':<10} "
          f"{batch['average_risk_weight_pct']:>7.1f}% ${batch['total_rwa']:>13,.0f}")
    print(f"\n  Capital Requirement (8%): ${batch['total_capital_requirement']:,.0f}")
