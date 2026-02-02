"""
Liquidity Requirements - LCR and NSFR

Implements:
- LCR: Liquidity Coverage Ratio
- NSFR: Net Stable Funding Ratio

Reference: LCR (LIQ30), NSFR (LIQ40)
"""

from typing import Optional


# =============================================================================
# LCR - Liquidity Coverage Ratio (LIQ30)
# =============================================================================

# HQLA haircuts by asset type (LIQ30.35-48)
HQLA_HAIRCUTS = {
    # Level 1 assets (no haircut, no cap)
    "L1_cash": 0.0,
    "L1_central_bank_reserves": 0.0,
    "L1_sovereign_0pct": 0.0,  # 0% risk-weighted sovereigns

    # Level 2A assets (15% haircut, max 40% of HQLA)
    "L2A_sovereign_20pct": 0.15,
    "L2A_covered_bonds_AA": 0.15,
    "L2A_corporate_bonds_AA": 0.15,

    # Level 2B assets (various haircuts, max 15% of HQLA)
    "L2B_rmbs_AA": 0.25,
    "L2B_corporate_bonds_A_BBB": 0.50,
    "L2B_equity_major_index": 0.50,
}

# Cash outflow rates (LIQ30.52-76)
CASH_OUTFLOW_RATES = {
    # Retail deposits
    "retail_stable": 0.03,       # 3% - stable deposits (insured, established relationship)
    "retail_less_stable": 0.10,  # 10% - less stable
    "retail_high_runoff": 0.20,  # 20% - high run-off

    # Wholesale deposits
    "wholesale_operational": 0.25,  # 25% - operational deposits
    "wholesale_non_operational_insured": 0.40,  # 40%
    "wholesale_non_operational_uninsured": 1.00,  # 100%
    "wholesale_financial_institution": 1.00,  # 100%

    # Secured funding
    "secured_L1": 0.0,           # 0% - backed by Level 1
    "secured_L2A": 0.15,         # 15% - backed by Level 2A
    "secured_L2B": 0.25,         # 25% - backed by Level 2B
    "secured_other": 1.00,       # 100% - other collateral

    # Commitments
    "committed_credit_retail": 0.05,  # 5%
    "committed_credit_corporate": 0.10,  # 10% (non-financial)
    "committed_credit_financial": 1.00,  # 100%
    "committed_liquidity_facility": 1.00,  # 100%

    # Other
    "derivative_outflows": 1.00,
    "other_contingent": 1.00,
}

# Cash inflow rates (LIQ30.77-90)
CASH_INFLOW_RATES = {
    "retail_loans": 0.50,          # 50% of contractual
    "wholesale_non_financial": 0.50,
    "wholesale_financial": 1.00,
    "secured_L1": 0.0,
    "secured_L2A": 0.15,
    "secured_L2B": 0.25,
    "secured_other": 1.00,
}


def calculate_hqla(assets: list[dict]) -> dict:
    """
    Calculate High-Quality Liquid Assets (HQLA) stock.

    Parameters:
    -----------
    assets : list of dict
        Each should have: amount, asset_type (from HQLA_HAIRCUTS keys)

    Returns:
    --------
    dict
        HQLA calculation by level
    """
    level1 = 0
    level2a = 0
    level2b = 0

    asset_details = []

    for asset in assets:
        amount = asset.get("amount", 0)
        asset_type = asset.get("asset_type", "")
        haircut = HQLA_HAIRCUTS.get(asset_type, 0.50)

        adjusted_amount = amount * (1 - haircut)

        if asset_type.startswith("L1"):
            level1 += adjusted_amount
            level = "L1"
        elif asset_type.startswith("L2A"):
            level2a += adjusted_amount
            level = "L2A"
        else:
            level2b += adjusted_amount
            level = "L2B"

        asset_details.append({
            "asset_type": asset_type,
            "amount": amount,
            "haircut": haircut,
            "adjusted_amount": adjusted_amount,
            "level": level,
        })

    # Apply caps
    # Level 2 cap: max 40% of total HQLA
    # Level 2B cap: max 15% of total HQLA
    total_unadjusted = level1 + level2a + level2b

    # Calculate adjusted Level 2
    max_level2 = level1 * (40 / 60)  # L2 can be max 40/60 of L1
    max_level2b = level1 * (15 / 85)  # L2B can be max 15/85 of L1

    level2b_adjusted = min(level2b, max_level2b)
    level2a_adjusted = min(level2a, max_level2 - level2b_adjusted)

    total_hqla = level1 + level2a_adjusted + level2b_adjusted

    return {
        "level1": level1,
        "level2a_gross": level2a,
        "level2a_adjusted": level2a_adjusted,
        "level2b_gross": level2b,
        "level2b_adjusted": level2b_adjusted,
        "total_hqla": total_hqla,
        "assets": asset_details,
    }


