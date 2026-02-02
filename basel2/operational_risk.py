"""
Basel II Operational Risk Capital Requirements

Implements the three Basel II approaches for operational risk:
1. Basic Indicator Approach (BIA): 15% of gross income
2. Standardised Approach (TSA): Different percentages by business line
3. Advanced Measurement Approach (AMA): Internal models

Key differences from Basel III:
- Basel III replaced all three with the Standardised Measurement Approach (SMA)
- Basel II AMA allowed internal models; Basel III removed this optionality
"""

from enum import Enum
from dataclasses import dataclass


# =============================================================================
# Business Line Classifications (Para 654)
# =============================================================================

class BusinessLine(Enum):
    """Basel II standardised business lines."""
    CORPORATE_FINANCE = "corporate_finance"
    TRADING_SALES = "trading_sales"
    RETAIL_BANKING = "retail_banking"
    COMMERCIAL_BANKING = "commercial_banking"
    PAYMENT_SETTLEMENT = "payment_settlement"
    AGENCY_SERVICES = "agency_services"
    ASSET_MANAGEMENT = "asset_management"
    RETAIL_BROKERAGE = "retail_brokerage"


# Beta factors for TSA (Para 654)
TSA_BETA_FACTORS = {
    BusinessLine.CORPORATE_FINANCE: 0.18,
    BusinessLine.TRADING_SALES: 0.18,
    BusinessLine.RETAIL_BANKING: 0.12,
    BusinessLine.COMMERCIAL_BANKING: 0.15,
    BusinessLine.PAYMENT_SETTLEMENT: 0.18,
    BusinessLine.AGENCY_SERVICES: 0.15,
    BusinessLine.ASSET_MANAGEMENT: 0.12,
    BusinessLine.RETAIL_BROKERAGE: 0.12,
}

# Alternative Standardised Approach (ASA) for retail/commercial (Para 656)
ASA_MULTIPLIER = 0.035  # 3.5% of loans and advances


# =============================================================================
# Basic Indicator Approach (BIA) - Para 649-651
# =============================================================================

def calculate_bia_capital(
    gross_income_year1: float,
    gross_income_year2: float,
    gross_income_year3: float,
    alpha: float = 0.15
) -> dict:
    """
    Calculate operational risk capital using Basic Indicator Approach.

    K_BIA = α × GI

    Where:
    - GI = average of gross income over previous 3 years (positive years only)
    - α = 15%

    Parameters:
    -----------
    gross_income_year1 : float
        Gross income year T-1
    gross_income_year2 : float
        Gross income year T-2
    gross_income_year3 : float
        Gross income year T-3
    alpha : float
        Alpha factor (default: 15%)

    Returns:
    --------
    dict
        BIA capital calculation results
    """
    # Only include positive gross income years
    positive_years = [gi for gi in [gross_income_year1, gross_income_year2, gross_income_year3]
                      if gi > 0]

    if not positive_years:
        avg_gross_income = 0
        n_years = 0
    else:
        avg_gross_income = sum(positive_years) / len(positive_years)
        n_years = len(positive_years)

    capital = alpha * avg_gross_income
    rwa = capital * 12.5

    return {
        "approach": "BIA",
        "gross_income": {
            "year1": gross_income_year1,
            "year2": gross_income_year2,
            "year3": gross_income_year3,
        },
        "positive_years_count": n_years,
        "average_gross_income": avg_gross_income,
        "alpha": alpha,
        "capital_requirement": capital,
        "rwa": rwa,
    }


# =============================================================================
# Standardised Approach (TSA) - Para 652-654
# =============================================================================

@dataclass
class BusinessLineIncome:
    """Gross income by business line for TSA."""
    business_line: BusinessLine
    gross_income_year1: float
    gross_income_year2: float
    gross_income_year3: float


