"""
Capital Framework Components

Implements:
- Output Floor (72.5% of standardised)
- Leverage Ratio
- Large Exposures Framework
- Credit Risk Mitigation (CRM)
- Credit Conversion Factors (CCF)
"""

import math
from typing import Optional


# =============================================================================
# Output Floor - CAP30
# =============================================================================

OUTPUT_FLOOR_PERCENTAGE = 0.725  # 72.5%

# Transitional arrangements (CAP30.4)
OUTPUT_FLOOR_TRANSITION = {
    2023: 0.50,
    2024: 0.55,
    2025: 0.60,
    2026: 0.65,
    2027: 0.70,
    2028: 0.725,  # Full implementation
}


def calculate_output_floor(
    rwa_irb: float,
    rwa_standardised: float,
    year: int = 2028
) -> dict:
    """
    Calculate Output Floor adjustment for IRB banks.

    Floored RWA = max(RWA_IRB, floor% * RWA_SA)

    Parameters:
    -----------
    rwa_irb : float
        RWA calculated under IRB approach
    rwa_standardised : float
        RWA calculated under Standardised approach
    year : int
        Year for transitional floor percentage

    Returns:
    --------
    dict
        Output floor calculation results
    """
    # Get floor percentage for the year
    floor_pct = OUTPUT_FLOOR_TRANSITION.get(year, OUTPUT_FLOOR_PERCENTAGE)

    # Calculate floor
    floor_rwa = floor_pct * rwa_standardised

    # Apply floor
    floored_rwa = max(rwa_irb, floor_rwa)

    # Calculate add-on if floor is binding
    floor_addon = max(floor_rwa - rwa_irb, 0)
    floor_is_binding = floor_rwa > rwa_irb

    return {
        "rwa_irb": rwa_irb,
        "rwa_standardised": rwa_standardised,
        "floor_percentage": floor_pct,
        "floor_rwa": floor_rwa,
        "floored_rwa": floored_rwa,
        "floor_addon": floor_addon,
        "floor_is_binding": floor_is_binding,
        "rwa_reduction_from_irb": (1 - rwa_irb / rwa_standardised) * 100 if rwa_standardised > 0 else 0,
    }


def calculate_output_floor_by_risk_type(
    credit_risk_irb: float,
    credit_risk_sa: float,
    market_risk_ima: float = 0,
    market_risk_sa: float = 0,
    operational_risk: float = 0,
    cva_risk: float = 0,
    year: int = 2028
) -> dict:
    """
    Calculate Output Floor with breakdown by risk type.

    The floor applies to total RWA, not individual risk types.

    Parameters:
    -----------
    credit_risk_irb : float
        Credit risk RWA under IRB
    credit_risk_sa : float
        Credit risk RWA under SA
    market_risk_ima : float
        Market risk RWA under IMA
    market_risk_sa : float
        Market risk RWA under SA
    operational_risk : float
        Operational risk RWA (SMA)
    cva_risk : float
        CVA risk RWA
    year : int
        Year for transitional floor

    Returns:
    --------
    dict
        Detailed output floor results
    """
    # Total IRB-based RWA
    total_irb = credit_risk_irb + market_risk_ima + operational_risk + cva_risk

    # Total SA-based RWA
    total_sa = credit_risk_sa + market_risk_sa + operational_risk + cva_risk

    # Apply floor
    result = calculate_output_floor(total_irb, total_sa, year)

    # Add breakdown
    result["breakdown"] = {
        "credit_risk_irb": credit_risk_irb,
        "credit_risk_sa": credit_risk_sa,
        "market_risk_ima": market_risk_ima,
        "market_risk_sa": market_risk_sa,
        "operational_risk": operational_risk,
        "cva_risk": cva_risk,
    }

    return result


# =============================================================================
# Leverage Ratio - LEV30
# =============================================================================

LEVERAGE_RATIO_MINIMUM = 0.03  # 3%
GSIB_BUFFER = 0.005  # 0.5% for G-SIBs (50% of G-SIB buffer)


