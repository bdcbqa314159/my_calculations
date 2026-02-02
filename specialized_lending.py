"""
Specialized Lending - Slotting Criteria Approach

Implements:
- IPRE: Income-Producing Real Estate
- HVCRE: High-Volatility Commercial Real Estate
- Object Finance (ships, aircraft, etc.)
- Project Finance
- Commodities Finance

Reference: CRE33 (Supervisory Slotting Criteria)
"""

from enum import Enum
from typing import Optional


# =============================================================================
# Slotting Categories and Risk Weights (CRE33.4)
# =============================================================================

class SlottingCategory(Enum):
    STRONG = "strong"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    WEAK = "weak"
    DEFAULT = "default"


# Risk weights by category and exposure type (CRE33.5)
SLOTTING_RISK_WEIGHTS = {
    # Standard slotting risk weights
    "standard": {
        SlottingCategory.STRONG: 70,
        SlottingCategory.GOOD: 90,
        SlottingCategory.SATISFACTORY: 115,
        SlottingCategory.WEAK: 250,
        SlottingCategory.DEFAULT: 0,  # Deducted or 100% for secured portion
    },
    # HVCRE has higher risk weights
    "hvcre": {
        SlottingCategory.STRONG: 95,
        SlottingCategory.GOOD: 120,
        SlottingCategory.SATISFACTORY: 140,
        SlottingCategory.WEAK: 250,
        SlottingCategory.DEFAULT: 0,
    },
}

# Supervisory slotting criteria factors
SLOTTING_FACTORS = {
    "financial_strength": {
        "description": "Debt service coverage, loan-to-value, project economics",
        "strong": "DSCR > 1.5x, LTV < 60%",
        "good": "DSCR 1.25-1.5x, LTV 60-75%",
        "satisfactory": "DSCR 1.0-1.25x, LTV 75-85%",
        "weak": "DSCR < 1.0x, LTV > 85%",
    },
    "political_legal": {
        "description": "Country risk, legal structure, regulatory environment",
        "strong": "Low country risk, strong legal framework",
        "good": "Moderate country risk, adequate legal framework",
        "satisfactory": "Higher country risk, some legal concerns",
        "weak": "High country risk, weak legal framework",
    },
    "transaction_characteristics": {
        "description": "Design risk, technology, construction risk",
        "strong": "Proven technology, fixed-price EPC",
        "good": "Standard technology, mostly fixed-price",
        "satisfactory": "Some technology risk, cost overrun history",
        "weak": "Unproven technology, significant overruns",
    },
    "sponsor_strength": {
        "description": "Sponsor track record, financial strength, support",
        "strong": "Excellent track record, strong financials",
        "good": "Good track record, adequate financials",
        "satisfactory": "Acceptable track record, limited financials",
        "weak": "Poor track record, weak financials",
    },
    "security_package": {
        "description": "Asset control, insurance, covenants",
        "strong": "First lien, comprehensive insurance, tight covenants",
        "good": "Strong security, good insurance, adequate covenants",
        "satisfactory": "Adequate security, standard insurance",
        "weak": "Weak security, limited insurance, loose covenants",
    },
}


def assess_slotting_category(
    financial_strength: int,  # 1-4 (1=strong, 4=weak)
    political_legal: int,
    transaction_characteristics: int,
    sponsor_strength: int,
    security_package: int,
    is_default: bool = False
) -> SlottingCategory:
    """
    Assess slotting category based on individual factor scores.

    Parameters:
    -----------
    financial_strength : int
        Score 1-4 (1=strong, 4=weak)
    political_legal : int
        Score 1-4
    transaction_characteristics : int
        Score 1-4
    sponsor_strength : int
        Score 1-4
    security_package : int
        Score 1-4
    is_default : bool
        Whether the exposure is in default

    Returns:
    --------
    SlottingCategory
        Overall slotting category
    """
    if is_default:
        return SlottingCategory.DEFAULT

    # Calculate weighted average (equal weights for simplicity)
    scores = [
        financial_strength,
        political_legal,
        transaction_characteristics,
        sponsor_strength,
        security_package
    ]
    avg_score = sum(scores) / len(scores)

    # Map to category
    if avg_score <= 1.5:
        return SlottingCategory.STRONG
    elif avg_score <= 2.25:
        return SlottingCategory.GOOD
    elif avg_score <= 3.0:
        return SlottingCategory.SATISFACTORY
    else:
        return SlottingCategory.WEAK