def calculate_cash_outflows(liabilities: list[dict]) -> dict:
    """
    Calculate total expected cash outflows over 30 days.

    Parameters:
    -----------
    liabilities : list of dict
        Each should have: amount, liability_type (from CASH_OUTFLOW_RATES keys)

    Returns:
    --------
    dict
        Outflow calculations
    """
    total_outflows = 0
    outflow_details = []

    for liability in liabilities:
        amount = liability.get("amount", 0)
        liability_type = liability.get("liability_type", "")
        rate = CASH_OUTFLOW_RATES.get(liability_type, 1.0)

        outflow = amount * rate

        outflow_details.append({
            "liability_type": liability_type,
            "amount": amount,
            "outflow_rate": rate,
            "outflow": outflow,
        })

        total_outflows += outflow

    return {
        "total_outflows": total_outflows,
        "details": outflow_details,
    }


def calculate_cash_inflows(receivables: list[dict], cap_rate: float = 0.75) -> dict:
    """
    Calculate total expected cash inflows over 30 days.

    Inflows are capped at 75% of outflows.

    Parameters:
    -----------
    receivables : list of dict
        Each should have: amount, receivable_type
    cap_rate : float
        Maximum inflow as % of outflows (default 75%)

    Returns:
    --------
    dict
        Inflow calculations
    """
    total_inflows = 0
    inflow_details = []

    for receivable in receivables:
        amount = receivable.get("amount", 0)
        receivable_type = receivable.get("receivable_type", "")
        rate = CASH_INFLOW_RATES.get(receivable_type, 0.50)

        inflow = amount * rate

        inflow_details.append({
            "receivable_type": receivable_type,
            "amount": amount,
            "inflow_rate": rate,
            "inflow": inflow,
        })

        total_inflows += inflow

    return {
        "total_inflows_gross": total_inflows,
        "cap_rate": cap_rate,
        "details": inflow_details,
    }


def calculate_lcr(
    hqla_assets: list[dict],
    liabilities: list[dict],
    receivables: list[dict],
    inflow_cap_rate: float = 0.75
) -> dict:
    """
    Calculate Liquidity Coverage Ratio.

    LCR = HQLA / (Total Outflows - min(Total Inflows, 75% * Outflows))

    Minimum requirement: 100%

    Parameters:
    -----------
    hqla_assets : list of dict
        High-quality liquid assets
    liabilities : list of dict
        Liabilities and commitments for outflow calculation
    receivables : list of dict
        Receivables for inflow calculation
    inflow_cap_rate : float
        Cap on inflows as % of outflows

    Returns:
    --------
    dict
        LCR calculation results
    """
    # Calculate components
    hqla = calculate_hqla(hqla_assets)
    outflows = calculate_cash_outflows(liabilities)
    inflows = calculate_cash_inflows(receivables, inflow_cap_rate)

    # Apply inflow cap
    inflow_cap = outflows["total_outflows"] * inflow_cap_rate
    capped_inflows = min(inflows["total_inflows_gross"], inflow_cap)

    # Net cash outflows
    net_outflows = outflows["total_outflows"] - capped_inflows

    # LCR
    lcr = hqla["total_hqla"] / net_outflows if net_outflows > 0 else float('inf')

    # Check compliance
    is_compliant = lcr >= 1.0

    return {
        "hqla": hqla["total_hqla"],
        "hqla_breakdown": hqla,
        "gross_outflows": outflows["total_outflows"],
        "gross_inflows": inflows["total_inflows_gross"],
        "capped_inflows": capped_inflows,
        "net_outflows": net_outflows,
        "lcr": lcr,
        "lcr_pct": lcr * 100,
        "minimum_requirement": 100,
        "is_compliant": is_compliant,
        "surplus_deficit": hqla["total_hqla"] - net_outflows,
    }


# =============================================================================
# NSFR - Net Stable Funding Ratio (LIQ40)
# =============================================================================