def calculate_leverage_ratio(
    tier1_capital: float,
    on_balance_sheet: float,
    derivatives_exposure: float,
    sft_exposure: float,
    off_balance_sheet: float,
    is_gsib: bool = False,
    gsib_buffer_pct: float = 0
) -> dict:
    """
    Calculate Leverage Ratio.

    Leverage Ratio = Tier 1 Capital / Total Exposure Measure

    Parameters:
    -----------
    tier1_capital : float
        Tier 1 capital (CET1 + AT1)
    on_balance_sheet : float
        On-balance sheet exposures (excluding derivatives and SFTs)
    derivatives_exposure : float
        Derivatives exposure (SA-CCR or simplified)
    sft_exposure : float
        Securities financing transactions exposure
    off_balance_sheet : float
        Off-balance sheet items (after CCF)
    is_gsib : bool
        Whether bank is a G-SIB
    gsib_buffer_pct : float
        G-SIB buffer percentage (e.g., 0.01 for 1%)

    Returns:
    --------
    dict
        Leverage ratio calculation results
    """
    # Total exposure measure
    total_exposure = (
        on_balance_sheet +
        derivatives_exposure +
        sft_exposure +
        off_balance_sheet
    )

    # Calculate leverage ratio
    leverage_ratio = tier1_capital / total_exposure if total_exposure > 0 else 0

    # Determine requirement
    min_requirement = LEVERAGE_RATIO_MINIMUM
    if is_gsib:
        min_requirement += gsib_buffer_pct * 0.5  # 50% of G-SIB buffer

    # Check compliance
    is_compliant = leverage_ratio >= min_requirement
    buffer = leverage_ratio - min_requirement

    # Required capital
    required_tier1 = min_requirement * total_exposure

    return {
        "tier1_capital": tier1_capital,
        "total_exposure": total_exposure,
        "leverage_ratio": leverage_ratio,
        "leverage_ratio_pct": leverage_ratio * 100,
        "minimum_requirement": min_requirement,
        "minimum_requirement_pct": min_requirement * 100,
        "is_compliant": is_compliant,
        "buffer": buffer,
        "buffer_pct": buffer * 100,
        "required_tier1": required_tier1,
        "excess_capital": tier1_capital - required_tier1,
        "exposure_breakdown": {
            "on_balance_sheet": on_balance_sheet,
            "derivatives": derivatives_exposure,
            "sft": sft_exposure,
            "off_balance_sheet": off_balance_sheet,
        }
    }


# =============================================================================
# Large Exposures - LEX30
# =============================================================================

LARGE_EXPOSURE_THRESHOLD = 0.10  # 10% of Tier 1 for reporting
LARGE_EXPOSURE_LIMIT = 0.25  # 25% of Tier 1 maximum
GSIB_INTERBANK_LIMIT = 0.15  # 15% for G-SIB to G-SIB exposures


def calculate_large_exposure(
    exposure_value: float,
    tier1_capital: float,
    counterparty_type: str = "corporate",
    is_gsib_counterparty: bool = False,
    bank_is_gsib: bool = False
) -> dict:
    """
    Calculate Large Exposure metrics.

    Parameters:
    -----------
    exposure_value : float
        Total exposure to counterparty (after CRM)
    tier1_capital : float
        Bank's Tier 1 capital
    counterparty_type : str
        Type: "corporate", "bank", "sovereign", "gsib"
    is_gsib_counterparty : bool
        Whether counterparty is a G-SIB
    bank_is_gsib : bool
        Whether the bank itself is a G-SIB

    Returns:
    --------
    dict
        Large exposure calculation results
    """
    # Calculate exposure as % of Tier 1
    exposure_pct = exposure_value / tier1_capital if tier1_capital > 0 else 0

    # Determine applicable limit
    if bank_is_gsib and is_gsib_counterparty:
        limit = GSIB_INTERBANK_LIMIT
        limit_type = "G-SIB to G-SIB"
    elif counterparty_type == "sovereign":
        limit = 1.0  # No limit for sovereigns (national discretion may apply)
        limit_type = "Sovereign (exempt)"
    else:
        limit = LARGE_EXPOSURE_LIMIT
        limit_type = "Standard"

    # Check thresholds
    is_large_exposure = exposure_pct >= LARGE_EXPOSURE_THRESHOLD
    exceeds_limit = exposure_pct > limit
    headroom = limit - exposure_pct

    # Maximum allowed exposure
    max_exposure = tier1_capital * limit

    return {
        "exposure_value": exposure_value,
        "tier1_capital": tier1_capital,
        "exposure_pct": exposure_pct * 100,
        "reporting_threshold_pct": LARGE_EXPOSURE_THRESHOLD * 100,
        "is_large_exposure": is_large_exposure,
        "limit": limit,
        "limit_pct": limit * 100,
        "limit_type": limit_type,
        "exceeds_limit": exceeds_limit,
        "headroom_pct": headroom * 100,
        "max_exposure": max_exposure,
        "available_capacity": max_exposure - exposure_value,
    }