def calculate_slotting_rwa(
    ead: float,
    category: SlottingCategory,
    exposure_type: str = "standard",  # "standard" or "hvcre"
    maturity: float = 2.5,
    use_maturity_adjustment: bool = True
) -> dict:
    """
    Calculate RWA using supervisory slotting approach.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    category : SlottingCategory
        Slotting category (strong, good, satisfactory, weak, default)
    exposure_type : str
        "standard" for IPRE/PF/OF/CF, "hvcre" for high-volatility CRE
    maturity : float
        Remaining maturity in years
    use_maturity_adjustment : bool
        Whether to apply maturity adjustment for strong/good categories

    Returns:
    --------
    dict
        Slotting RWA calculation results
    """
    # Get base risk weight
    rw_table = SLOTTING_RISK_WEIGHTS.get(exposure_type, SLOTTING_RISK_WEIGHTS["standard"])
    base_rw = rw_table.get(category, 115)

    # Maturity adjustment for strong and good categories (national discretion)
    if use_maturity_adjustment and category in [SlottingCategory.STRONG, SlottingCategory.GOOD]:
        if maturity < 2.5:
            if category == SlottingCategory.STRONG:
                base_rw = 50 if exposure_type == "standard" else 70
            else:  # GOOD
                base_rw = 70 if exposure_type == "standard" else 95

    # Calculate RWA
    if category == SlottingCategory.DEFAULT:
        # For default, typically deducted or 100% if secured
        rwa = ead * 1.0  # Conservative assumption
        risk_weight = 100
    else:
        risk_weight = base_rw
        rwa = ead * risk_weight / 100

    return {
        "approach": "Slotting",
        "ead": ead,
        "category": category.value,
        "exposure_type": exposure_type,
        "maturity": maturity,
        "risk_weight_pct": risk_weight,
        "rwa": rwa,
        "capital_requirement_k": risk_weight / 100 / 12.5,
    }


# =============================================================================
# Specialized Lending Sub-types
# =============================================================================

def calculate_project_finance_rwa(
    ead: float,
    phase: str = "operational",  # "pre_operational" or "operational"
    dscr: float = 1.3,
    ltv: float = 0.70,
    country_risk: str = "low",
    sponsor_rating: str = "strong"
) -> dict:
    """
    Calculate RWA for Project Finance using slotting.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    phase : str
        Project phase
    dscr : float
        Debt Service Coverage Ratio
    ltv : float
        Loan-to-Value ratio
    country_risk : str
        "low", "moderate", "high"
    sponsor_rating : str
        "strong", "good", "satisfactory", "weak"
    """
    # Score financial strength based on DSCR and LTV
    if dscr >= 1.5 and ltv <= 0.60:
        financial_score = 1
    elif dscr >= 1.25 and ltv <= 0.75:
        financial_score = 2
    elif dscr >= 1.0 and ltv <= 0.85:
        financial_score = 3
    else:
        financial_score = 4

    # Score country risk
    country_scores = {"low": 1, "moderate": 2, "high": 4}
    country_score = country_scores.get(country_risk, 3)

    # Score phase
    phase_score = 1 if phase == "operational" else 3

    # Score sponsor
    sponsor_scores = {"strong": 1, "good": 2, "satisfactory": 3, "weak": 4}
    sponsor_score = sponsor_scores.get(sponsor_rating, 3)

    # Security assumed average
    security_score = 2

    category = assess_slotting_category(
        financial_score, country_score, phase_score, sponsor_score, security_score
    )

    result = calculate_slotting_rwa(ead, category, "standard")
    result["sub_type"] = "project_finance"
    result["phase"] = phase
    result["dscr"] = dscr
    result["ltv"] = ltv

    return result


