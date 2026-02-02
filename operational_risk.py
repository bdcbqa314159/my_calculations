"""
Operational Risk - Standardised Measurement Approach (SMA)

Implements:
- SMA: Basel III final standardised approach for operational risk
- BIC: Business Indicator Component
- ILM: Internal Loss Multiplier
"""

import math
from typing import Optional


# =============================================================================
# SMA (Standardised Measurement Approach) - OPE25
# =============================================================================

# Business Indicator Component (BIC) marginal coefficients (OPE25.12)
BIC_COEFFICIENTS = {
    # (lower_bound, upper_bound, marginal_coefficient)
    "bucket_1": (0, 1_000_000_000, 0.12),           # BI <= 1bn: 12%
    "bucket_2": (1_000_000_000, 30_000_000_000, 0.15),  # 1bn < BI <= 30bn: 15%
    "bucket_3": (30_000_000_000, float('inf'), 0.18),   # BI > 30bn: 18%
}

# ILM scaling coefficient
ILM_COEFFICIENT = 0.8

# Loss component calculation parameters
LOSS_COMPONENT_YEARS = 10  # Average over 10 years


def calculate_interest_leasing_dividend_component(
    interest_income: float,
    interest_expense: float,
    interest_earning_assets: float,
    leasing_income: float,
    leasing_expense: float,
    dividend_income: float
) -> float:
    """
    Calculate Interest, Leasing and Dividend Component (ILDC).

    ILDC = min(|Interest Income - Interest Expense|, 2.25% * IEA)
           + Dividend Income

    Parameters:
    -----------
    interest_income : float
        Gross interest income
    interest_expense : float
        Gross interest expense
    interest_earning_assets : float
        Average interest-earning assets
    leasing_income : float
        Gross leasing income
    leasing_expense : float
        Gross leasing expense
    dividend_income : float
        Dividend income

    Returns:
    --------
    float
        ILDC value
    """
    # Net interest component with cap
    net_interest = abs(interest_income - interest_expense)
    interest_cap = 0.0225 * interest_earning_assets
    interest_component = min(net_interest, interest_cap)

    # Net leasing
    net_leasing = abs(leasing_income - leasing_expense)

    # Total ILDC
    ildc = interest_component + net_leasing + dividend_income

    return ildc


def calculate_services_component(
    fee_income: float,
    fee_expense: float,
    other_operating_income: float,
    other_operating_expense: float
) -> float:
    """
    Calculate Services Component (SC).

    SC = max(Fee Income, Fee Expense)
         + max(Other Operating Income, Other Operating Expense)
    """
    fee_component = max(fee_income, fee_expense)
    other_component = max(other_operating_income, other_operating_expense)

    return fee_component + other_component


def calculate_financial_component(
    trading_book_pnl: float,
    banking_book_pnl: float
) -> float:
    """
    Calculate Financial Component (FC).

    FC = |Net P&L Trading Book| + |Net P&L Banking Book|
    """
    return abs(trading_book_pnl) + abs(banking_book_pnl)


def calculate_business_indicator(
    ildc: float,
    sc: float,
    fc: float
) -> float:
    """
    Calculate Business Indicator (BI).

    BI = ILDC + SC + FC

    All components should be averaged over 3 years.
    """
    return ildc + sc + fc


def calculate_bic(bi: float) -> float:
    """
    Calculate Business Indicator Component (BIC).

    BIC uses a piecewise linear function with marginal coefficients.

    For BI <= 1bn:         BIC = 12% * BI
    For 1bn < BI <= 30bn:  BIC = 120m + 15% * (BI - 1bn)
    For BI > 30bn:         BIC = 120m + 4.35bn + 18% * (BI - 30bn)
    """
    if bi <= 1_000_000_000:
        bic = BIC_COEFFICIENTS["bucket_1"][2] * bi
    elif bi <= 30_000_000_000:
        bic_bucket1 = BIC_COEFFICIENTS["bucket_1"][2] * 1_000_000_000
        bic_bucket2 = BIC_COEFFICIENTS["bucket_2"][2] * (bi - 1_000_000_000)
        bic = bic_bucket1 + bic_bucket2
    else:
        bic_bucket1 = BIC_COEFFICIENTS["bucket_1"][2] * 1_000_000_000
        bic_bucket2 = BIC_COEFFICIENTS["bucket_2"][2] * (30_000_000_000 - 1_000_000_000)
        bic_bucket3 = BIC_COEFFICIENTS["bucket_3"][2] * (bi - 30_000_000_000)
        bic = bic_bucket1 + bic_bucket2 + bic_bucket3

    return bic