def aggregate_connected_counterparties(
    exposures: list[dict],
    tier1_capital: float
) -> dict:
    """
    Aggregate exposures to connected counterparties.

    Connected counterparties must be treated as single counterparty.

    Parameters:
    -----------
    exposures : list of dict
        Each should have: counterparty, exposure_value, connection_group
    tier1_capital : float
        Bank's Tier 1 capital

    Returns:
    --------
    dict
        Aggregated exposure results
    """
    # Group by connection
    groups = {}
    for exp in exposures:
        group = exp.get("connection_group", exp["counterparty"])
        if group not in groups:
            groups[group] = {
                "counterparties": [],
                "total_exposure": 0,
            }
        groups[group]["counterparties"].append(exp["counterparty"])
        groups[group]["total_exposure"] += exp["exposure_value"]

    # Analyze each group
    results = {}
    for group, data in groups.items():
        le_result = calculate_large_exposure(
            data["total_exposure"],
            tier1_capital
        )
        le_result["counterparties"] = data["counterparties"]
        results[group] = le_result

    # Summary
    large_exposures = {k: v for k, v in results.items() if v["is_large_exposure"]}
    limit_breaches = {k: v for k, v in results.items() if v["exceeds_limit"]}

    return {
        "tier1_capital": tier1_capital,
        "groups": results,
        "num_large_exposures": len(large_exposures),
        "num_limit_breaches": len(limit_breaches),
        "large_exposures": large_exposures,
        "limit_breaches": limit_breaches,
    }


# =============================================================================
# Credit Risk Mitigation (CRM) - CRE22
# =============================================================================

# Standard supervisory haircuts (CRE22.52)
SUPERVISORY_HAIRCUTS = {
    # Debt securities by rating and maturity
    "sovereign_AAA_AA_1y": 0.005,
    "sovereign_AAA_AA_5y": 0.02,
    "sovereign_AAA_AA_long": 0.04,
    "sovereign_A_BBB_1y": 0.01,
    "sovereign_A_BBB_5y": 0.03,
    "sovereign_A_BBB_long": 0.06,
    "other_AAA_AA_1y": 0.01,
    "other_AAA_AA_5y": 0.04,
    "other_AAA_AA_long": 0.08,
    "other_A_BBB_1y": 0.02,
    "other_A_BBB_5y": 0.06,
    "other_A_BBB_long": 0.12,
    "securitization_AAA_AA_1y": 0.02,
    "securitization_AAA_AA_5y": 0.08,
    "securitization_AAA_AA_long": 0.16,

    # Main index equities
    "equity_main_index": 0.15,
    # Other equities
    "equity_other": 0.25,

    # Cash
    "cash": 0.0,

    # Gold
    "gold": 0.15,

    # Currency mismatch
    "fx_mismatch": 0.08,
}

# LGD values for secured exposures under F-IRB
SECURED_LGD = {
    "financial_collateral": 0.0,  # After haircuts
    "receivables": 0.35,
    "commercial_real_estate": 0.35,
    "residential_real_estate": 0.35,
    "other_physical": 0.40,
}