# Available Stable Funding (ASF) factors (LIQ40.14-31)
ASF_FACTORS = {
    # Capital and long-term debt
    "tier1_capital": 1.00,
    "tier2_capital": 1.00,
    "other_capital": 1.00,
    "long_term_debt_1y": 1.00,

    # Deposits
    "retail_stable_deposits": 0.95,
    "retail_less_stable_deposits": 0.90,
    "wholesale_operational": 0.50,
    "wholesale_non_operational_1y": 1.00,
    "wholesale_non_operational_6m_1y": 0.50,
    "wholesale_non_operational_lt_6m": 0.0,

    # Other
    "all_other_liabilities_1y": 1.00,
    "all_other_liabilities_lt_1y": 0.0,
}

# Required Stable Funding (RSF) factors (LIQ40.32-74)
RSF_FACTORS = {
    # HQLA
    "L1_assets": 0.0,
    "L2A_assets": 0.15,
    "L2B_assets": 0.50,

    # Loans
    "loans_to_financials_lt_6m": 0.10,
    "loans_to_financials_6m_1y": 0.50,
    "loans_to_financials_gt_1y": 1.00,
    "loans_to_non_financials_lt_1y": 0.50,
    "loans_to_non_financials_gt_1y_lt_35rw": 0.65,
    "loans_to_non_financials_gt_1y_ge_35rw": 0.85,
    "mortgages_gt_1y_lt_35rw": 0.65,
    "mortgages_gt_1y_ge_35rw": 0.85,

    # Other assets
    "unencumbered_equity": 0.85,
    "physical_commodities": 0.85,
    "other_assets": 1.00,
    "off_balance_sheet": 0.05,  # Default 5%
}


def calculate_asf(funding_sources: list[dict]) -> dict:
    """
    Calculate Available Stable Funding.

    Parameters:
    -----------
    funding_sources : list of dict
        Each should have: amount, funding_type (from ASF_FACTORS keys)

    Returns:
    --------
    dict
        ASF calculation
    """
    total_asf = 0
    asf_details = []

    for source in funding_sources:
        amount = source.get("amount", 0)
        funding_type = source.get("funding_type", "")
        factor = ASF_FACTORS.get(funding_type, 0.0)

        weighted_amount = amount * factor

        asf_details.append({
            "funding_type": funding_type,
            "amount": amount,
            "asf_factor": factor,
            "weighted_amount": weighted_amount,
        })

        total_asf += weighted_amount

    return {
        "total_asf": total_asf,
        "details": asf_details,
    }


def calculate_rsf(assets: list[dict], off_balance_sheet: float = 0) -> dict:
    """
    Calculate Required Stable Funding.

    Parameters:
    -----------
    assets : list of dict
        Each should have: amount, asset_type (from RSF_FACTORS keys)
    off_balance_sheet : float
        Off-balance sheet exposures

    Returns:
    --------
    dict
        RSF calculation
    """
    total_rsf = 0
    rsf_details = []

    for asset in assets:
        amount = asset.get("amount", 0)
        asset_type = asset.get("asset_type", "")
        factor = RSF_FACTORS.get(asset_type, 1.0)

        weighted_amount = amount * factor

        rsf_details.append({
            "asset_type": asset_type,
            "amount": amount,
            "rsf_factor": factor,
            "weighted_amount": weighted_amount,
        })

        total_rsf += weighted_amount

    # Add off-balance sheet
    obs_rsf = off_balance_sheet * RSF_FACTORS["off_balance_sheet"]
    total_rsf += obs_rsf

    rsf_details.append({
        "asset_type": "off_balance_sheet",
        "amount": off_balance_sheet,
        "rsf_factor": RSF_FACTORS["off_balance_sheet"],
        "weighted_amount": obs_rsf,
    })

    return {
        "total_rsf": total_rsf,
        "details": rsf_details,
    }