def calculate_object_finance_rwa(
    ead: float,
    asset_type: str = "aircraft",  # "aircraft", "ship", "rolling_stock"
    asset_age: int = 5,
    market_conditions: str = "stable",
    operator_quality: str = "good"
) -> dict:
    """
    Calculate RWA for Object Finance (ships, aircraft, etc.).

    Parameters:
    -----------
    ead : float
        Exposure at Default
    asset_type : str
        Type of asset
    asset_age : int
        Age of asset in years
    market_conditions : str
        "strong", "stable", "weak"
    operator_quality : str
        "strong", "good", "satisfactory", "weak"
    """
    # Score based on asset characteristics
    if asset_age <= 5:
        asset_score = 1
    elif asset_age <= 10:
        asset_score = 2
    elif asset_age <= 15:
        asset_score = 3
    else:
        asset_score = 4

    market_scores = {"strong": 1, "stable": 2, "weak": 4}
    market_score = market_scores.get(market_conditions, 2)

    operator_scores = {"strong": 1, "good": 2, "satisfactory": 3, "weak": 4}
    operator_score = operator_scores.get(operator_quality, 2)

    # Average scoring
    financial_score = 2  # Assumed
    security_score = 2   # Assumed

    category = assess_slotting_category(
        financial_score, market_score, asset_score, operator_score, security_score
    )

    result = calculate_slotting_rwa(ead, category, "standard")
    result["sub_type"] = "object_finance"
    result["asset_type"] = asset_type
    result["asset_age"] = asset_age

    return result


def calculate_ipre_rwa(
    ead: float,
    property_type: str = "office",
    occupancy_rate: float = 0.90,
    dscr: float = 1.4,
    ltv: float = 0.65,
    location_quality: str = "prime"
) -> dict:
    """
    Calculate RWA for Income-Producing Real Estate.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    property_type : str
        "office", "retail", "industrial", "multifamily"
    occupancy_rate : float
        Current occupancy rate
    dscr : float
        Debt Service Coverage Ratio
    ltv : float
        Loan-to-Value ratio
    location_quality : str
        "prime", "good", "secondary", "tertiary"
    """
    # Financial strength scoring
    if dscr >= 1.5 and ltv <= 0.60:
        financial_score = 1
    elif dscr >= 1.25 and ltv <= 0.70:
        financial_score = 2
    elif dscr >= 1.1 and ltv <= 0.80:
        financial_score = 3
    else:
        financial_score = 4

    # Location scoring
    location_scores = {"prime": 1, "good": 2, "secondary": 3, "tertiary": 4}
    location_score = location_scores.get(location_quality, 2)

    # Occupancy scoring
    if occupancy_rate >= 0.95:
        occupancy_score = 1
    elif occupancy_rate >= 0.85:
        occupancy_score = 2
    elif occupancy_rate >= 0.75:
        occupancy_score = 3
    else:
        occupancy_score = 4

    # Property type risk (multifamily generally lower risk)
    type_scores = {"multifamily": 1, "industrial": 2, "office": 2, "retail": 3}
    type_score = type_scores.get(property_type, 2)

    security_score = 2  # Real estate typically has good security

    category = assess_slotting_category(
        financial_score, location_score, type_score, occupancy_score, security_score
    )

    result = calculate_slotting_rwa(ead, category, "standard")
    result["sub_type"] = "ipre"
    result["property_type"] = property_type
    result["occupancy_rate"] = occupancy_rate
    result["dscr"] = dscr
    result["ltv"] = ltv

    return result


