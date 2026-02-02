"""
Advanced Credit Risk Components - Basel III/IV
- Infrastructure Supporting Factor
- Purchased Receivables (Dilution Risk)
- Double Default Framework

Reference: BCBS d424 (December 2017), CRR2 (EU 2019/876)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import math

# For normal distribution
try:
    from scipy.stats import norm
except ImportError:
    # Fallback approximation
    class NormFallback:
        @staticmethod
        def ppf(p):
            # Approximation of inverse normal CDF
            if p <= 0:
                return -10
            if p >= 1:
                return 10
            if p == 0.5:
                return 0

            t = math.sqrt(-2 * math.log(min(p, 1-p)))
            c0, c1, c2 = 2.515517, 0.802853, 0.010328
            d1, d2, d3 = 1.432788, 0.189269, 0.001308
            result = t - (c0 + c1*t + c2*t**2) / (1 + d1*t + d2*t**2 + d3*t**3)
            return result if p > 0.5 else -result

        @staticmethod
        def cdf(x):
            # Approximation of normal CDF
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    norm = NormFallback()


# =============================================================================
# INFRASTRUCTURE SUPPORTING FACTOR
# =============================================================================

class InfrastructureType(Enum):
    """Types of qualifying infrastructure exposures."""
    PROJECT_FINANCE = "project_finance"
    PUBLIC_PRIVATE_PARTNERSHIP = "ppp"
    CORPORATE_INFRASTRUCTURE = "corporate_infrastructure"


# Infrastructure supporting factor (ISF) - reduces RWA by ~25%
INFRASTRUCTURE_SUPPORTING_FACTOR = 0.75  # Multiply RWA by 0.75 for qualifying exposures


# Qualifying criteria for infrastructure
QUALIFYING_CRITERIA = {
    "operational_requirements": [
        "Contractual arrangements providing protection for lenders",
        "Revenue predictability (take-or-pay, regulated tariffs, availability-based)",
        "Restrictions on activities that could be detrimental to lenders",
        "First priority security interest over project assets",
    ],
    "financial_requirements": [
        "Cash flows can be modelled with high degree of confidence",
        "Stress testing shows ability to meet financial obligations",
        "Reserve funds or other liquidity arrangements",
        "Equity funded before debt drawdown",
    ],
    "risk_mitigation": [
        "Construction risk appropriately mitigated",
        "Experienced sponsors and contractors",
        "Appropriate insurance coverage",
        "Political and legal risk managed",
    ],
}


@dataclass
class InfrastructureExposure:
    """Infrastructure exposure for ISF assessment."""
    exposure_id: str
    ead: float
    pd: float  # Probability of default
    lgd: float  # Loss given default
    maturity: float  # in years
    infrastructure_type: InfrastructureType
    is_operational: bool  # vs. construction phase
    has_take_or_pay: bool
    has_regulated_revenue: bool
    meets_financial_criteria: bool
    jurisdiction_oecd: bool  # OECD or equivalent


def check_infrastructure_eligibility(exposure: InfrastructureExposure) -> Dict:
    """
    Check if infrastructure exposure qualifies for supporting factor.

    EU CRR2 Article 501a criteria:
    - Exposure to entity operating infrastructure
    - Cash flows allow repayment
    - Cash flows predictable
    - Located in EU/EEA (or OECD equivalent)

    Args:
        exposure: Infrastructure exposure details

    Returns:
        Dict with eligibility result and criteria assessment
    """
    criteria_met = {
        "is_infrastructure": True,  # Assumed if passed as InfrastructureExposure
        "operational_phase": exposure.is_operational,
        "predictable_revenues": exposure.has_take_or_pay or exposure.has_regulated_revenue,
        "financial_criteria": exposure.meets_financial_criteria,
        "jurisdiction": exposure.jurisdiction_oecd,
    }

    # All criteria must be met for operational phase
    # Construction phase may qualify with additional conditions
    if exposure.is_operational:
        all_met = all(criteria_met.values())
    else:
        # Construction phase - stricter requirements
        construction_criteria = criteria_met.copy()
        construction_criteria["completion_guarantees"] = True  # Would need to verify
        all_met = all(construction_criteria.values())

    return {
        "is_eligible": all_met,
        "supporting_factor": INFRASTRUCTURE_SUPPORTING_FACTOR if all_met else 1.0,
        "criteria_assessment": criteria_met,
        "rwa_reduction": f"{(1 - INFRASTRUCTURE_SUPPORTING_FACTOR) * 100:.0f}%" if all_met else "0%",
    }


def calculate_infrastructure_rwa(
    exposure: InfrastructureExposure,
    approach: str = "firb",  # 'firb' or 'airb'
) -> Dict:
    """
    Calculate RWA for infrastructure exposure with supporting factor.

    Args:
        exposure: Infrastructure exposure
        approach: 'firb' or 'airb'

    Returns:
        Dict with RWA calculation
    """
    # Check eligibility
    eligibility = check_infrastructure_eligibility(exposure)
    isf = eligibility["supporting_factor"]

    # Calculate base RWA using IRB formula
    pd = max(exposure.pd, 0.0003)  # Floor at 3bps
    lgd = exposure.lgd
    m = exposure.maturity

    # Corporate correlation (infrastructure typically corporate)
    r = 0.12 * (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    r += 0.24 * (1 - (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)))

    # Maturity adjustment
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    maturity_adj = (1 + (m - 2.5) * b) / (1 - 1.5 * b)

    # Capital requirement (K)
    k = (
        lgd * norm.cdf(
            (1 / math.sqrt(1 - r)) * norm.ppf(pd) +
            math.sqrt(r / (1 - r)) * norm.ppf(0.999)
        ) - pd * lgd
    ) * maturity_adj

    # RWA without ISF
    rwa_base = k * 12.5 * exposure.ead

    # Apply ISF if eligible
    rwa_with_isf = rwa_base * isf

    return {
        "exposure_id": exposure.exposure_id,
        "ead": exposure.ead,
        "pd": exposure.pd,
        "lgd": exposure.lgd,
        "maturity": exposure.maturity,
        "correlation": r,
        "maturity_adjustment": maturity_adj,
        "capital_requirement_k": k,
        "rwa_base": rwa_base,
        "infrastructure_supporting_factor": isf,
        "rwa_with_isf": rwa_with_isf,
        "rwa_reduction": rwa_base - rwa_with_isf,
        "eligibility": eligibility,
    }


# =============================================================================
# PURCHASED RECEIVABLES - DILUTION RISK
# =============================================================================

@dataclass
class PurchasedReceivable:
    """Purchased receivable exposure."""
    receivable_id: str
    ead: float
    pd_default: float  # PD for default risk
    pd_dilution: float  # PD for dilution risk
    lgd_default: float
    lgd_dilution: float  # Typically 100% for dilution
    maturity: float
    is_corporate: bool  # vs. retail
    has_recourse_to_seller: bool
    recourse_amount: float  # Amount of recourse available


def calculate_dilution_risk_rwa(receivable: PurchasedReceivable) -> Dict:
    """
    Calculate RWA for dilution risk on purchased receivables.

    Dilution risk = risk that receivable amounts are reduced through
    cash or non-cash credits to obligor (returns, disputes, etc.)

    Under IRB, dilution risk treated similarly to default risk.

    Args:
        receivable: Purchased receivable details

    Returns:
        Dict with dilution risk RWA
    """
    # Dilution PD
    pd_d = max(receivable.pd_dilution, 0.0003)  # Floor

    # Dilution LGD - typically 100% but can be reduced by recourse
    lgd_d = receivable.lgd_dilution
    if receivable.has_recourse_to_seller:
        # Reduce LGD by recourse coverage
        recourse_coverage = min(receivable.recourse_amount / receivable.ead, 1.0)
        lgd_d = lgd_d * (1 - recourse_coverage)

    # Use 1-year maturity for dilution (short-term nature)
    m = 1.0

    # Correlation - use same formula as corporate/retail
    if receivable.is_corporate:
        r = 0.12 * (1 - math.exp(-50 * pd_d)) / (1 - math.exp(-50))
        r += 0.24 * (1 - (1 - math.exp(-50 * pd_d)) / (1 - math.exp(-50)))
    else:
        # Retail correlation
        r = 0.03 * (1 - math.exp(-35 * pd_d)) / (1 - math.exp(-35))
        r += 0.16 * (1 - (1 - math.exp(-35 * pd_d)) / (1 - math.exp(-35)))

    # Maturity adjustment
    b = (0.11852 - 0.05478 * math.log(pd_d)) ** 2
    maturity_adj = (1 + (m - 2.5) * b) / (1 - 1.5 * b)

    # Capital requirement (K) for dilution
    k_dilution = (
        lgd_d * norm.cdf(
            (1 / math.sqrt(1 - r)) * norm.ppf(pd_d) +
            math.sqrt(r / (1 - r)) * norm.ppf(0.999)
        ) - pd_d * lgd_d
    ) * maturity_adj

    k_dilution = max(k_dilution, 0)  # Floor at 0

    rwa_dilution = k_dilution * 12.5 * receivable.ead

    return {
        "receivable_id": receivable.receivable_id,
        "ead": receivable.ead,
        "pd_dilution": pd_d,
        "lgd_dilution_base": receivable.lgd_dilution,
        "lgd_dilution_adjusted": lgd_d,
        "recourse_reduction": receivable.lgd_dilution - lgd_d,
        "correlation": r,
        "maturity_adjustment": maturity_adj,
        "k_dilution": k_dilution,
        "rwa_dilution": rwa_dilution,
    }


def calculate_purchased_receivable_total_rwa(receivable: PurchasedReceivable) -> Dict:
    """
    Calculate total RWA for purchased receivable (default + dilution).

    Args:
        receivable: Purchased receivable

    Returns:
        Dict with total RWA breakdown
    """
    # Default risk RWA
    pd = max(receivable.pd_default, 0.0003)
    lgd = receivable.lgd_default
    m = receivable.maturity

    if receivable.is_corporate:
        r = 0.12 * (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
        r += 0.24 * (1 - (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)))
    else:
        r = 0.03 * (1 - math.exp(-35 * pd)) / (1 - math.exp(-35))
        r += 0.16 * (1 - (1 - math.exp(-35 * pd)) / (1 - math.exp(-35)))

    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    maturity_adj = (1 + (m - 2.5) * b) / (1 - 1.5 * b)

    k_default = (
        lgd * norm.cdf(
            (1 / math.sqrt(1 - r)) * norm.ppf(pd) +
            math.sqrt(r / (1 - r)) * norm.ppf(0.999)
        ) - pd * lgd
    ) * maturity_adj

    k_default = max(k_default, 0)
    rwa_default = k_default * 12.5 * receivable.ead

    # Dilution risk
    dilution_result = calculate_dilution_risk_rwa(receivable)
    rwa_dilution = dilution_result["rwa_dilution"]

    # Total RWA
    total_rwa = rwa_default + rwa_dilution

    return {
        "receivable_id": receivable.receivable_id,
        "ead": receivable.ead,
        "default_risk": {
            "pd": pd,
            "lgd": lgd,
            "k": k_default,
            "rwa": rwa_default,
        },
        "dilution_risk": {
            "pd": receivable.pd_dilution,
            "lgd": dilution_result["lgd_dilution_adjusted"],
            "k": dilution_result["k_dilution"],
            "rwa": rwa_dilution,
        },
        "total_rwa": total_rwa,
        "rwa_density": total_rwa / (receivable.ead * 12.5) if receivable.ead > 0 else 0,
    }


# =============================================================================
# DOUBLE DEFAULT FRAMEWORK
# =============================================================================

@dataclass
class GuaranteedExposure:
    """Exposure with guarantee for double default treatment."""
    exposure_id: str
    ead: float
    pd_obligor: float      # PD of underlying obligor
    pd_guarantor: float    # PD of guarantor
    lgd: float
    maturity: float
    guarantor_type: str    # 'sovereign', 'bank', 'corporate'


def calculate_double_default_pd(
    pd_obligor: float,
    pd_guarantor: float,
    correlation_factor: float = 0.50,
) -> float:
    """
    Calculate joint probability of double default.

    P(both default) = P(obligor defaults) × P(guarantor defaults | obligor defaults)

    Under Basel, conditional default probability is derived using
    correlation between obligor and guarantor.

    Args:
        pd_obligor: PD of obligor
        pd_guarantor: PD of guarantor
        correlation_factor: Correlation between obligor and guarantor defaults

    Returns:
        Joint default probability
    """
    # Simplified approach: assume correlation reduces benefit
    # Full formula uses bivariate normal distribution

    # Joint PD approximation
    # Under independence: pd_joint = pd_obligor * pd_guarantor
    # With correlation, we use conservative estimate

    pd_independent = pd_obligor * pd_guarantor

    # Correlation adjustment (higher correlation = less benefit)
    # Using simplified formula: pd_joint = pd_independent + rho * sqrt(pd_o * pd_g * (1-pd_o) * (1-pd_g))
    adjustment = correlation_factor * math.sqrt(
        pd_obligor * pd_guarantor * (1 - pd_obligor) * (1 - pd_guarantor)
    )

    pd_joint = pd_independent + adjustment

    # Floor and cap
    pd_joint = max(pd_joint, 0.0003)  # Regulatory floor
    pd_joint = min(pd_joint, pd_obligor)  # Cannot exceed obligor PD

    return pd_joint


def calculate_double_default_rwa(exposure: GuaranteedExposure) -> Dict:
    """
    Calculate RWA under double default framework.

    Double default applies to exposures where:
    - Guaranteed by eligible financial guarantor
    - Guarantor is externally rated
    - Guarantee meets CRM requirements

    Args:
        exposure: Guaranteed exposure

    Returns:
        Dict with double default RWA
    """
    # Determine correlation based on guarantor type
    correlation_factors = {
        "sovereign": 0.30,   # Lower correlation with sovereign
        "bank": 0.50,        # Moderate correlation with bank
        "corporate": 0.60,   # Higher correlation with corporate
    }

    correlation = correlation_factors.get(exposure.guarantor_type, 0.50)

    # Calculate double default PD
    pd_dd = calculate_double_default_pd(
        exposure.pd_obligor,
        exposure.pd_guarantor,
        correlation,
    )

    # Calculate RWA with double default PD
    lgd = exposure.lgd
    m = exposure.maturity

    # Corporate correlation formula (using double default PD)
    r = 0.12 * (1 - math.exp(-50 * pd_dd)) / (1 - math.exp(-50))
    r += 0.24 * (1 - (1 - math.exp(-50 * pd_dd)) / (1 - math.exp(-50)))

    # Maturity adjustment
    b = (0.11852 - 0.05478 * math.log(pd_dd)) ** 2
    maturity_adj = (1 + (m - 2.5) * b) / (1 - 1.5 * b)

    # Capital requirement with double default PD
    k_dd = (
        lgd * norm.cdf(
            (1 / math.sqrt(1 - r)) * norm.ppf(pd_dd) +
            math.sqrt(r / (1 - r)) * norm.ppf(0.999)
        ) - pd_dd * lgd
    ) * maturity_adj

    k_dd = max(k_dd, 0)
    rwa_dd = k_dd * 12.5 * exposure.ead

    # Compare with unguaranteed RWA (using obligor PD)
    pd_ob = max(exposure.pd_obligor, 0.0003)
    r_ob = 0.12 * (1 - math.exp(-50 * pd_ob)) / (1 - math.exp(-50))
    r_ob += 0.24 * (1 - (1 - math.exp(-50 * pd_ob)) / (1 - math.exp(-50)))

    b_ob = (0.11852 - 0.05478 * math.log(pd_ob)) ** 2
    maturity_adj_ob = (1 + (m - 2.5) * b_ob) / (1 - 1.5 * b_ob)

    k_ob = (
        lgd * norm.cdf(
            (1 / math.sqrt(1 - r_ob)) * norm.ppf(pd_ob) +
            math.sqrt(r_ob / (1 - r_ob)) * norm.ppf(0.999)
        ) - pd_ob * lgd
    ) * maturity_adj_ob

    rwa_unguaranteed = max(k_ob, 0) * 12.5 * exposure.ead

    return {
        "exposure_id": exposure.exposure_id,
        "ead": exposure.ead,
        "pd_obligor": exposure.pd_obligor,
        "pd_guarantor": exposure.pd_guarantor,
        "pd_double_default": pd_dd,
        "correlation_factor": correlation,
        "lgd": lgd,
        "maturity": exposure.maturity,
        "k_double_default": k_dd,
        "rwa_double_default": rwa_dd,
        "rwa_unguaranteed": rwa_unguaranteed,
        "rwa_reduction": rwa_unguaranteed - rwa_dd,
        "reduction_percent": (rwa_unguaranteed - rwa_dd) / rwa_unguaranteed if rwa_unguaranteed > 0 else 0,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("ADVANCED CREDIT RISK COMPONENTS - EXAMPLES")
    print("=" * 70)

    # 1. Infrastructure Supporting Factor
    print("\n1. INFRASTRUCTURE SUPPORTING FACTOR")
    print("-" * 40)

    infra_exposure = InfrastructureExposure(
        exposure_id="INFRA001",
        ead=50_000_000,
        pd=0.01,  # 1%
        lgd=0.35,
        maturity=7,
        infrastructure_type=InfrastructureType.PROJECT_FINANCE,
        is_operational=True,
        has_take_or_pay=True,
        has_regulated_revenue=False,
        meets_financial_criteria=True,
        jurisdiction_oecd=True,
    )

    infra_result = calculate_infrastructure_rwa(infra_exposure)

    print(f"Exposure: EUR {infra_result['ead']:,.0f}")
    print(f"PD: {infra_result['pd']:.2%}")
    print(f"LGD: {infra_result['lgd']:.2%}")
    print(f"Eligible for ISF: {infra_result['eligibility']['is_eligible']}")
    print(f"Supporting Factor: {infra_result['infrastructure_supporting_factor']:.2f}")
    print(f"\nRWA without ISF: EUR {infra_result['rwa_base']:,.0f}")
    print(f"RWA with ISF: EUR {infra_result['rwa_with_isf']:,.0f}")
    print(f"RWA Reduction: EUR {infra_result['rwa_reduction']:,.0f} ({infra_result['eligibility']['rwa_reduction']})")

    # 2. Purchased Receivables - Dilution Risk
    print("\n\n2. PURCHASED RECEIVABLES - DILUTION RISK")
    print("-" * 40)

    receivable = PurchasedReceivable(
        receivable_id="RCV001",
        ead=10_000_000,
        pd_default=0.02,      # 2% default risk
        pd_dilution=0.05,     # 5% dilution risk
        lgd_default=0.40,
        lgd_dilution=1.00,    # 100% loss if diluted
        maturity=0.5,
        is_corporate=True,
        has_recourse_to_seller=True,
        recourse_amount=2_000_000,  # 20% recourse
    )

    recv_result = calculate_purchased_receivable_total_rwa(receivable)

    print(f"Receivable Amount: EUR {recv_result['ead']:,.0f}")
    print(f"\nDefault Risk:")
    print(f"  PD: {recv_result['default_risk']['pd']:.2%}")
    print(f"  LGD: {recv_result['default_risk']['lgd']:.2%}")
    print(f"  K: {recv_result['default_risk']['k']:.4f}")
    print(f"  RWA: EUR {recv_result['default_risk']['rwa']:,.0f}")

    print(f"\nDilution Risk:")
    print(f"  PD: {recv_result['dilution_risk']['pd']:.2%}")
    print(f"  LGD (adjusted for recourse): {recv_result['dilution_risk']['lgd']:.2%}")
    print(f"  K: {recv_result['dilution_risk']['k']:.4f}")
    print(f"  RWA: EUR {recv_result['dilution_risk']['rwa']:,.0f}")

    print(f"\nTotal RWA: EUR {recv_result['total_rwa']:,.0f}")
    print(f"RWA Density: {recv_result['rwa_density']:.2%}")

    # 3. Double Default Framework
    print("\n\n3. DOUBLE DEFAULT FRAMEWORK")
    print("-" * 40)

    guaranteed_exp = GuaranteedExposure(
        exposure_id="GUAR001",
        ead=20_000_000,
        pd_obligor=0.05,       # 5% obligor PD
        pd_guarantor=0.002,    # 0.2% guarantor PD (bank)
        lgd=0.45,
        maturity=3,
        guarantor_type="bank",
    )

    dd_result = calculate_double_default_rwa(guaranteed_exp)

    print(f"Exposure: EUR {dd_result['ead']:,.0f}")
    print(f"Obligor PD: {dd_result['pd_obligor']:.2%}")
    print(f"Guarantor PD: {dd_result['pd_guarantor']:.2%}")
    print(f"Correlation Factor: {dd_result['correlation_factor']:.2f}")
    print(f"Double Default PD: {dd_result['pd_double_default']:.4%}")

    print(f"\nRWA without guarantee: EUR {dd_result['rwa_unguaranteed']:,.0f}")
    print(f"RWA with double default: EUR {dd_result['rwa_double_default']:,.0f}")
    print(f"RWA Reduction: EUR {dd_result['rwa_reduction']:,.0f} ({dd_result['reduction_percent']:.1%})")

    # Compare different guarantor types
    print("\n\n4. DOUBLE DEFAULT - GUARANTOR TYPE COMPARISON")
    print("-" * 40)

    for guarantor_type in ["sovereign", "bank", "corporate"]:
        exp = GuaranteedExposure(
            exposure_id=f"GUAR_{guarantor_type}",
            ead=20_000_000,
            pd_obligor=0.05,
            pd_guarantor=0.002,
            lgd=0.45,
            maturity=3,
            guarantor_type=guarantor_type,
        )
        result = calculate_double_default_rwa(exp)
        print(f"\n{guarantor_type.upper()} Guarantor:")
        print(f"  Correlation: {result['correlation_factor']:.2f}")
        print(f"  DD PD: {result['pd_double_default']:.4%}")
        print(f"  RWA: EUR {result['rwa_double_default']:,.0f}")
        print(f"  Reduction: {result['reduction_percent']:.1%}")