def calculate_collateral_haircut(
    collateral_type: str,
    collateral_value: float,
    issuer_rating: str = "AAA",
    maturity: str = "5y",
    currency_mismatch: bool = False
) -> dict:
    """
    Calculate haircut-adjusted collateral value.

    C_a = C * (1 - H_c - H_fx)

    Parameters:
    -----------
    collateral_type : str
        Type of collateral (cash, sovereign_debt, equity, etc.)
    collateral_value : float
        Market value of collateral
    issuer_rating : str
        Rating of collateral issuer
    maturity : str
        Maturity bucket: "1y", "5y", "long"
    currency_mismatch : bool
        Whether collateral is in different currency

    Returns:
    --------
    dict
        Haircut calculation results
    """
    # Determine haircut key
    if collateral_type == "cash":
        haircut_key = "cash"
    elif collateral_type == "gold":
        haircut_key = "gold"
    elif collateral_type.startswith("equity"):
        haircut_key = collateral_type
    elif collateral_type == "sovereign_debt":
        if issuer_rating in ["AAA", "AA+", "AA", "AA-"]:
            haircut_key = f"sovereign_AAA_AA_{maturity}"
        else:
            haircut_key = f"sovereign_A_BBB_{maturity}"
    elif collateral_type == "securitization":
        haircut_key = f"securitization_AAA_AA_{maturity}"
    else:
        haircut_key = f"other_A_BBB_{maturity}"

    # Get haircut
    h_c = SUPERVISORY_HAIRCUTS.get(haircut_key, 0.25)

    # FX haircut
    h_fx = SUPERVISORY_HAIRCUTS["fx_mismatch"] if currency_mismatch else 0

    # Total haircut
    total_haircut = h_c + h_fx

    # Adjusted value
    adjusted_value = collateral_value * (1 - total_haircut)

    return {
        "collateral_type": collateral_type,
        "collateral_value": collateral_value,
        "haircut_collateral": h_c,
        "haircut_fx": h_fx,
        "total_haircut": total_haircut,
        "adjusted_value": adjusted_value,
        "haircut_amount": collateral_value - adjusted_value,
    }


def calculate_exposure_with_crm(
    exposure_value: float,
    collateral: list[dict] = None,
    guarantee_value: float = 0,
    guarantor_rw: float = None,
    credit_derivative_value: float = 0,
    exposure_rw: float = 1.0
) -> dict:
    """
    Calculate exposure after Credit Risk Mitigation.

    Parameters:
    -----------
    exposure_value : float
        Original exposure value
    collateral : list of dict
        List of collateral with type, value, rating, etc.
    guarantee_value : float
        Value of unfunded credit protection (guarantee)
    guarantor_rw : float
        Risk weight of guarantor (for substitution approach)
    credit_derivative_value : float
        Value of credit derivative protection
    exposure_rw : float
        Risk weight of original exposure

    Returns:
    --------
    dict
        CRM calculation results
    """
    collateral = collateral or []

    # Calculate adjusted collateral value
    total_collateral = 0
    collateral_details = []

    for coll in collateral:
        result = calculate_collateral_haircut(
            coll.get("type", "other"),
            coll.get("value", 0),
            coll.get("rating", "BBB"),
            coll.get("maturity", "5y"),
            coll.get("currency_mismatch", False)
        )
        total_collateral += result["adjusted_value"]
        collateral_details.append(result)

    # Apply simple approach (SA) or comprehensive approach
    # Using comprehensive approach (more common)

    # Exposure after collateral
    e_star = max(exposure_value - total_collateral, 0)

    # Apply guarantee (substitution approach)
    if guarantee_value > 0 and guarantor_rw is not None:
        # Protected portion takes guarantor RW
        protected_portion = min(guarantee_value, e_star)
        unprotected_portion = e_star - protected_portion

        rwa_protected = protected_portion * guarantor_rw
        rwa_unprotected = unprotected_portion * exposure_rw
        total_rwa = rwa_protected + rwa_unprotected
    else:
        total_rwa = e_star * exposure_rw

    # Credit derivatives (simplified)
    if credit_derivative_value > 0:
        e_star = max(e_star - credit_derivative_value, 0)
        total_rwa = e_star * exposure_rw

    return {
        "original_exposure": exposure_value,
        "total_collateral_adjusted": total_collateral,
        "guarantee_value": guarantee_value,
        "credit_derivative_value": credit_derivative_value,
        "exposure_after_crm": e_star,
        "original_rwa": exposure_value * exposure_rw,
        "rwa_after_crm": total_rwa,
        "rwa_reduction": exposure_value * exposure_rw - total_rwa,
        "collateral_details": collateral_details,
    }


# =============================================================================
# Credit Conversion Factors (CCF) - CRE20.93-106
# =============================================================================

