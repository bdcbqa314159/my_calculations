"""
Total Capital Requirements Calculator - Basel III/IV

Comprehensive RWA Calculation Library integrating all risk types:

Core Credit Risk:
- SA-CR (KSA): Standardised Approach
- F-IRB: Foundation Internal Ratings-Based
- A-IRB: Advanced Internal Ratings-Based
- Specialized Lending: Slotting approach (PF, OF, CF, IPRE, HVCRE)
- Infrastructure Supporting Factor
- Purchased Receivables (Dilution Risk)
- Double Default Framework

Securitization:
- SEC-SA: Standardised Approach
- SEC-IRBA: Internal Ratings-Based Approach
- ERBA: External Ratings-Based Approach
- IAA: Internal Assessment Approach
- STC Criteria Checker
- Significant Risk Transfer (SRT) Test

Counterparty & CVA:
- SA-CCR: Standardised Approach for CCR
- BA-CVA: Basic Approach for CVA
- SA-CVA: Standardised Approach for CVA

Market Risk:
- FRTB-SA: Sensitivities-based Method (SbM)
- DRC: Default Risk Charge
- RRAO: Residual Risk Add-On
- Simplified SA (for smaller banks)

Operational Risk:
- SMA: Standardised Measurement Approach

Liquidity:
- LCR: Liquidity Coverage Ratio
- NSFR: Net Stable Funding Ratio

Interest Rate Risk (Banking Book):
- IRRBB: EVE and NII sensitivity
- Duration Gap Analysis

Equity & CCP:
- Equity: Simple RW, PD/LGD, Funds
- CCP: Trade exposures, Default fund contributions

Capital Framework:
- Output Floor (72.5%)
- Leverage Ratio
- Large Exposures
- CRM (Credit Risk Mitigation)
- CCF (Credit Conversion Factors)
- G-SIB Scoring and Buffers
- TLAC/MREL

Specialized:
- Crypto-assets (Groups 1a, 1b, 2a, 2b)
- Step-in Risk (BCBS 398)
- Pillar 3 Disclosure Templates
- Stress Testing Framework
"""

from rwa_calc import (
    calculate_sa_rwa, calculate_rwa, calculate_airb_rwa,
    calculate_sec_sa_rwa, calculate_sec_irba_rwa, calculate_erba_rwa,
    compare_all_irb_approaches, compare_securitization_approaches,
    RATING_TO_PD
)
from counterparty_risk import calculate_sa_ccr_ead, calculate_ba_cva
from market_risk import calculate_frtb_sa, calculate_drc_charge, calculate_rrao
from operational_risk import calculate_sma_capital
from capital_framework import (
    calculate_output_floor, calculate_leverage_ratio,
    calculate_large_exposure, calculate_exposure_with_crm,
    calculate_batch_off_balance_sheet
)