def calculate_loss_component(
    average_annual_loss: float,
    years: int = 10
) -> float:
    """
    Calculate Loss Component (LC).

    LC = 15 * Average Annual Operational Loss

    The average should be over 10 years, excluding the two highest loss years
    if there are outliers.
    """
    lc = 15 * average_annual_loss
    return lc


def calculate_ilm(
    bic: float,
    lc: float,
    use_ilm: bool = True
) -> float:
    """
    Calculate Internal Loss Multiplier (ILM).

    ILM = ln(exp(1) - 1 + (LC/BIC)^0.8)

    If bank does not use ILM (e.g., bucket 1 banks), ILM = 1.
    """
    if not use_ilm or bic <= 0:
        return 1.0

    ratio = lc / bic if bic > 0 else 0

    # ILM formula
    ilm = math.log(math.exp(1) - 1 + ratio ** ILM_COEFFICIENT)

    # Floor at 0 (though mathematically should always be positive)
    return max(ilm, 0)


def calculate_sma_capital(
    bi: float = None,
    average_annual_loss: float = 0,
    use_ilm: bool = True,
    # Or provide components directly
    ildc: float = None,
    sc: float = None,
    fc: float = None,
    # Or provide detailed inputs
    interest_income: float = 0,
    interest_expense: float = 0,
    interest_earning_assets: float = 0,
    leasing_income: float = 0,
    leasing_expense: float = 0,
    dividend_income: float = 0,
    fee_income: float = 0,
    fee_expense: float = 0,
    other_operating_income: float = 0,
    other_operating_expense: float = 0,
    trading_book_pnl: float = 0,
    banking_book_pnl: float = 0
) -> dict:
    """
    Calculate SMA Operational Risk Capital.

    K_SMA = BIC * ILM

    Parameters:
    -----------
    bi : float
        Pre-calculated Business Indicator (3-year average)
    average_annual_loss : float
        Average annual operational loss (10-year)
    use_ilm : bool
        Whether to use Internal Loss Multiplier
    ildc, sc, fc : float
        Pre-calculated BI components
    Or provide detailed P&L inputs

    Returns:
    --------
    dict
        SMA calculation results
    """
    # Calculate BI if not provided
    if bi is None:
        if ildc is not None and sc is not None and fc is not None:
            bi = calculate_business_indicator(ildc, sc, fc)
        else:
            # Calculate from detailed inputs
            ildc = calculate_interest_leasing_dividend_component(
                interest_income, interest_expense, interest_earning_assets,
                leasing_income, leasing_expense, dividend_income
            )
            sc = calculate_services_component(
                fee_income, fee_expense,
                other_operating_income, other_operating_expense
            )
            fc = calculate_financial_component(trading_book_pnl, banking_book_pnl)
            bi = calculate_business_indicator(ildc, sc, fc)

    # Calculate BIC
    bic = calculate_bic(bi)

    # Calculate LC
    lc = calculate_loss_component(average_annual_loss)

    # Calculate ILM
    ilm = calculate_ilm(bic, lc, use_ilm)

    # Calculate SMA capital
    k_sma = bic * ilm

    # RWA = K * 12.5
    rwa = k_sma * 12.5

    # Determine bucket
    if bi <= 1_000_000_000:
        bucket = 1
    elif bi <= 30_000_000_000:
        bucket = 2
    else:
        bucket = 3

    return {
        "approach": "SMA",
        "business_indicator": bi,
        "bic": bic,
        "loss_component": lc,
        "ilm": ilm,
        "use_ilm": use_ilm,
        "bucket": bucket,
        "k_sma": k_sma,
        "rwa": rwa,
        "components": {
            "ildc": ildc if ildc is not None else 0,
            "sc": sc if sc is not None else 0,
            "fc": fc if fc is not None else 0,
        }
    }


def calculate_sma_simplified(
    total_revenue: float,
    average_annual_loss: float = 0,
    use_ilm: bool = True
) -> dict:
    """
    Simplified SMA calculation using total revenue as BI proxy.

    This is a rough approximation when detailed P&L is not available.

    Parameters:
    -----------
    total_revenue : float
        Total operating revenue (as BI approximation)
    average_annual_loss : float
        Average annual operational loss
    use_ilm : bool
        Whether to use ILM

    Returns:
    --------
    dict
        SMA calculation results
    """
    # Use revenue as BI approximation (typically BI ≈ 70-90% of revenue)
    bi_estimate = total_revenue * 0.80

    return calculate_sma_capital(
        bi=bi_estimate,
        average_annual_loss=average_annual_loss,
        use_ilm=use_ilm
    )