def calculate_hvcre_rwa(
    ead: float,
    property_type: str = "land_development",
    pre_sales_rate: float = 0.30,
    ltv: float = 0.75,
    sponsor_equity: float = 0.15
) -> dict:
    """
    Calculate RWA for High-Volatility Commercial Real Estate.

    HVCRE includes ADC (Acquisition, Development, Construction) loans.

    Parameters:
    -----------
    ead : float
        Exposure at Default
    property_type : str
        "land_development", "speculative_construction", "adc"
    pre_sales_rate : float
        Percentage of units pre-sold
    ltv : float
        Loan-to-Value ratio
    sponsor_equity : float
        Sponsor's equity contribution
    """
    # Higher risk for development/construction
    if pre_sales_rate >= 0.50 and sponsor_equity >= 0.20:
        phase_score = 2
    elif pre_sales_rate >= 0.30 and sponsor_equity >= 0.15:
        phase_score = 3
    else:
        phase_score = 4

    # Financial scoring
    if ltv <= 0.65 and sponsor_equity >= 0.25:
        financial_score = 2
    elif ltv <= 0.75 and sponsor_equity >= 0.15:
        financial_score = 3
    else:
        financial_score = 4

    # HVCRE generally scored more conservatively
    category = assess_slotting_category(
        financial_score, 2, phase_score, 2, 3
    )

    result = calculate_slotting_rwa(ead, category, "hvcre")
    result["sub_type"] = "hvcre"
    result["property_type"] = property_type
    result["pre_sales_rate"] = pre_sales_rate
    result["ltv"] = ltv

    return result


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Specialized Lending - Slotting Approach")
    print("=" * 70)

    # Project Finance example
    print("\n  Project Finance (Operational Power Plant):")
    pf_result = calculate_project_finance_rwa(
        ead=50_000_000,
        phase="operational",
        dscr=1.45,
        ltv=0.65,
        country_risk="low",
        sponsor_rating="good"
    )
    print(f"    Category: {pf_result['category']}")
    print(f"    Risk Weight: {pf_result['risk_weight_pct']}%")
    print(f"    RWA: ${pf_result['rwa']:,.0f}")

    # Object Finance example
    print("\n  Object Finance (Aircraft):")
    of_result = calculate_object_finance_rwa(
        ead=30_000_000,
        asset_type="aircraft",
        asset_age=3,
        market_conditions="stable",
        operator_quality="good"
    )
    print(f"    Category: {of_result['category']}")
    print(f"    Risk Weight: {of_result['risk_weight_pct']}%")
    print(f"    RWA: ${of_result['rwa']:,.0f}")

    # IPRE example
    print("\n  Income-Producing Real Estate (Office):")
    ipre_result = calculate_ipre_rwa(
        ead=25_000_000,
        property_type="office",
        occupancy_rate=0.92,
        dscr=1.35,
        ltv=0.68,
        location_quality="prime"
    )
    print(f"    Category: {ipre_result['category']}")
    print(f"    Risk Weight: {ipre_result['risk_weight_pct']}%")
    print(f"    RWA: ${ipre_result['rwa']:,.0f}")

    # HVCRE example
    print("\n  High-Volatility CRE (Development):")
    hvcre_result = calculate_hvcre_rwa(
        ead=20_000_000,
        property_type="speculative_construction",
        pre_sales_rate=0.25,
        ltv=0.70,
        sponsor_equity=0.20
    )
    print(f"    Category: {hvcre_result['category']}")
    print(f"    Risk Weight: {hvcre_result['risk_weight_pct']}%")
    print(f"    RWA: ${hvcre_result['rwa']:,.0f}")

    # Summary table
    print("\n" + "=" * 70)
    print("Slotting Risk Weight Summary")
    print("=" * 70)
    print(f"\n  {'Category':<15} {'Standard':>12} {'HVCRE':>12}")
    print(f"  {'-'*15} {'-'*12} {'-'*12}")
    for cat in SlottingCategory:
        if cat != SlottingCategory.DEFAULT:
            std_rw = SLOTTING_RISK_WEIGHTS["standard"][cat]
            hvcre_rw = SLOTTING_RISK_WEIGHTS["hvcre"][cat]
            print(f"  {cat.value:<15} {std_rw:>11}% {hvcre_rw:>11}%")