def calculate_total_rwa(
    # Credit Risk
    credit_exposures_sa: list[dict] = None,
    credit_exposures_irb: list[dict] = None,
    use_airb: bool = False,

    # Securitization
    securitization_exposures: list[dict] = None,
    securitization_approach: str = "SEC-SA",

    # Counterparty Credit Risk
    derivative_trades: list[dict] = None,
    derivative_collateral: float = 0,

    # CVA
    cva_counterparties: list[dict] = None,

    # Market Risk
    trading_positions: dict = None,
    drc_positions: list[dict] = None,
    rrao_positions: list[dict] = None,

    # Operational Risk
    business_indicator: float = 0,
    average_annual_loss: float = 0,

    # Output Floor
    apply_output_floor: bool = True,
    floor_year: int = 2028,
) -> dict:
    """
    Calculate total RWA across all risk types.

    Returns:
    --------
    dict
        Comprehensive RWA breakdown
    """
    credit_exposures_sa = credit_exposures_sa or []
    credit_exposures_irb = credit_exposures_irb or []
    securitization_exposures = securitization_exposures or []
    derivative_trades = derivative_trades or []
    cva_counterparties = cva_counterparties or []
    trading_positions = trading_positions or {}
    drc_positions = drc_positions or []
    rrao_positions = rrao_positions or []

    results = {
        "credit_risk": {"sa": 0, "irb": 0, "approach": "SA"},
        "securitization": {"rwa": 0, "approach": securitization_approach},
        "counterparty_risk": {"ead": 0, "rwa": 0},
        "cva_risk": {"rwa": 0},
        "market_risk": {"rwa": 0},
        "operational_risk": {"rwa": 0},
    }

    # ==========================================================================
    # Credit Risk RWA
    # ==========================================================================
    credit_rwa_sa = 0
    credit_rwa_irb = 0

    # SA calculation
    for exp in credit_exposures_sa:
        sa_result = calculate_sa_rwa(
            exp["ead"],
            exp.get("exposure_class", "corporate"),
            exp.get("rating", "unrated"),
            **{k: v for k, v in exp.items() if k not in ["ead", "exposure_class", "rating"]}
        )
        credit_rwa_sa += sa_result["rwa"]

    # IRB calculation
    for exp in credit_exposures_irb:
        if use_airb:
            irb_result = calculate_airb_rwa(
                exp["ead"], exp["pd"], exp["lgd"],
                exp.get("maturity", 2.5), exp.get("asset_class", "corporate")
            )
        else:
            irb_result = calculate_rwa(
                exp["ead"], exp["pd"], exp.get("lgd", 0.45),
                exp.get("maturity", 2.5), exp.get("asset_class", "corporate")
            )
        credit_rwa_irb += irb_result["rwa"]

    results["credit_risk"]["sa"] = credit_rwa_sa
    results["credit_risk"]["irb"] = credit_rwa_irb

    # Determine which to use
    if credit_exposures_irb:
        results["credit_risk"]["rwa"] = credit_rwa_irb
        results["credit_risk"]["approach"] = "A-IRB" if use_airb else "F-IRB"
    else:
        results["credit_risk"]["rwa"] = credit_rwa_sa
        results["credit_risk"]["approach"] = "SA-CR"

    # ==========================================================================
    # Securitization RWA
    # ==========================================================================
    sec_rwa = 0
    for exp in securitization_exposures:
        if securitization_approach == "SEC-IRBA":
            sec_result = calculate_sec_irba_rwa(
                exp["ead"], exp["attachment"], exp["detachment"],
                kirb=exp.get("kirb", 0.06), n=exp.get("n", 25)
            )
        elif securitization_approach == "ERBA":
            sec_result = calculate_erba_rwa(
                exp["ead"], exp["rating"], exp.get("seniority", "senior")
            )
        else:  # SEC-SA
            sec_result = calculate_sec_sa_rwa(
                exp["ead"], exp["attachment"], exp["detachment"],
                ksa=exp.get("ksa", 0.08), n=exp.get("n", 25)
            )
        sec_rwa += sec_result["rwa"]

    results["securitization"]["rwa"] = sec_rwa

    # ==========================================================================
    # Counterparty Credit Risk (SA-CCR)
    # ==========================================================================
    if derivative_trades:
        ccr_result = calculate_sa_ccr_ead(
            derivative_trades,
            collateral_held=derivative_collateral
        )
        ccr_ead = ccr_result["ead"]

        # Apply counterparty risk weight (simplified: 100%)
        ccr_rw = 1.0
        ccr_rwa = ccr_ead * ccr_rw * 12.5  # Standardised approach

        results["counterparty_risk"]["ead"] = ccr_ead
        results["counterparty_risk"]["rwa"] = ccr_rwa
        results["counterparty_risk"]["detail"] = ccr_result

    # ==========================================================================
    # CVA Risk
    # ==========================================================================
    if cva_counterparties:
        cva_result = calculate_ba_cva(cva_counterparties)
        results["cva_risk"]["rwa"] = cva_result["rwa"]
        results["cva_risk"]["detail"] = cva_result

    # ==========================================================================
    # Market Risk (FRTB-SA)
    # ==========================================================================
    if trading_positions or drc_positions or rrao_positions:
        frtb_result = calculate_frtb_sa(
            delta_positions=trading_positions,
            drc_positions=drc_positions,
            rrao_positions=rrao_positions
        )
        results["market_risk"]["rwa"] = frtb_result["total_rwa"]
        results["market_risk"]["detail"] = frtb_result

    # ==========================================================================
    # Operational Risk (SMA)
    # ==========================================================================
    if business_indicator > 0:
        sma_result = calculate_sma_capital(
            bi=business_indicator,
            average_annual_loss=average_annual_loss
        )
        results["operational_risk"]["rwa"] = sma_result["rwa"]
        results["operational_risk"]["detail"] = sma_result

    # ==========================================================================
    # Total RWA
    # ==========================================================================
    total_rwa_irb = (
        results["credit_risk"]["irb"] +
        results["securitization"]["rwa"] +
        results["counterparty_risk"]["rwa"] +
        results["cva_risk"]["rwa"] +
        results["market_risk"]["rwa"] +
        results["operational_risk"]["rwa"]
    )

    total_rwa_sa = (
        results["credit_risk"]["sa"] +
        results["securitization"]["rwa"] +
        results["counterparty_risk"]["rwa"] +
        results["cva_risk"]["rwa"] +
        results["market_risk"]["rwa"] +
        results["operational_risk"]["rwa"]
    )

    results["total_rwa_irb_based"] = total_rwa_irb
    results["total_rwa_sa_based"] = total_rwa_sa

    # ==========================================================================
    # Output Floor
    # ==========================================================================
    if apply_output_floor and credit_exposures_irb:
        floor_result = calculate_output_floor(
            total_rwa_irb, total_rwa_sa, floor_year
        )
        results["output_floor"] = floor_result
        results["total_rwa_floored"] = floor_result["floored_rwa"]
        results["total_rwa"] = floor_result["floored_rwa"]
    else:
        results["total_rwa"] = total_rwa_irb if credit_exposures_irb else total_rwa_sa

    return results