# CCF for off-balance sheet items under SA
SA_CCF = {
    # Commitments
    "commitment_unconditionally_cancellable": 0.10,  # 10%
    "commitment_1y_or_less": 0.20,  # 20%
    "commitment_over_1y": 0.40,  # 40%

    # Trade-related
    "trade_related_short_term": 0.20,  # 20%
    "transaction_related": 0.50,  # 50%

    # Direct credit substitutes
    "direct_credit_substitute": 1.00,  # 100%
    "standby_lc": 1.00,  # 100%

    # Other
    "nif_ruf": 0.50,  # 50%
    "other_commitments": 0.50,  # 50%

    # Repo-style transactions
    "repo_lending": 1.00,  # 100%

    # Unsettled transactions
    "unsettled_dvp_5_15_days": 1.00,  # 100%
    "unsettled_dvp_16_30_days": 6.25,  # 625%
    "unsettled_dvp_31_45_days": 9.375,  # 937.5%
    "unsettled_dvp_over_45_days": 12.50,  # 1250%
}

# CCF under IRB (Foundation)
IRB_CCF = {
    "commitment_unconditionally_cancellable": 0.00,  # 0% (own estimates under A-IRB)
    "commitment_1y_or_less": 0.20,
    "commitment_over_1y": 0.50,
    "nif_ruf": 0.50,
    "trade_related_short_term": 0.20,
    "transaction_related": 0.50,
    "direct_credit_substitute": 1.00,
}


def calculate_ead_off_balance_sheet(
    commitment_amount: float,
    commitment_type: str,
    drawn_amount: float = 0,
    approach: str = "SA"
) -> dict:
    """
    Calculate EAD for off-balance sheet items.

    EAD = Drawn + CCF * Undrawn

    Parameters:
    -----------
    commitment_amount : float
        Total commitment amount
    commitment_type : str
        Type of commitment
    drawn_amount : float
        Amount already drawn
    approach : str
        "SA" or "IRB"

    Returns:
    --------
    dict
        EAD calculation results
    """
    # Get CCF
    ccf_table = SA_CCF if approach == "SA" else IRB_CCF
    ccf = ccf_table.get(commitment_type, 0.50)

    # Calculate undrawn
    undrawn = commitment_amount - drawn_amount

    # Calculate EAD
    ead = drawn_amount + ccf * undrawn

    return {
        "commitment_amount": commitment_amount,
        "commitment_type": commitment_type,
        "drawn_amount": drawn_amount,
        "undrawn_amount": undrawn,
        "ccf": ccf,
        "ccf_pct": ccf * 100,
        "ead": ead,
        "approach": approach,
    }