def calculate_tsa_capital(
    business_line_incomes: list[BusinessLineIncome],
    use_asa: bool = False,
    retail_loans: float = None,
    commercial_loans: float = None
) -> dict:
    """
    Calculate operational risk capital using Standardised Approach.

    K_TSA = {Σ years 1-3 max[Σ(GI_j × β_j), 0]} / 3

    Parameters:
    -----------
    business_line_incomes : list of BusinessLineIncome
        Gross income by business line for each of 3 years
    use_asa : bool
        Use Alternative Standardised Approach for retail/commercial
    retail_loans : float
        Total retail loans (for ASA)
    commercial_loans : float
        Total commercial loans (for ASA)

    Returns:
    --------
    dict
        TSA capital calculation results
    """
    # Calculate weighted income by business line for each year
    yearly_capitals = []
    business_line_details = {}

    for year_idx in range(3):
        year_capital = 0

        for bl_income in business_line_incomes:
            bl = bl_income.business_line

            # Get gross income for this year
            if year_idx == 0:
                gi = bl_income.gross_income_year1
            elif year_idx == 1:
                gi = bl_income.gross_income_year2
            else:
                gi = bl_income.gross_income_year3

            # ASA treatment for retail/commercial banking
            if use_asa and bl in [BusinessLine.RETAIL_BANKING, BusinessLine.COMMERCIAL_BANKING]:
                if bl == BusinessLine.RETAIL_BANKING and retail_loans:
                    beta_gi = ASA_MULTIPLIER * retail_loans
                elif bl == BusinessLine.COMMERCIAL_BANKING and commercial_loans:
                    beta_gi = ASA_MULTIPLIER * commercial_loans
                else:
                    beta = TSA_BETA_FACTORS[bl]
                    beta_gi = beta * gi
            else:
                beta = TSA_BETA_FACTORS[bl]
                beta_gi = beta * gi

            year_capital += beta_gi

            # Track by business line
            if bl.value not in business_line_details:
                business_line_details[bl.value] = {
                    "beta": TSA_BETA_FACTORS[bl],
                    "years": [],
                    "total_contribution": 0,
                }
            business_line_details[bl.value]["years"].append({
                "gross_income": gi,
                "contribution": beta_gi,
            })
            business_line_details[bl.value]["total_contribution"] += beta_gi / 3

        # Floor at zero for each year
        yearly_capitals.append(max(year_capital, 0))

    # Average over 3 years
    capital = sum(yearly_capitals) / 3
    rwa = capital * 12.5

    return {
        "approach": "TSA" if not use_asa else "ASA",
        "yearly_capitals": {
            "year1": yearly_capitals[0],
            "year2": yearly_capitals[1],
            "year3": yearly_capitals[2],
        },
        "business_lines": business_line_details,
        "capital_requirement": capital,
        "rwa": rwa,
    }


# =============================================================================
# Advanced Measurement Approach (AMA) - Para 655-683
# =============================================================================

@dataclass
class AMAParameters:
    """Parameters for AMA calculation."""
    expected_loss: float
    unexpected_loss_999: float  # 99.9th percentile
    correlation_adjustment: float = 1.0
    insurance_mitigation: float = 0.0  # Max 20%
    diversification_benefit: float = 0.0


def calculate_ama_capital(
    ama_params: AMAParameters,
    business_environment_factor: float = 1.0,
    internal_control_factor: float = 1.0
) -> dict:
    """
    Calculate operational risk capital using Advanced Measurement Approach.

    AMA allows banks to use internal models based on:
    - Internal loss data
    - External loss data
    - Scenario analysis
    - Business environment and internal control factors (BEICFs)

    Parameters:
    -----------
    ama_params : AMAParameters
        Internal model parameters
    business_environment_factor : float
        BEICF adjustment (typically 0.8-1.2)
    internal_control_factor : float
        Internal control adjustment

    Returns:
    --------
    dict
        AMA capital calculation results
    """
    # Base UL from internal model
    base_capital = ama_params.unexpected_loss_999

    # Correlation adjustment (if bank uses multiple risk cells)
    adjusted_capital = base_capital * ama_params.correlation_adjustment

    # BEICF adjustments
    adjusted_capital *= business_environment_factor * internal_control_factor

    # Insurance mitigation (max 20% reduction)
    max_insurance = 0.20 * adjusted_capital
    insurance_benefit = min(ama_params.insurance_mitigation, max_insurance)
    final_capital = adjusted_capital - insurance_benefit

    # Diversification benefit
    final_capital *= (1 - ama_params.diversification_benefit)

    rwa = final_capital * 12.5

    return {
        "approach": "AMA",
        "expected_loss": ama_params.expected_loss,
        "unexpected_loss_999": ama_params.unexpected_loss_999,
        "base_capital": base_capital,
        "correlation_adjustment": ama_params.correlation_adjustment,
        "business_environment_factor": business_environment_factor,
        "internal_control_factor": internal_control_factor,
        "insurance_mitigation": insurance_benefit,
        "diversification_benefit": ama_params.diversification_benefit,
        "capital_requirement": final_capital,
        "rwa": rwa,
    }


# =============================================================================
# Comparison Functions
# =============================================================================

def compare_oprisk_approaches(
    gross_income_year1: float,
    gross_income_year2: float,
    gross_income_year3: float,
    business_line_incomes: list[BusinessLineIncome] = None,
    ama_params: AMAParameters = None
) -> dict:
    """
    Compare operational risk capital across all approaches.

    Parameters:
    -----------
    gross_income_year1, year2, year3 : float
        Total gross income for BIA
    business_line_incomes : list of BusinessLineIncome
        For TSA calculation
    ama_params : AMAParameters
        For AMA calculation

    Returns:
    --------
    dict
        Comparison results
    """
    results = {}

    # BIA
    bia_result = calculate_bia_capital(
        gross_income_year1, gross_income_year2, gross_income_year3
    )
    results["bia"] = bia_result

    # TSA (if business line data provided)
    if business_line_incomes:
        tsa_result = calculate_tsa_capital(business_line_incomes)
        results["tsa"] = tsa_result
    else:
        results["tsa"] = None

    # AMA (if parameters provided)
    if ama_params:
        ama_result = calculate_ama_capital(ama_params)
        results["ama"] = ama_result
    else:
        results["ama"] = None

    # Find most conservative
    capitals = [
        ("BIA", bia_result["capital_requirement"]),
    ]
    if results["tsa"]:
        capitals.append(("TSA", results["tsa"]["capital_requirement"]))
    if results["ama"]:
        capitals.append(("AMA", results["ama"]["capital_requirement"]))

    capitals_sorted = sorted(capitals, key=lambda x: x[1], reverse=True)

    return {
        "bia": results["bia"],
        "tsa": results["tsa"],
        "ama": results["ama"],
        "most_conservative": capitals_sorted[0][0],
        "least_conservative": capitals_sorted[-1][0],
        "ranking": [c[0] for c in capitals_sorted],
    }