def calculate_capital_ratios(
    total_rwa: float,
    cet1_capital: float,
    at1_capital: float = 0,
    tier2_capital: float = 0,
    countercyclical_buffer: float = 0,
    gsib_buffer: float = 0
) -> dict:
    """
    Calculate capital ratios and buffers.

    Parameters:
    -----------
    total_rwa : float
        Total risk-weighted assets
    cet1_capital : float
        Common Equity Tier 1 capital
    at1_capital : float
        Additional Tier 1 capital
    tier2_capital : float
        Tier 2 capital
    countercyclical_buffer : float
        Countercyclical buffer rate (e.g., 0.01 for 1%)
    gsib_buffer : float
        G-SIB buffer rate

    Returns:
    --------
    dict
        Capital ratios and compliance status
    """
    tier1_capital = cet1_capital + at1_capital
    total_capital = tier1_capital + tier2_capital

    # Calculate ratios
    cet1_ratio = cet1_capital / total_rwa if total_rwa > 0 else 0
    tier1_ratio = tier1_capital / total_rwa if total_rwa > 0 else 0
    total_ratio = total_capital / total_rwa if total_rwa > 0 else 0

    # Minimum requirements (Pillar 1)
    min_cet1 = 0.045  # 4.5%
    min_tier1 = 0.06  # 6%
    min_total = 0.08  # 8%

    # Capital conservation buffer
    conservation_buffer = 0.025  # 2.5%

    # Total buffer requirement
    total_buffer_req = conservation_buffer + countercyclical_buffer + gsib_buffer

    # Combined requirement
    combined_cet1_req = min_cet1 + total_buffer_req
    combined_tier1_req = min_tier1 + total_buffer_req
    combined_total_req = min_total + total_buffer_req

    # Check compliance
    cet1_compliant = cet1_ratio >= combined_cet1_req
    tier1_compliant = tier1_ratio >= combined_tier1_req
    total_compliant = total_ratio >= combined_total_req

    # Surplus/deficit
    cet1_surplus = (cet1_ratio - combined_cet1_req) * total_rwa
    tier1_surplus = (tier1_ratio - combined_tier1_req) * total_rwa
    total_surplus = (total_ratio - combined_total_req) * total_rwa

    return {
        "cet1_capital": cet1_capital,
        "tier1_capital": tier1_capital,
        "total_capital": total_capital,
        "total_rwa": total_rwa,
        "cet1_ratio": cet1_ratio,
        "cet1_ratio_pct": cet1_ratio * 100,
        "tier1_ratio": tier1_ratio,
        "tier1_ratio_pct": tier1_ratio * 100,
        "total_ratio": total_ratio,
        "total_ratio_pct": total_ratio * 100,
        "requirements": {
            "min_cet1": min_cet1,
            "min_tier1": min_tier1,
            "min_total": min_total,
            "conservation_buffer": conservation_buffer,
            "countercyclical_buffer": countercyclical_buffer,
            "gsib_buffer": gsib_buffer,
            "combined_cet1": combined_cet1_req,
            "combined_tier1": combined_tier1_req,
            "combined_total": combined_total_req,
        },
        "compliance": {
            "cet1": cet1_compliant,
            "tier1": tier1_compliant,
            "total": total_compliant,
            "all": cet1_compliant and tier1_compliant and total_compliant,
        },
        "surplus": {
            "cet1": cet1_surplus,
            "tier1": tier1_surplus,
            "total": total_surplus,
        }
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("COMPREHENSIVE RWA CALCULATION EXAMPLE")
    print("=" * 70)

    # ==========================================================================
    # Sample Bank Portfolio
    # ==========================================================================

    # Credit exposures (for SA)
    credit_exposures_sa = [
        {"ead": 500_000_000, "exposure_class": "corporate", "rating": "A"},
        {"ead": 300_000_000, "exposure_class": "corporate", "rating": "BBB"},
        {"ead": 200_000_000, "exposure_class": "retail", "retail_type": "regulatory_retail"},
        {"ead": 400_000_000, "exposure_class": "residential_re", "ltv": 0.70},
        {"ead": 100_000_000, "exposure_class": "bank", "rating": "A"},
    ]

    # Credit exposures (for IRB)
    credit_exposures_irb = [
        {"ead": 500_000_000, "pd": 0.009, "lgd": 0.35, "maturity": 3.0},  # A-rated
        {"ead": 300_000_000, "pd": 0.04, "lgd": 0.40, "maturity": 2.5},   # BBB-rated
        {"ead": 200_000_000, "pd": 0.02, "lgd": 0.30, "maturity": 1.0, "asset_class": "retail_other"},
        {"ead": 400_000_000, "pd": 0.01, "lgd": 0.15, "maturity": 15.0, "asset_class": "retail_mortgage"},
        {"ead": 100_000_000, "pd": 0.002, "lgd": 0.45, "maturity": 1.0},  # Bank
    ]

    # Securitization exposures
    securitization_exposures = [
        {"ead": 50_000_000, "attachment": 0.10, "detachment": 0.20, "rating": "A", "ksa": 0.08},
        {"ead": 30_000_000, "attachment": 0.03, "detachment": 0.10, "rating": "BBB", "ksa": 0.08},
    ]

    # Derivative trades
    derivative_trades = [
        {"notional": 100_000_000, "asset_class": "IR", "maturity": 5.0, "mtm": 2_000_000, "delta": 1.0},
        {"notional": 50_000_000, "asset_class": "FX", "maturity": 1.0, "mtm": 500_000, "delta": 1.0},
    ]

    # CVA counterparties
    cva_counterparties = [
        {"ead": 10_000_000, "rating": "A", "maturity": 3.0},
        {"ead": 5_000_000, "rating": "BBB", "maturity": 5.0},
    ]

    # Trading positions (simplified)
    trading_positions = {
        "EQ": [
            {"bucket": "large_cap_developed", "sensitivity": 5_000_000, "risk_weight": 20},
        ]
    }

    # DRC positions
    drc_positions = [
        {"obligor": "Corp_X", "notional": 10_000_000, "rating": "A", "seniority": "senior", "is_long": True},
    ]

    # Operational risk inputs
    business_indicator = 2_000_000_000  # 2bn BI
    average_annual_loss = 100_000_000    # 100m average loss

    # ==========================================================================
    # Calculate Total RWA
    # ==========================================================================

    print("\n" + "-" * 40)
    print("Calculating RWA with A-IRB...")
    print("-" * 40)

    result = calculate_total_rwa(
        credit_exposures_sa=credit_exposures_sa,
        credit_exposures_irb=credit_exposures_irb,
        use_airb=True,
        securitization_exposures=securitization_exposures,
        securitization_approach="SEC-SA",
        derivative_trades=derivative_trades,
        derivative_collateral=1_000_000,
        cva_counterparties=cva_counterparties,
        trading_positions=trading_positions,
        drc_positions=drc_positions,
        business_indicator=business_indicator,
        average_annual_loss=average_annual_loss,
        apply_output_floor=True,
        floor_year=2028
    )

    # Print results
    print(f"\n  Risk Type               SA RWA         IRB RWA")
    print(f"  {'-'*20} {'-'*14} {'-'*14}")
    print(f"  Credit Risk             ${result['credit_risk']['sa']/1e6:>10,.0f}m  ${result['credit_risk']['irb']/1e6:>10,.0f}m")
    print(f"  Securitization          ${result['securitization']['rwa']/1e6:>10,.0f}m")
    print(f"  Counterparty Risk       ${result['counterparty_risk']['rwa']/1e6:>10,.0f}m")
    print(f"  CVA Risk                ${result['cva_risk']['rwa']/1e6:>10,.0f}m")
    print(f"  Market Risk             ${result['market_risk']['rwa']/1e6:>10,.0f}m")
    print(f"  Operational Risk        ${result['operational_risk']['rwa']/1e6:>10,.0f}m")
    print(f"  {'-'*20} {'-'*14} {'-'*14}")
    print(f"  Total (pre-floor)       ${result['total_rwa_sa_based']/1e6:>10,.0f}m  ${result['total_rwa_irb_based']/1e6:>10,.0f}m")

    if "output_floor" in result:
        print(f"\n  Output Floor Analysis:")
        print(f"    Floor %:              {result['output_floor']['floor_percentage']*100:.1f}%")
        print(f"    Floor binding:        {result['output_floor']['floor_is_binding']}")
        if result['output_floor']['floor_is_binding']:
            print(f"    Floor add-on:         ${result['output_floor']['floor_addon']/1e6:,.0f}m")

    print(f"\n  TOTAL RWA (floored):    ${result['total_rwa']/1e6:,.0f}m")

    # ==========================================================================
    # Capital Ratios
    # ==========================================================================
    print("\n" + "=" * 70)
    print("CAPITAL RATIOS")
    print("=" * 70)

    capital_result = calculate_capital_ratios(
        total_rwa=result["total_rwa"],
        cet1_capital=80_000_000_000,    # 80bn CET1
        at1_capital=10_000_000_000,     # 10bn AT1
        tier2_capital=15_000_000_000,   # 15bn T2
        countercyclical_buffer=0.01,     # 1%
        gsib_buffer=0.015                # 1.5%
    )

    print(f"\n  Capital:")
    print(f"    CET1:                 ${capital_result['cet1_capital']/1e9:.0f}bn")
    print(f"    Tier 1:               ${capital_result['tier1_capital']/1e9:.0f}bn")
    print(f"    Total Capital:        ${capital_result['total_capital']/1e9:.0f}bn")

    print(f"\n  Ratios vs Requirements:")
    print(f"    {'Ratio':<12} {'Actual':>10} {'Required':>10} {'Status':>10}")
    print(f"    {'-'*12} {'-'*10} {'-'*10} {'-'*10}")
    print(f"    {'CET1':<12} {capital_result['cet1_ratio_pct']:>9.1f}% {capital_result['requirements']['combined_cet1']*100:>9.1f}% {'PASS' if capital_result['compliance']['cet1'] else 'FAIL':>10}")
    print(f"    {'Tier 1':<12} {capital_result['tier1_ratio_pct']:>9.1f}% {capital_result['requirements']['combined_tier1']*100:>9.1f}% {'PASS' if capital_result['compliance']['tier1'] else 'FAIL':>10}")
    print(f"    {'Total':<12} {capital_result['total_ratio_pct']:>9.1f}% {capital_result['requirements']['combined_total']*100:>9.1f}% {'PASS' if capital_result['compliance']['total'] else 'FAIL':>10}")

    print(f"\n  Overall Status:         {'COMPLIANT' if capital_result['compliance']['all'] else 'NON-COMPLIANT'}")
    print(f"  CET1 Surplus:           ${capital_result['surplus']['cet1']/1e9:.1f}bn")

    # ==========================================================================
    # Summary of Approaches Implemented
    # ==========================================================================
    print("\n" + "=" * 70)
    print("IMPLEMENTED METHODOLOGIES SUMMARY - BASEL III/IV LIBRARY")
    print("=" * 70)

    methodologies = [
        ("Credit Risk (rwa_calc.py)", [
            "SA-CR (KSA) - Standardised Approach",
            "F-IRB - Foundation IRB",
            "A-IRB - Advanced IRB",
        ]),
        ("Specialized Lending (specialized_lending.py)", [
            "Slotting: Project Finance, Object Finance, Commodities Finance",
            "IPRE - Income Producing Real Estate",
            "HVCRE - High Volatility Commercial Real Estate",
        ]),
        ("Credit Risk Advanced (credit_risk_advanced.py)", [
            "Infrastructure Supporting Factor (0.75x RWA)",
            "Purchased Receivables - Dilution Risk",
            "Double Default Framework",
        ]),
        ("Securitization (rwa_calc.py)", [
            "SEC-SA - Standardised Approach",
            "SEC-IRBA - Internal Ratings-Based",
            "ERBA - External Ratings-Based",
            "IAA - Internal Assessment Approach",
        ]),
        ("Securitization Tests (securitization_tests.py)", [
            "STC Criteria Checker (Simple, Transparent, Comparable)",
            "Significant Risk Transfer (SRT) Test",
        ]),
        ("Counterparty Risk (counterparty_risk.py)", [
            "SA-CCR - Standardised Approach for CCR",
            "BA-CVA - Basic Approach for CVA",
            "SA-CVA - Standardised Approach for CVA",
        ]),
        ("Market Risk FRTB (market_risk.py)", [
            "SbM - Sensitivities-based Method (Delta, Vega, Curvature)",
            "DRC - Default Risk Charge",
            "RRAO - Residual Risk Add-On",
        ]),
        ("Simplified Market Risk (simplified_sa_mr.py)", [
            "Simplified SA for smaller banks",
            "De minimis exemption check",
            "Delta-plus method for options",
        ]),
        ("Operational Risk (operational_risk.py)", [
            "SMA - Standardised Measurement Approach",
            "BIC calculation (12%/15%/18% buckets)",
            "Internal Loss Multiplier (ILM)",
        ]),
        ("Liquidity (liquidity.py)", [
            "LCR - Liquidity Coverage Ratio",
            "NSFR - Net Stable Funding Ratio",
            "HQLA classification and haircuts",
        ]),
        ("IRRBB (irrbb.py)", [
            "EVE - Economic Value of Equity (6 scenarios)",
            "NII - Net Interest Income sensitivity",
            "Duration Gap Analysis",
            "Outlier Test (15% of Tier 1)",
        ]),
        ("Equity & CCP (equity_ccp.py)", [
            "Equity: Simple RW (300%/400%), PD/LGD approach",
            "Investment Funds: Look-through, Mandate, Fall-back",
            "CCP: Trade exposures (2% QCCP), Default fund",
        ]),
        ("Capital Framework (capital_framework.py)", [
            "Output Floor (72.5% with transition)",
            "Leverage Ratio (3% minimum)",
            "Large Exposures (25% Tier 1 limit)",
            "CRM - Credit Risk Mitigation",
            "CCF - Credit Conversion Factors",
        ]),
        ("G-SIB & TLAC (gsib_tlac.py)", [
            "G-SIB Scoring (5 categories, 12 indicators)",
            "G-SIB Buckets and Buffers (1%-3.5%)",
            "TLAC (18% RWA, 6.75% leverage)",
            "MREL requirements",
        ]),
        ("Crypto-assets (crypto_assets.py)", [
            "Group 1a - Tokenised traditional assets",
            "Group 1b - Stablecoins (with redemption risk)",
            "Group 2a - Crypto with hedging recognition",
            "Group 2b - Other crypto (1250% RW)",
            "Exposure limits (2% Tier 1 for Group 2)",
        ]),
        ("Step-in Risk (step_in_risk.py)", [
            "Entity assessment (SPVs, MMFs, Funds)",
            "Step-in indicators scoring",
            "Capital and liquidity impact",
        ]),
        ("Pillar 3 (pillar3.py)", [
            "KM1 - Key Metrics",
            "OV1 - RWA Overview",
            "CR1 - Credit Quality",
            "LIQ1 - LCR disclosure",
        ]),
        ("Stress Testing (stress_testing.py)", [
            "Macro scenario design (Baseline/Adverse/Severe)",
            "Credit stress (PD/LGD migration)",
            "Market stress (VaR, P&L)",
            "Liquidity stress (LCR impact)",
            "Capital impact assessment",
        ]),
    ]

    for category, approaches in methodologies:
        print(f"\n  {category}:")
        for approach in approaches:
            print(f"    ✓ {approach}")

    print("\n" + "=" * 70)
    print("Total: 17 modules covering all major Basel III/IV methodologies")
    print("=" * 70)