def calculate_batch_off_balance_sheet(
    commitments: list[dict],
    approach: str = "SA"
) -> dict:
    """
    Calculate EAD for multiple off-balance sheet items.

    Parameters:
    -----------
    commitments : list of dict
        Each should have: amount, type, drawn (optional)
    approach : str
        "SA" or "IRB"

    Returns:
    --------
    dict
        Aggregated EAD results
    """
    results = []
    total_commitment = 0
    total_drawn = 0
    total_ead = 0

    for comm in commitments:
        result = calculate_ead_off_balance_sheet(
            comm["amount"],
            comm["type"],
            comm.get("drawn", 0),
            approach
        )
        results.append(result)
        total_commitment += comm["amount"]
        total_drawn += comm.get("drawn", 0)
        total_ead += result["ead"]

    return {
        "total_commitment": total_commitment,
        "total_drawn": total_drawn,
        "total_undrawn": total_commitment - total_drawn,
        "total_ead": total_ead,
        "average_ccf": (total_ead - total_drawn) / (total_commitment - total_drawn) if total_commitment > total_drawn else 0,
        "items": results,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Output Floor Example")
    print("=" * 70)

    floor_result = calculate_output_floor(
        rwa_irb=80_000_000_000,  # 80bn IRB RWA
        rwa_standardised=120_000_000_000,  # 120bn SA RWA
        year=2028
    )

    print(f"\n  RWA (IRB):               ${floor_result['rwa_irb']/1e9:.0f}bn")
    print(f"  RWA (SA):                ${floor_result['rwa_standardised']/1e9:.0f}bn")
    print(f"  Floor %:                 {floor_result['floor_percentage']*100:.1f}%")
    print(f"  Floor RWA:               ${floor_result['floor_rwa']/1e9:.0f}bn")
    print(f"  Floored RWA:             ${floor_result['floored_rwa']/1e9:.0f}bn")
    print(f"  Floor binding:           {floor_result['floor_is_binding']}")
    print(f"  IRB benefit vs SA:       {floor_result['rwa_reduction_from_irb']:.1f}%")

    print("\n" + "=" * 70)
    print("Leverage Ratio Example")
    print("=" * 70)

    lr_result = calculate_leverage_ratio(
        tier1_capital=50_000_000_000,  # 50bn Tier 1
        on_balance_sheet=1_000_000_000_000,  # 1tn on-BS
        derivatives_exposure=100_000_000_000,  # 100bn derivatives
        sft_exposure=50_000_000_000,  # 50bn SFT
        off_balance_sheet=200_000_000_000,  # 200bn off-BS
        is_gsib=True,
        gsib_buffer_pct=0.01
    )

    print(f"\n  Tier 1 Capital:          ${lr_result['tier1_capital']/1e9:.0f}bn")
    print(f"  Total Exposure:          ${lr_result['total_exposure']/1e9:.0f}tn")
    print(f"  Leverage Ratio:          {lr_result['leverage_ratio_pct']:.2f}%")
    print(f"  Minimum Required:        {lr_result['minimum_requirement_pct']:.2f}%")
    print(f"  Compliant:               {lr_result['is_compliant']}")
    print(f"  Buffer:                  {lr_result['buffer_pct']:.2f}%")

    print("\n" + "=" * 70)
    print("Large Exposures Example")
    print("=" * 70)

    le_result = calculate_large_exposure(
        exposure_value=10_000_000_000,  # 10bn exposure
        tier1_capital=50_000_000_000,   # 50bn Tier 1
        counterparty_type="corporate"
    )

    print(f"\n  Exposure:                ${le_result['exposure_value']/1e9:.0f}bn")
    print(f"  As % of Tier 1:          {le_result['exposure_pct']:.1f}%")
    print(f"  Is Large Exposure:       {le_result['is_large_exposure']}")
    print(f"  Limit:                   {le_result['limit_pct']:.0f}%")
    print(f"  Exceeds Limit:           {le_result['exceeds_limit']}")
    print(f"  Available Capacity:      ${le_result['available_capacity']/1e9:.1f}bn")

    print("\n" + "=" * 70)
    print("Credit Risk Mitigation Example")
    print("=" * 70)

    crm_result = calculate_exposure_with_crm(
        exposure_value=100_000_000,  # 100m exposure
        collateral=[
            {"type": "cash", "value": 20_000_000},
            {"type": "sovereign_debt", "value": 30_000_000, "rating": "AA", "maturity": "5y"},
        ],
        guarantee_value=20_000_000,
        guarantor_rw=0.20,
        exposure_rw=1.00
    )

    print(f"\n  Original Exposure:       ${crm_result['original_exposure']/1e6:.0f}m")
    print(f"  Collateral (adjusted):   ${crm_result['total_collateral_adjusted']/1e6:.0f}m")
    print(f"  Guarantee:               ${crm_result['guarantee_value']/1e6:.0f}m")
    print(f"  Exposure after CRM:      ${crm_result['exposure_after_crm']/1e6:.0f}m")
    print(f"  Original RWA:            ${crm_result['original_rwa']/1e6:.0f}m")
    print(f"  RWA after CRM:           ${crm_result['rwa_after_crm']/1e6:.0f}m")
    print(f"  RWA Reduction:           ${crm_result['rwa_reduction']/1e6:.0f}m")

    print("\n" + "=" * 70)
    print("Credit Conversion Factor Example")
    print("=" * 70)

    commitments = [
        {"amount": 100_000_000, "type": "commitment_over_1y", "drawn": 30_000_000},
        {"amount": 50_000_000, "type": "commitment_unconditionally_cancellable", "drawn": 0},
        {"amount": 20_000_000, "type": "direct_credit_substitute", "drawn": 20_000_000},
    ]

    ccf_result = calculate_batch_off_balance_sheet(commitments, approach="SA")

    print(f"\n  Total Commitment:        ${ccf_result['total_commitment']/1e6:.0f}m")
    print(f"  Total Drawn:             ${ccf_result['total_drawn']/1e6:.0f}m")
    print(f"  Total EAD:               ${ccf_result['total_ead']/1e6:.0f}m")
    print(f"  Average CCF:             {ccf_result['average_ccf']*100:.0f}%")