def calculate_nsfr(
    funding_sources: list[dict],
    assets: list[dict],
    off_balance_sheet: float = 0
) -> dict:
    """
    Calculate Net Stable Funding Ratio.

    NSFR = ASF / RSF

    Minimum requirement: 100%

    Parameters:
    -----------
    funding_sources : list of dict
        Liabilities and capital for ASF
    assets : list of dict
        Assets for RSF
    off_balance_sheet : float
        Off-balance sheet exposures

    Returns:
    --------
    dict
        NSFR calculation results
    """
    asf = calculate_asf(funding_sources)
    rsf = calculate_rsf(assets, off_balance_sheet)

    nsfr = asf["total_asf"] / rsf["total_rsf"] if rsf["total_rsf"] > 0 else float('inf')

    is_compliant = nsfr >= 1.0

    return {
        "asf": asf["total_asf"],
        "asf_breakdown": asf,
        "rsf": rsf["total_rsf"],
        "rsf_breakdown": rsf,
        "nsfr": nsfr,
        "nsfr_pct": nsfr * 100,
        "minimum_requirement": 100,
        "is_compliant": is_compliant,
        "surplus_deficit": asf["total_asf"] - rsf["total_rsf"],
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("LCR - Liquidity Coverage Ratio")
    print("=" * 70)

    # HQLA
    hqla_assets = [
        {"amount": 100_000_000, "asset_type": "L1_cash"},
        {"amount": 200_000_000, "asset_type": "L1_sovereign_0pct"},
        {"amount": 50_000_000, "asset_type": "L2A_corporate_bonds_AA"},
        {"amount": 20_000_000, "asset_type": "L2B_equity_major_index"},
    ]

    # Outflows
    liabilities = [
        {"amount": 300_000_000, "liability_type": "retail_stable"},
        {"amount": 100_000_000, "liability_type": "retail_less_stable"},
        {"amount": 200_000_000, "liability_type": "wholesale_operational"},
        {"amount": 50_000_000, "liability_type": "committed_credit_corporate"},
    ]

    # Inflows
    receivables = [
        {"amount": 100_000_000, "receivable_type": "wholesale_non_financial"},
        {"amount": 50_000_000, "receivable_type": "retail_loans"},
    ]

    lcr_result = calculate_lcr(hqla_assets, liabilities, receivables)

    print(f"\n  HQLA:                    ${lcr_result['hqla']:,.0f}")
    print(f"    Level 1:               ${lcr_result['hqla_breakdown']['level1']:,.0f}")
    print(f"    Level 2A:              ${lcr_result['hqla_breakdown']['level2a_adjusted']:,.0f}")
    print(f"    Level 2B:              ${lcr_result['hqla_breakdown']['level2b_adjusted']:,.0f}")
    print(f"  Gross Outflows:          ${lcr_result['gross_outflows']:,.0f}")
    print(f"  Capped Inflows:          ${lcr_result['capped_inflows']:,.0f}")
    print(f"  Net Outflows:            ${lcr_result['net_outflows']:,.0f}")
    print(f"  LCR:                     {lcr_result['lcr_pct']:.1f}%")
    print(f"  Compliant (>=100%):      {lcr_result['is_compliant']}")

    print("\n" + "=" * 70)
    print("NSFR - Net Stable Funding Ratio")
    print("=" * 70)

    # Funding sources
    funding = [
        {"amount": 50_000_000, "funding_type": "tier1_capital"},
        {"amount": 20_000_000, "funding_type": "tier2_capital"},
        {"amount": 100_000_000, "funding_type": "long_term_debt_1y"},
        {"amount": 200_000_000, "funding_type": "retail_stable_deposits"},
        {"amount": 150_000_000, "funding_type": "retail_less_stable_deposits"},
        {"amount": 100_000_000, "funding_type": "wholesale_operational"},
    ]

    # Assets
    assets = [
        {"amount": 100_000_000, "asset_type": "L1_assets"},
        {"amount": 50_000_000, "asset_type": "L2A_assets"},
        {"amount": 150_000_000, "asset_type": "loans_to_non_financials_lt_1y"},
        {"amount": 200_000_000, "asset_type": "mortgages_gt_1y_lt_35rw"},
        {"amount": 50_000_000, "asset_type": "unencumbered_equity"},
    ]

    nsfr_result = calculate_nsfr(funding, assets, off_balance_sheet=100_000_000)

    print(f"\n  Available Stable Funding: ${nsfr_result['asf']:,.0f}")
    print(f"  Required Stable Funding:  ${nsfr_result['rsf']:,.0f}")
    print(f"  NSFR:                     {nsfr_result['nsfr_pct']:.1f}%")
    print(f"  Compliant (>=100%):       {nsfr_result['is_compliant']}")
    print(f"  Surplus/Deficit:          ${nsfr_result['surplus_deficit']:,.0f}")
