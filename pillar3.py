"""
Pillar 3 Disclosure Framework - Basel III/IV
BCBS d400 (March 2017), BCBS d455 (December 2018)

Pillar 3 = Market discipline through public disclosure

Key disclosure templates:
- Overview templates (KM, OV1)
- Credit risk (CR, CR-SA, CR-IRB)
- Counterparty credit risk (CCR)
- Securitization (SEC)
- Market risk (MR)
- Operational risk (OR)
- Liquidity (LIQ)
- Capital composition (CC)
- Leverage ratio (LR)

Reference: BCBS Pillar 3 disclosure requirements
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import date
import json


class DisclosureFrequency(Enum):
    """Disclosure frequency requirements."""
    ANNUAL = "annual"
    SEMI_ANNUAL = "semi_annual"
    QUARTERLY = "quarterly"


class DisclosureTemplate(Enum):
    """Standard Pillar 3 disclosure templates."""
    # Overview
    KM1 = "KM1"    # Key metrics
    KM2 = "KM2"    # Key metrics - TLAC
    OV1 = "OV1"    # Overview of RWA

    # Credit Risk
    CR1 = "CR1"    # Credit quality of assets
    CR2 = "CR2"    # Changes in defaulted loans
    CR3 = "CR3"    # CRM techniques
    CR4 = "CR4"    # SA credit risk exposure
    CR5 = "CR5"    # SA exposures by asset class
    CR6 = "CR6"    # IRB credit risk exposure
    CR7 = "CR7"    # IRB effect on RWA
    CR8 = "CR8"    # RWA flow statements

    # CCR
    CCR1 = "CCR1"  # Analysis of CCR exposure
    CCR2 = "CCR2"  # CVA capital charge
    CCR3 = "CCR3"  # SA-CCR exposures
    CCR5 = "CCR5"  # Composition of collateral
    CCR6 = "CCR6"  # Credit derivatives

    # Securitization
    SEC1 = "SEC1"  # Securitization exposures in banking book
    SEC2 = "SEC2"  # Securitization exposures in trading book
    SEC3 = "SEC3"  # Securitization exposures and RWA
    SEC4 = "SEC4"  # Securitization exposures and capital

    # Market Risk
    MR1 = "MR1"    # Market risk under SA
    MR2 = "MR2"    # RWA flow for market risk
    MR3 = "MR3"    # IMA values for trading portfolios

    # Operational Risk
    OR1 = "OR1"    # Historical losses

    # Liquidity
    LIQ1 = "LIQ1"  # LCR
    LIQ2 = "LIQ2"  # NSFR

    # Leverage
    LR1 = "LR1"    # Leverage ratio common disclosure
    LR2 = "LR2"    # Leverage ratio

    # Capital
    CC1 = "CC1"    # Capital composition
    CC2 = "CC2"    # Capital reconciliation


# Template requirements mapping
TEMPLATE_REQUIREMENTS = {
    DisclosureTemplate.KM1: {
        "frequency": DisclosureFrequency.QUARTERLY,
        "description": "Key metrics template",
        "rows": [
            "cet1_capital", "at1_capital", "tier1_capital", "tier2_capital",
            "total_capital", "total_rwa", "cet1_ratio", "tier1_ratio",
            "total_capital_ratio", "leverage_ratio", "lcr", "nsfr",
        ],
    },
    DisclosureTemplate.OV1: {
        "frequency": DisclosureFrequency.QUARTERLY,
        "description": "Overview of risk-weighted assets",
        "rows": [
            "credit_risk_sa", "credit_risk_irb", "ccr", "cva",
            "equity_irb", "securitization", "market_risk", "operational_risk",
            "amounts_below_threshold", "floor_adjustment", "total_rwa",
        ],
    },
    DisclosureTemplate.CR1: {
        "frequency": DisclosureFrequency.SEMI_ANNUAL,
        "description": "Credit quality of assets",
        "rows": [
            "loans", "debt_securities", "off_balance_sheet", "total",
        ],
        "columns": [
            "gross_carrying_amount_defaulted", "gross_carrying_amount_non_defaulted",
            "allowances", "net_values",
        ],
    },
    DisclosureTemplate.LIQ1: {
        "frequency": DisclosureFrequency.QUARTERLY,
        "description": "Liquidity Coverage Ratio",
        "rows": [
            "hqla", "cash_outflows", "cash_inflows", "net_cash_outflows", "lcr",
        ],
    },
}


@dataclass
class DisclosureData:
    """Data structure for a disclosure template."""
    template: DisclosureTemplate
    reporting_date: date
    data: Dict[str, Any]
    currency: str = "EUR"
    units: str = "millions"


@dataclass
class Pillar3Report:
    """Complete Pillar 3 disclosure report."""
    bank_name: str
    reporting_date: date
    disclosures: List[DisclosureData] = field(default_factory=list)
    qualitative_disclosures: Dict[str, str] = field(default_factory=dict)


def generate_km1_template(
    cet1_capital: float,
    at1_capital: float,
    tier2_capital: float,
    total_rwa: float,
    leverage_exposure: float,
    lcr: float,
    nsfr: float,
    prior_period: Optional[Dict] = None,
) -> DisclosureData:
    """
    Generate KM1 Key Metrics template.

    Args:
        cet1_capital: Common Equity Tier 1 capital
        at1_capital: Additional Tier 1 capital
        tier2_capital: Tier 2 capital
        total_rwa: Total risk-weighted assets
        leverage_exposure: Total leverage exposure measure
        lcr: Liquidity Coverage Ratio
        nsfr: Net Stable Funding Ratio
        prior_period: Prior period data for comparison

    Returns:
        DisclosureData for KM1 template
    """
    tier1_capital = cet1_capital + at1_capital
    total_capital = tier1_capital + tier2_capital

    # Calculate ratios
    cet1_ratio = cet1_capital / total_rwa if total_rwa > 0 else 0
    tier1_ratio = tier1_capital / total_rwa if total_rwa > 0 else 0
    total_capital_ratio = total_capital / total_rwa if total_rwa > 0 else 0
    leverage_ratio = tier1_capital / leverage_exposure if leverage_exposure > 0 else 0

    data = {
        "available_capital": {
            "cet1_capital": cet1_capital,
            "tier1_capital": tier1_capital,
            "total_capital": total_capital,
        },
        "risk_weighted_assets": {
            "total_rwa": total_rwa,
        },
        "capital_ratios": {
            "cet1_ratio": cet1_ratio,
            "tier1_ratio": tier1_ratio,
            "total_capital_ratio": total_capital_ratio,
        },
        "additional_cet1_buffers": {
            "capital_conservation_buffer": 0.025,
            "countercyclical_buffer": 0.0,  # Would be calculated
            "gsib_buffer": 0.0,  # If applicable
            "total_buffer_requirement": 0.025,
            "cet1_available_for_buffers": max(0, cet1_ratio - 0.045),
        },
        "leverage_ratio": {
            "exposure_measure": leverage_exposure,
            "leverage_ratio": leverage_ratio,
        },
        "liquidity_ratios": {
            "lcr": lcr,
            "nsfr": nsfr,
        },
    }

    # Add comparison to prior period if available
    if prior_period:
        data["comparison"] = {
            "cet1_ratio_change": cet1_ratio - prior_period.get("cet1_ratio", 0),
            "total_rwa_change": total_rwa - prior_period.get("total_rwa", 0),
        }

    return DisclosureData(
        template=DisclosureTemplate.KM1,
        reporting_date=date.today(),
        data=data,
    )


def generate_ov1_template(
    credit_risk_sa_rwa: float,
    credit_risk_irb_rwa: float,
    ccr_rwa: float,
    cva_rwa: float,
    equity_rwa: float,
    securitization_rwa: float,
    market_risk_rwa: float,
    operational_risk_rwa: float,
    floor_adjustment: float = 0,
) -> DisclosureData:
    """
    Generate OV1 Overview of RWA template.

    Args:
        credit_risk_sa_rwa: Credit risk RWA under SA
        credit_risk_irb_rwa: Credit risk RWA under IRB
        ccr_rwa: Counterparty credit risk RWA
        cva_rwa: CVA risk RWA
        equity_rwa: Equity positions RWA
        securitization_rwa: Securitization exposures RWA
        market_risk_rwa: Market risk RWA
        operational_risk_rwa: Operational risk RWA
        floor_adjustment: Output floor adjustment

    Returns:
        DisclosureData for OV1 template
    """
    # Calculate totals
    total_credit_risk = credit_risk_sa_rwa + credit_risk_irb_rwa
    total_rwa_before_floor = (
        total_credit_risk + ccr_rwa + cva_rwa + equity_rwa +
        securitization_rwa + market_risk_rwa + operational_risk_rwa
    )
    total_rwa = total_rwa_before_floor + floor_adjustment

    # Minimum capital requirement (8%)
    min_capital = total_rwa * 0.08

    data = {
        "risk_weighted_assets": {
            "1_credit_risk_sa": credit_risk_sa_rwa,
            "2_credit_risk_irb": credit_risk_irb_rwa,
            "3_ccr": ccr_rwa,
            "4_cva": cva_rwa,
            "5_equity_irb": equity_rwa,
            "6_securitization": securitization_rwa,
            "7_market_risk": market_risk_rwa,
            "8_operational_risk": operational_risk_rwa,
            "9_floor_adjustment": floor_adjustment,
            "10_total_rwa": total_rwa,
        },
        "minimum_capital_requirements": {
            "1_credit_risk_sa": credit_risk_sa_rwa * 0.08,
            "2_credit_risk_irb": credit_risk_irb_rwa * 0.08,
            "3_ccr": ccr_rwa * 0.08,
            "4_cva": cva_rwa * 0.08,
            "5_equity_irb": equity_rwa * 0.08,
            "6_securitization": securitization_rwa * 0.08,
            "7_market_risk": market_risk_rwa * 0.08,
            "8_operational_risk": operational_risk_rwa * 0.08,
            "9_floor_adjustment": floor_adjustment * 0.08,
            "10_total": min_capital,
        },
        "breakdown_percentages": {
            "credit_risk": (total_credit_risk / total_rwa * 100) if total_rwa > 0 else 0,
            "market_risk": (market_risk_rwa / total_rwa * 100) if total_rwa > 0 else 0,
            "operational_risk": (operational_risk_rwa / total_rwa * 100) if total_rwa > 0 else 0,
            "other": ((ccr_rwa + cva_rwa + equity_rwa + securitization_rwa) / total_rwa * 100) if total_rwa > 0 else 0,
        },
    }

    return DisclosureData(
        template=DisclosureTemplate.OV1,
        reporting_date=date.today(),
        data=data,
    )


def generate_cr1_template(
    loans_defaulted: float,
    loans_non_defaulted: float,
    loans_allowances: float,
    securities_defaulted: float,
    securities_non_defaulted: float,
    securities_allowances: float,
    obs_defaulted: float,
    obs_non_defaulted: float,
    obs_allowances: float,
) -> DisclosureData:
    """
    Generate CR1 Credit Quality of Assets template.

    Args:
        loans_*: Loan exposure data
        securities_*: Debt securities data
        obs_*: Off-balance sheet exposure data

    Returns:
        DisclosureData for CR1 template
    """
    data = {
        "exposures": {
            "loans": {
                "defaulted": loans_defaulted,
                "non_defaulted": loans_non_defaulted,
                "allowances": loans_allowances,
                "net": loans_defaulted + loans_non_defaulted - loans_allowances,
            },
            "debt_securities": {
                "defaulted": securities_defaulted,
                "non_defaulted": securities_non_defaulted,
                "allowances": securities_allowances,
                "net": securities_defaulted + securities_non_defaulted - securities_allowances,
            },
            "off_balance_sheet": {
                "defaulted": obs_defaulted,
                "non_defaulted": obs_non_defaulted,
                "allowances": obs_allowances,
                "net": obs_defaulted + obs_non_defaulted - obs_allowances,
            },
        },
    }

    # Calculate totals
    total_defaulted = loans_defaulted + securities_defaulted + obs_defaulted
    total_non_defaulted = loans_non_defaulted + securities_non_defaulted + obs_non_defaulted
    total_allowances = loans_allowances + securities_allowances + obs_allowances

    data["totals"] = {
        "defaulted": total_defaulted,
        "non_defaulted": total_non_defaulted,
        "allowances": total_allowances,
        "net": total_defaulted + total_non_defaulted - total_allowances,
    }

    # Credit quality metrics
    total_gross = total_defaulted + total_non_defaulted
    data["metrics"] = {
        "npl_ratio": total_defaulted / total_gross if total_gross > 0 else 0,
        "coverage_ratio": total_allowances / total_defaulted if total_defaulted > 0 else 0,
    }

    return DisclosureData(
        template=DisclosureTemplate.CR1,
        reporting_date=date.today(),
        data=data,
    )


def generate_liq1_template(
    hqla_level1: float,
    hqla_level2a: float,
    hqla_level2b: float,
    retail_outflows: float,
    wholesale_outflows: float,
    secured_outflows: float,
    additional_outflows: float,
    retail_inflows: float,
    wholesale_inflows: float,
    secured_inflows: float,
) -> DisclosureData:
    """
    Generate LIQ1 LCR template.

    Args:
        hqla_*: High-quality liquid assets by level
        *_outflows: Cash outflow categories
        *_inflows: Cash inflow categories

    Returns:
        DisclosureData for LIQ1 template
    """
    # Apply haircuts
    hqla_total = (
        hqla_level1 * 1.0 +      # No haircut
        hqla_level2a * 0.85 +    # 15% haircut
        hqla_level2b * 0.50      # 50% haircut
    )

    # Total outflows
    total_outflows = (
        retail_outflows + wholesale_outflows +
        secured_outflows + additional_outflows
    )

    # Total inflows (capped at 75% of outflows)
    gross_inflows = retail_inflows + wholesale_inflows + secured_inflows
    capped_inflows = min(gross_inflows, total_outflows * 0.75)

    # Net outflows
    net_outflows = max(total_outflows - capped_inflows, total_outflows * 0.25)

    # LCR
    lcr = hqla_total / net_outflows if net_outflows > 0 else 0

    data = {
        "high_quality_liquid_assets": {
            "level_1": hqla_level1,
            "level_2a": hqla_level2a,
            "level_2a_after_haircut": hqla_level2a * 0.85,
            "level_2b": hqla_level2b,
            "level_2b_after_haircut": hqla_level2b * 0.50,
            "total_hqla": hqla_total,
        },
        "cash_outflows": {
            "retail_deposits": retail_outflows,
            "unsecured_wholesale": wholesale_outflows,
            "secured_funding": secured_outflows,
            "additional_requirements": additional_outflows,
            "total_outflows": total_outflows,
        },
        "cash_inflows": {
            "retail": retail_inflows,
            "wholesale": wholesale_inflows,
            "secured_lending": secured_inflows,
            "gross_inflows": gross_inflows,
            "capped_inflows": capped_inflows,
        },
        "lcr_calculation": {
            "total_hqla": hqla_total,
            "net_cash_outflows": net_outflows,
            "lcr": lcr,
            "lcr_percentage": lcr * 100,
            "minimum_requirement": 100,
            "surplus_deficit": (lcr - 1.0) * net_outflows,
        },
    }

    return DisclosureData(
        template=DisclosureTemplate.LIQ1,
        reporting_date=date.today(),
        data=data,
    )


def format_disclosure_for_publication(
    disclosure: DisclosureData,
    format_type: str = "table",
) -> str:
    """
    Format disclosure data for publication.

    Args:
        disclosure: Disclosure data to format
        format_type: 'table', 'json', or 'html'

    Returns:
        Formatted disclosure string
    """
    if format_type == "json":
        return json.dumps({
            "template": disclosure.template.value,
            "reporting_date": disclosure.reporting_date.isoformat(),
            "currency": disclosure.currency,
            "units": disclosure.units,
            "data": disclosure.data,
        }, indent=2)

    elif format_type == "table":
        lines = [
            f"Template: {disclosure.template.value}",
            f"Reporting Date: {disclosure.reporting_date}",
            f"Currency: {disclosure.currency} ({disclosure.units})",
            "-" * 50,
        ]

        def format_dict(d, indent=0):
            result = []
            for key, value in d.items():
                if isinstance(value, dict):
                    result.append("  " * indent + f"{key}:")
                    result.extend(format_dict(value, indent + 1))
                elif isinstance(value, float):
                    if key.endswith("ratio") or key.endswith("percentage") or key == "lcr":
                        result.append("  " * indent + f"{key}: {value:.2%}")
                    else:
                        result.append("  " * indent + f"{key}: {value:,.0f}")
                else:
                    result.append("  " * indent + f"{key}: {value}")
            return result

        lines.extend(format_dict(disclosure.data))
        return "\n".join(lines)

    return str(disclosure.data)


def generate_pillar3_report(
    bank_name: str,
    capital_data: Dict,
    rwa_data: Dict,
    credit_quality_data: Dict,
    liquidity_data: Dict,
) -> Pillar3Report:
    """
    Generate complete Pillar 3 report.

    Args:
        bank_name: Name of the reporting bank
        capital_data: Capital composition data
        rwa_data: RWA breakdown data
        credit_quality_data: Credit quality data
        liquidity_data: Liquidity data

    Returns:
        Complete Pillar3Report
    """
    report = Pillar3Report(
        bank_name=bank_name,
        reporting_date=date.today(),
    )

    # Generate KM1
    km1 = generate_km1_template(
        cet1_capital=capital_data.get("cet1", 0),
        at1_capital=capital_data.get("at1", 0),
        tier2_capital=capital_data.get("tier2", 0),
        total_rwa=rwa_data.get("total", 0),
        leverage_exposure=capital_data.get("leverage_exposure", 0),
        lcr=liquidity_data.get("lcr", 0),
        nsfr=liquidity_data.get("nsfr", 0),
    )
    report.disclosures.append(km1)

    # Generate OV1
    ov1 = generate_ov1_template(
        credit_risk_sa_rwa=rwa_data.get("credit_sa", 0),
        credit_risk_irb_rwa=rwa_data.get("credit_irb", 0),
        ccr_rwa=rwa_data.get("ccr", 0),
        cva_rwa=rwa_data.get("cva", 0),
        equity_rwa=rwa_data.get("equity", 0),
        securitization_rwa=rwa_data.get("securitization", 0),
        market_risk_rwa=rwa_data.get("market", 0),
        operational_risk_rwa=rwa_data.get("operational", 0),
        floor_adjustment=rwa_data.get("floor", 0),
    )
    report.disclosures.append(ov1)

    # Add qualitative disclosures
    report.qualitative_disclosures = {
        "risk_management_objectives": "Description of risk management objectives and policies...",
        "governance_structure": "Description of governance structure...",
        "scope_of_application": "Description of consolidation scope...",
    }

    return report


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("PILLAR 3 DISCLOSURE FRAMEWORK - EXAMPLES")
    print("=" * 70)

    # 1. KM1 Key Metrics
    print("\n1. KM1 - KEY METRICS TEMPLATE")
    print("-" * 40)

    km1 = generate_km1_template(
        cet1_capital=50_000,        # EUR 50bn
        at1_capital=5_000,          # EUR 5bn
        tier2_capital=10_000,       # EUR 10bn
        total_rwa=400_000,          # EUR 400bn
        leverage_exposure=1_200_000, # EUR 1.2tr
        lcr=1.35,                    # 135%
        nsfr=1.15,                   # 115%
    )

    print(format_disclosure_for_publication(km1))

    # 2. OV1 RWA Overview
    print("\n\n2. OV1 - OVERVIEW OF RWA")
    print("-" * 40)

    ov1 = generate_ov1_template(
        credit_risk_sa_rwa=100_000,
        credit_risk_irb_rwa=200_000,
        ccr_rwa=30_000,
        cva_rwa=10_000,
        equity_rwa=15_000,
        securitization_rwa=20_000,
        market_risk_rwa=25_000,
        operational_risk_rwa=50_000,
        floor_adjustment=5_000,
    )

    print(format_disclosure_for_publication(ov1))

    # 3. CR1 Credit Quality
    print("\n\n3. CR1 - CREDIT QUALITY OF ASSETS")
    print("-" * 40)

    cr1 = generate_cr1_template(
        loans_defaulted=5_000,
        loans_non_defaulted=500_000,
        loans_allowances=4_000,
        securities_defaulted=100,
        securities_non_defaulted=100_000,
        securities_allowances=50,
        obs_defaulted=500,
        obs_non_defaulted=150_000,
        obs_allowances=300,
    )

    print(format_disclosure_for_publication(cr1))

    # 4. LIQ1 LCR
    print("\n\n4. LIQ1 - LIQUIDITY COVERAGE RATIO")
    print("-" * 40)

    liq1 = generate_liq1_template(
        hqla_level1=100_000,
        hqla_level2a=20_000,
        hqla_level2b=10_000,
        retail_outflows=30_000,
        wholesale_outflows=50_000,
        secured_outflows=10_000,
        additional_outflows=15_000,
        retail_inflows=10_000,
        wholesale_inflows=20_000,
        secured_inflows=15_000,
    )

    print(format_disclosure_for_publication(liq1))

    # 5. Full Report Generation
    print("\n\n5. COMPLETE PILLAR 3 REPORT")
    print("-" * 40)

    report = generate_pillar3_report(
        bank_name="Example Bank AG",
        capital_data={
            "cet1": 50_000,
            "at1": 5_000,
            "tier2": 10_000,
            "leverage_exposure": 1_200_000,
        },
        rwa_data={
            "credit_sa": 100_000,
            "credit_irb": 200_000,
            "ccr": 30_000,
            "cva": 10_000,
            "equity": 15_000,
            "securitization": 20_000,
            "market": 25_000,
            "operational": 50_000,
            "floor": 5_000,
            "total": 455_000,
        },
        credit_quality_data={},
        liquidity_data={
            "lcr": 1.35,
            "nsfr": 1.15,
        },
    )

    print(f"Bank: {report.bank_name}")
    print(f"Reporting Date: {report.reporting_date}")
    print(f"Number of Disclosures: {len(report.disclosures)}")
    print(f"\nIncluded Templates:")
    for disc in report.disclosures:
        print(f"  - {disc.template.value}: {TEMPLATE_REQUIREMENTS.get(disc.template, {}).get('description', 'N/A')}")