# Legacy approaches for reference/comparison
def calculate_bia(gross_income: float) -> dict:
    """
    Calculate Basic Indicator Approach (BIA) - for reference only.

    BIA was replaced by SMA in Basel III final.

    K_BIA = 15% * GI (average over 3 years)
    """
    alpha = 0.15
    k_bia = alpha * gross_income

    return {
        "approach": "BIA (legacy)",
        "gross_income": gross_income,
        "alpha": alpha,
        "k_bia": k_bia,
        "rwa": k_bia * 12.5,
    }


def calculate_tsa(
    business_line_income: dict
) -> dict:
    """
    Calculate Standardised Approach / TSA (legacy) - for reference only.

    TSA was replaced by SMA in Basel III final.

    Beta factors by business line:
    - Corporate finance: 18%
    - Trading & sales: 18%
    - Retail banking: 12%
    - Commercial banking: 15%
    - Payment & settlement: 18%
    - Agency services: 15%
    - Asset management: 12%
    - Retail brokerage: 12%
    """
    beta_factors = {
        "corporate_finance": 0.18,
        "trading_sales": 0.18,
        "retail_banking": 0.12,
        "commercial_banking": 0.15,
        "payment_settlement": 0.18,
        "agency_services": 0.15,
        "asset_management": 0.12,
        "retail_brokerage": 0.12,
    }

    k_tsa = 0
    breakdown = {}

    for bl, income in business_line_income.items():
        beta = beta_factors.get(bl, 0.15)
        k_bl = beta * income
        breakdown[bl] = {"income": income, "beta": beta, "capital": k_bl}
        k_tsa += k_bl

    return {
        "approach": "TSA (legacy)",
        "k_tsa": k_tsa,
        "rwa": k_tsa * 12.5,
        "breakdown": breakdown,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("SMA - Standardised Measurement Approach")
    print("=" * 70)

    # Example bank data
    bi_components = {
        "ildc": 500_000_000,    # Interest, Leasing, Dividend Component
        "sc": 300_000_000,      # Services Component
        "fc": 200_000_000,      # Financial Component
    }

    bi = sum(bi_components.values())  # 1 billion

    result = calculate_sma_capital(
        bi=bi,
        average_annual_loss=50_000_000,  # 50m average annual loss
        use_ilm=True
    )

    print(f"\n  Business Indicator:      ${result['business_indicator']/1e9:.2f}bn")
    print(f"  Bucket:                  {result['bucket']}")
    print(f"  BIC:                     ${result['bic']/1e6:,.0f}m")
    print(f"  Loss Component:          ${result['loss_component']/1e6:,.0f}m")
    print(f"  ILM:                     {result['ilm']:.3f}")
    print(f"  K_SMA:                   ${result['k_sma']/1e6:,.0f}m")
    print(f"  Op Risk RWA:             ${result['rwa']/1e9:.2f}bn")

    # Larger bank example (bucket 3)
    print("\n" + "-" * 40)
    print("Larger Bank Example (Bucket 3)")
    print("-" * 40)

    result_large = calculate_sma_capital(
        bi=50_000_000_000,  # 50bn BI
        average_annual_loss=500_000_000,  # 500m average loss
        use_ilm=True
    )

    print(f"\n  Business Indicator:      ${result_large['business_indicator']/1e9:.1f}bn")
    print(f"  Bucket:                  {result_large['bucket']}")
    print(f"  BIC:                     ${result_large['bic']/1e9:.2f}bn")
    print(f"  Loss Component:          ${result_large['loss_component']/1e9:.2f}bn")
    print(f"  ILM:                     {result_large['ilm']:.3f}")
    print(f"  K_SMA:                   ${result_large['k_sma']/1e9:.2f}bn")
    print(f"  Op Risk RWA:             ${result_large['rwa']/1e9:.1f}bn")

    # Comparison with legacy approaches
    print("\n" + "=" * 70)
    print("Comparison with Legacy Approaches")
    print("=" * 70)

    gross_income = 800_000_000  # 800m

    bia_result = calculate_bia(gross_income)
    print(f"\n  BIA Capital:             ${bia_result['k_bia']/1e6:,.0f}m")

    tsa_income = {
        "corporate_finance": 100_000_000,
        "trading_sales": 150_000_000,
        "retail_banking": 200_000_000,
        "commercial_banking": 250_000_000,
        "payment_settlement": 50_000_000,
        "asset_management": 50_000_000,
    }

    tsa_result = calculate_tsa(tsa_income)
    print(f"  TSA Capital:             ${tsa_result['k_tsa']/1e6:,.0f}m")
    print(f"  SMA Capital:             ${result['k_sma']/1e6:,.0f}m")