# =============================================================================
# Gross Income Calculation Helper
# =============================================================================

def calculate_gross_income(
    net_interest_income: float,
    net_non_interest_income: float,
    exclude_items: dict = None
) -> float:
    """
    Calculate gross income for operational risk purposes.

    Gross Income = Net Interest Income + Net Non-Interest Income

    Excludes (Para 650):
    - Provisions
    - Operating expenses
    - Realized profits/losses from sale of securities in banking book
    - Extraordinary/irregular items
    - Income from insurance

    Parameters:
    -----------
    net_interest_income : float
        Net interest income
    net_non_interest_income : float
        Net non-interest income (fees, trading, etc.)
    exclude_items : dict
        Items to exclude (insurance_income, irregular_items, etc.)

    Returns:
    --------
    float
        Gross income for BIA/TSA
    """
    gross_income = net_interest_income + net_non_interest_income

    if exclude_items:
        for item, value in exclude_items.items():
            gross_income -= value

    return gross_income


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Operational Risk")
    print("=" * 70)

    # BIA Example
    print("\n  Basic Indicator Approach (BIA):")
    bia = calculate_bia_capital(
        gross_income_year1=500_000_000,
        gross_income_year2=550_000_000,
        gross_income_year3=480_000_000
    )
    print(f"  Average Gross Income: ${bia['average_gross_income']:,.0f}")
    print(f"  Alpha: {bia['alpha']*100:.0f}%")
    print(f"  Capital Requirement: ${bia['capital_requirement']:,.0f}")
    print(f"  RWA: ${bia['rwa']:,.0f}")

    # TSA Example
    print("\n  Standardised Approach (TSA):")
    bl_incomes = [
        BusinessLineIncome(BusinessLine.RETAIL_BANKING, 150_000_000, 160_000_000, 140_000_000),
        BusinessLineIncome(BusinessLine.COMMERCIAL_BANKING, 200_000_000, 210_000_000, 190_000_000),
        BusinessLineIncome(BusinessLine.TRADING_SALES, 80_000_000, 100_000_000, 70_000_000),
        BusinessLineIncome(BusinessLine.ASSET_MANAGEMENT, 50_000_000, 55_000_000, 52_000_000),
        BusinessLineIncome(BusinessLine.PAYMENT_SETTLEMENT, 20_000_000, 25_000_000, 23_000_000),
    ]
    tsa = calculate_tsa_capital(bl_incomes)
    print(f"  Capital Requirement: ${tsa['capital_requirement']:,.0f}")
    print(f"  RWA: ${tsa['rwa']:,.0f}")

    # AMA Example
    print("\n  Advanced Measurement Approach (AMA):")
    ama_params = AMAParameters(
        expected_loss=20_000_000,
        unexpected_loss_999=80_000_000,
        correlation_adjustment=0.95,
        insurance_mitigation=10_000_000,
        diversification_benefit=0.10
    )
    ama = calculate_ama_capital(ama_params)
    print(f"  Expected Loss: ${ama['expected_loss']:,.0f}")
    print(f"  UL (99.9%): ${ama['unexpected_loss_999']:,.0f}")
    print(f"  Insurance Benefit: ${ama['insurance_mitigation']:,.0f}")
    print(f"  Capital Requirement: ${ama['capital_requirement']:,.0f}")
    print(f"  RWA: ${ama['rwa']:,.0f}")

    # Comparison
    print("\n" + "=" * 70)
    print("Approach Comparison")
    print("=" * 70)

    comparison = compare_oprisk_approaches(
        gross_income_year1=500_000_000,
        gross_income_year2=550_000_000,
        gross_income_year3=480_000_000,
        business_line_incomes=bl_incomes,
        ama_params=ama_params
    )

    print(f"\n  {'Approach':<10} {'Capital':>15} {'RWA':>18}")
    print(f"  {'-'*10} {'-'*15} {'-'*18}")
    print(f"  {'BIA':<10} ${comparison['bia']['capital_requirement']:>13,.0f} ${comparison['bia']['rwa']:>16,.0f}")
    print(f"  {'TSA':<10} ${comparison['tsa']['capital_requirement']:>13,.0f} ${comparison['tsa']['rwa']:>16,.0f}")
    print(f"  {'AMA':<10} ${comparison['ama']['capital_requirement']:>13,.0f} ${comparison['ama']['rwa']:>16,.0f}")
    print(f"\n  Most conservative: {comparison['most_conservative']}")
    print(f"  Least conservative: {comparison['least_conservative']}")
