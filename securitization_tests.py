"""
Securitization Tests - Basel III/IV
- STC (Simple, Transparent and Comparable) Criteria Checker
- SRT (Significant Risk Transfer) Test

Reference: BCBS d374 (July 2016), BCBS d400 (July 2017)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import date


# =============================================================================
# STC CRITERIA CHECKER
# =============================================================================

class STCCategory(Enum):
    """STC criteria categories."""
    SIMPLICITY = "simplicity"
    TRANSPARENCY = "transparency"
    COMPARABILITY = "comparability"


# STC criteria by category (BCBS d374)
STC_CRITERIA = {
    STCCategory.SIMPLICITY: {
        "S1": "Nature of assets - homogeneous pool, clear characteristics",
        "S2": "Asset performance history - historical data available",
        "S3": "Payment status - no defaulted assets at origination",
        "S4": "Consistency of underwriting - prudent standards applied",
        "S5": "Asset selection - no cherry-picking, clear eligibility criteria",
        "S6": "No synthetic structures or residual value dependence",
    },
    STCCategory.TRANSPARENCY: {
        "T1": "Data on historical performance - pool and comparable assets",
        "T2": "Liability data - cash flow model available to investors",
        "T3": "Pre-pricing disclosure - draft prospectus before pricing",
        "T4": "Post-issuance disclosure - ongoing reporting to investors",
    },
    STCCategory.COMPARABILITY: {
        "C1": "Risk retention - originator retains material net economic interest",
        "C2": "Interest rate and currency risks - hedged appropriately",
        "C3": "Referenced interest payments - based on market interest rates",
        "C4": "Post-enforcement priorities - clear, disclosed waterfall",
        "C5": "Voting rights - defined triggers for enforcement actions",
        "C6": "Documentation - standard representations and warranties",
    },
}


# RWA cap reductions for STC-compliant transactions
STC_RWA_BENEFITS = {
    "sec_sa": {
        "non_stc_floor": 0.15,   # 15% RW floor
        "stc_floor": 0.10,      # 10% RW floor for STC
    },
    "sec_irba": {
        "non_stc_floor": 0.15,
        "stc_floor": 0.10,
    },
    "sec_erba": {
        "non_stc_floor": 0.15,
        "stc_floor": 0.10,
    },
}


@dataclass
class STCAssessment:
    """Assessment of STC criteria for a securitization."""
    transaction_id: str
    asset_class: str  # RMBS, auto loans, consumer credit, etc.
    origination_date: date
    criteria_met: Dict[str, bool] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)


def initialize_stc_assessment(transaction_id: str, asset_class: str) -> STCAssessment:
    """
    Initialize an STC assessment with all criteria set to False.

    Args:
        transaction_id: Unique transaction identifier
        asset_class: Asset class of the securitization

    Returns:
        Initialized STCAssessment
    """
    criteria_met = {}
    for category in STCCategory:
        for criterion_id in STC_CRITERIA[category].keys():
            criteria_met[criterion_id] = False

    return STCAssessment(
        transaction_id=transaction_id,
        asset_class=asset_class,
        origination_date=date.today(),
        criteria_met=criteria_met,
        notes={},
    )


def assess_simplicity_criteria(
    assessment: STCAssessment,
    pool_homogeneous: bool,
    has_performance_history: bool,
    no_defaulted_at_cutoff: bool,
    consistent_underwriting: bool,
    clear_selection_criteria: bool,
    no_synthetic_features: bool,
) -> STCAssessment:
    """
    Assess simplicity criteria for STC designation.

    Args:
        assessment: Current assessment
        pool_homogeneous: Pool consists of homogeneous assets
        has_performance_history: Historical performance data available
        no_defaulted_at_cutoff: No defaulted assets at cut-off date
        consistent_underwriting: Consistent underwriting standards
        clear_selection_criteria: Clear eligibility criteria for pool
        no_synthetic_features: No synthetic structures or derivatives

    Returns:
        Updated assessment
    """
    assessment.criteria_met["S1"] = pool_homogeneous
    assessment.criteria_met["S2"] = has_performance_history
    assessment.criteria_met["S3"] = no_defaulted_at_cutoff
    assessment.criteria_met["S4"] = consistent_underwriting
    assessment.criteria_met["S5"] = clear_selection_criteria
    assessment.criteria_met["S6"] = no_synthetic_features

    return assessment


def assess_transparency_criteria(
    assessment: STCAssessment,
    historical_data_available: bool,
    cash_flow_model_available: bool,
    pre_pricing_disclosure: bool,
    ongoing_reporting: bool,
) -> STCAssessment:
    """
    Assess transparency criteria for STC designation.

    Args:
        assessment: Current assessment
        historical_data_available: Historical performance data available
        cash_flow_model_available: Liability cash flow model provided
        pre_pricing_disclosure: Draft prospectus before pricing
        ongoing_reporting: Ongoing investor reporting in place

    Returns:
        Updated assessment
    """
    assessment.criteria_met["T1"] = historical_data_available
    assessment.criteria_met["T2"] = cash_flow_model_available
    assessment.criteria_met["T3"] = pre_pricing_disclosure
    assessment.criteria_met["T4"] = ongoing_reporting

    return assessment


def assess_comparability_criteria(
    assessment: STCAssessment,
    risk_retention_met: bool,
    risks_hedged: bool,
    market_interest_rates: bool,
    clear_waterfall: bool,
    defined_voting_rights: bool,
    standard_documentation: bool,
) -> STCAssessment:
    """
    Assess comparability criteria for STC designation.

    Args:
        assessment: Current assessment
        risk_retention_met: Originator retains 5%+ net economic interest
        risks_hedged: Interest rate/FX risks appropriately hedged
        market_interest_rates: Payments based on market rates
        clear_waterfall: Post-enforcement waterfall clearly defined
        defined_voting_rights: Voting rights and triggers defined
        standard_documentation: Standard representations and warranties

    Returns:
        Updated assessment
    """
    assessment.criteria_met["C1"] = risk_retention_met
    assessment.criteria_met["C2"] = risks_hedged
    assessment.criteria_met["C3"] = market_interest_rates
    assessment.criteria_met["C4"] = clear_waterfall
    assessment.criteria_met["C5"] = defined_voting_rights
    assessment.criteria_met["C6"] = standard_documentation

    return assessment


def evaluate_stc_compliance(assessment: STCAssessment) -> Dict:
    """
    Evaluate overall STC compliance based on criteria assessment.

    Args:
        assessment: Completed STC assessment

    Returns:
        Dict with compliance result and breakdown
    """
    # Count criteria by category
    category_results = {}
    for category in STCCategory:
        category_criteria = [k for k in STC_CRITERIA[category].keys()]
        met_count = sum(1 for c in category_criteria if assessment.criteria_met.get(c, False))
        total_count = len(category_criteria)
        category_results[category.value] = {
            "met": met_count,
            "total": total_count,
            "fully_compliant": met_count == total_count,
        }

    # Overall compliance requires ALL criteria met
    all_criteria_met = all(assessment.criteria_met.values())

    # Identify failed criteria
    failed_criteria = [
        {"id": k, "description": get_criterion_description(k)}
        for k, v in assessment.criteria_met.items() if not v
    ]

    return {
        "transaction_id": assessment.transaction_id,
        "asset_class": assessment.asset_class,
        "is_stc_compliant": all_criteria_met,
        "category_results": category_results,
        "total_criteria": len(assessment.criteria_met),
        "criteria_met_count": sum(assessment.criteria_met.values()),
        "failed_criteria": failed_criteria,
        "rwa_floor_benefit": STC_RWA_BENEFITS["sec_sa"]["stc_floor"] if all_criteria_met else STC_RWA_BENEFITS["sec_sa"]["non_stc_floor"],
        "notes": assessment.notes,
    }


def get_criterion_description(criterion_id: str) -> str:
    """Get description for a criterion ID."""
    for category in STCCategory:
        if criterion_id in STC_CRITERIA[category]:
            return STC_CRITERIA[category][criterion_id]
    return "Unknown criterion"


# =============================================================================
# SIGNIFICANT RISK TRANSFER (SRT) TEST
# =============================================================================

@dataclass
class SecuritizationTranche:
    """A tranche in a securitization structure."""
    tranche_id: str
    attachment_point: float  # e.g., 0.00 for equity
    detachment_point: float  # e.g., 0.05 for 0-5% tranche
    principal_amount: float
    is_retained: bool
    thickness: float = 0.0  # Will be calculated

    def __post_init__(self):
        self.thickness = self.detachment_point - self.attachment_point


@dataclass
class SRTAssessment:
    """Assessment data for SRT test."""
    transaction_id: str
    total_pool_amount: float
    pool_rwa_if_not_securitized: float  # RWA if bank held directly
    tranches: List[SecuritizationTranche]
    first_loss_retention: float  # % of first loss retained
    mezzanine_retention: float   # % of mezzanine retained


# SRT thresholds per Basel framework
SRT_THRESHOLDS = {
    "traditional": {
        "capital_reduction_commensurate": True,
        "min_risk_transfer": 0.50,  # 50% of risk transferred
    },
    "synthetic": {
        "funded_protection": True,
        "unfunded_eligible_provider": True,
        "min_risk_transfer": 0.50,
    },
    # Quantitative test thresholds
    "quantitative": {
        "significant_risk_ratio": 0.50,  # 50% of RWA reduction
        "vertical_slice_max_retention": 0.20,  # Max 20% vertical
        "first_loss_max_exposure": 0.20,  # Max 20% first loss exposure
    },
}


def calculate_kirb_floor(
    pd_pool: float,
    lgd_pool: float,
    maturity: float = 2.5,
) -> float:
    """
    Calculate Kirb (IRB capital if pool held directly).

    Args:
        pd_pool: Weighted average PD of pool
        lgd_pool: Weighted average LGD of pool
        maturity: Weighted average maturity

    Returns:
        Kirb as decimal
    """
    import math

    pd = max(pd_pool, 0.0003)
    lgd = lgd_pool

    # Correlation (corporate)
    r = 0.12 * (1 - math.exp(-50 * pd)) / (1 - math.exp(-50))
    r += 0.24 * (1 - (1 - math.exp(-50 * pd)) / (1 - math.exp(-50)))

    # Maturity adjustment
    b = (0.11852 - 0.05478 * math.log(pd)) ** 2
    maturity_adj = (1 + (maturity - 2.5) * b) / (1 - 1.5 * b)

    # Normal distribution
    try:
        from scipy.stats import norm
    except ImportError:
        return 0.08  # Default fallback

    k = (
        lgd * norm.cdf(
            (1 / math.sqrt(1 - r)) * norm.ppf(pd) +
            math.sqrt(r / (1 - r)) * norm.ppf(0.999)
        ) - pd * lgd
    ) * maturity_adj

    return max(k, 0)


def calculate_retained_risk(
    assessment: SRTAssessment,
) -> Dict:
    """
    Calculate the risk retained by the originator.

    Args:
        assessment: SRT assessment data

    Returns:
        Dict with retained risk breakdown
    """
    retained_tranches = [t for t in assessment.tranches if t.is_retained]
    sold_tranches = [t for t in assessment.tranches if not t.is_retained]

    # Calculate retained amounts
    retained_principal = sum(t.principal_amount for t in retained_tranches)
    sold_principal = sum(t.principal_amount for t in sold_tranches)
    total_principal = sum(t.principal_amount for t in assessment.tranches)

    # First loss analysis
    first_loss_tranches = [t for t in assessment.tranches if t.attachment_point == 0]
    first_loss_retained = sum(
        t.principal_amount for t in first_loss_tranches if t.is_retained
    )
    total_first_loss = sum(t.principal_amount for t in first_loss_tranches)

    # Calculate risk weights for retained tranches (simplified)
    # In practice, would use SEC-IRBA or SEC-SA formulas
    retained_risk_weighted = sum(
        t.principal_amount * (1 - t.attachment_point)  # Higher risk for lower tranches
        for t in retained_tranches
    )

    return {
        "retained_principal": retained_principal,
        "sold_principal": sold_principal,
        "total_principal": total_principal,
        "retention_ratio": retained_principal / total_principal if total_principal > 0 else 0,
        "first_loss_retained": first_loss_retained,
        "total_first_loss": total_first_loss,
        "first_loss_retention_ratio": first_loss_retained / total_first_loss if total_first_loss > 0 else 0,
        "retained_risk_weighted": retained_risk_weighted,
    }


def perform_srt_quantitative_test(
    assessment: SRTAssessment,
    pd_pool: float,
    lgd_pool: float,
) -> Dict:
    """
    Perform quantitative SRT test.

    Banks must demonstrate that the securitization achieves
    significant transfer of credit risk to third parties.

    Tests:
    1. RWA reduction is commensurate with risk transferred
    2. Retained positions don't undermine risk transfer
    3. No implicit support arrangements

    Args:
        assessment: SRT assessment data
        pd_pool: Pool PD
        lgd_pool: Pool LGD

    Returns:
        Dict with test results
    """
    # Calculate Kirb
    kirb = calculate_kirb_floor(pd_pool, lgd_pool)

    # RWA if held directly
    rwa_if_held = assessment.pool_rwa_if_not_securitized

    # Calculate retained risk
    retained = calculate_retained_risk(assessment)

    # Estimate RWA for retained positions
    # Simplified: use thickness-based approach
    rwa_retained = 0
    for tranche in assessment.tranches:
        if tranche.is_retained:
            # Higher capital for lower tranches
            if tranche.attachment_point < kirb:
                # Below Kirb - high capital charge
                rw = min(1250, 1250 * (kirb - tranche.attachment_point) / kirb)
            else:
                # Above Kirb - standard RW based on thickness
                rw = 100 + (1000 * tranche.thickness)
            rwa_retained += tranche.principal_amount * rw / 100 * 12.5

    # Risk transfer ratio
    risk_transferred = (rwa_if_held - rwa_retained) / rwa_if_held if rwa_if_held > 0 else 0

    # Test criteria
    thresholds = SRT_THRESHOLDS["quantitative"]

    tests_passed = {
        "significant_risk_transfer": risk_transferred >= thresholds["significant_risk_ratio"],
        "first_loss_test": retained["first_loss_retention_ratio"] <= thresholds["first_loss_max_exposure"],
        "vertical_slice_test": retained["retention_ratio"] <= thresholds["vertical_slice_max_retention"],
    }

    # SRT achieved if risk transfer test passed (main criterion)
    srt_achieved = tests_passed["significant_risk_transfer"]

    return {
        "transaction_id": assessment.transaction_id,
        "kirb": kirb,
        "rwa_if_held_directly": rwa_if_held,
        "rwa_retained_positions": rwa_retained,
        "risk_transfer_ratio": risk_transferred,
        "retained_analysis": retained,
        "tests_passed": tests_passed,
        "srt_achieved": srt_achieved,
        "capital_relief_available": srt_achieved,
        "estimated_capital_relief": (rwa_if_held - rwa_retained) * 0.08 if srt_achieved else 0,
    }


def check_srt_qualitative_requirements(
    has_clean_sale: bool,
    no_implicit_support: bool,
    no_call_options_before_maturity: bool,
    adequate_disclosure: bool,
    third_party_verification: bool,
) -> Dict:
    """
    Check qualitative SRT requirements.

    Args:
        has_clean_sale: True sale achieved (legal opinion)
        no_implicit_support: No implicit support arrangements
        no_call_options_before_maturity: Clean-up call only
        adequate_disclosure: Appropriate disclosure to investors
        third_party_verification: Independent verification of structure

    Returns:
        Dict with qualitative test results
    """
    requirements = {
        "clean_sale": has_clean_sale,
        "no_implicit_support": no_implicit_support,
        "call_options": no_call_options_before_maturity,
        "disclosure": adequate_disclosure,
        "verification": third_party_verification,
    }

    all_met = all(requirements.values())

    return {
        "requirements_met": requirements,
        "qualitative_pass": all_met,
        "failed_requirements": [k for k, v in requirements.items() if not v],
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("SECURITIZATION TESTS - EXAMPLES")
    print("=" * 70)

    # 1. STC Criteria Check
    print("\n1. STC CRITERIA ASSESSMENT")
    print("-" * 40)

    assessment = initialize_stc_assessment("RMBS-2024-001", "RMBS")

    # Assess simplicity
    assessment = assess_simplicity_criteria(
        assessment,
        pool_homogeneous=True,
        has_performance_history=True,
        no_defaulted_at_cutoff=True,
        consistent_underwriting=True,
        clear_selection_criteria=True,
        no_synthetic_features=True,
    )

    # Assess transparency
    assessment = assess_transparency_criteria(
        assessment,
        historical_data_available=True,
        cash_flow_model_available=True,
        pre_pricing_disclosure=True,
        ongoing_reporting=True,
    )

    # Assess comparability
    assessment = assess_comparability_criteria(
        assessment,
        risk_retention_met=True,
        risks_hedged=True,
        market_interest_rates=True,
        clear_waterfall=True,
        defined_voting_rights=True,
        standard_documentation=True,
    )

    stc_result = evaluate_stc_compliance(assessment)

    print(f"Transaction: {stc_result['transaction_id']}")
    print(f"Asset Class: {stc_result['asset_class']}")
    print(f"\nSTC Compliant: {stc_result['is_stc_compliant']}")
    print(f"Criteria Met: {stc_result['criteria_met_count']}/{stc_result['total_criteria']}")

    print(f"\nCategory Results:")
    for cat, results in stc_result['category_results'].items():
        status = "✓" if results['fully_compliant'] else "✗"
        print(f"  {cat.capitalize()}: {results['met']}/{results['total']} {status}")

    if stc_result['failed_criteria']:
        print(f"\nFailed Criteria:")
        for fc in stc_result['failed_criteria']:
            print(f"  - {fc['id']}: {fc['description']}")

    print(f"\nRWA Floor: {stc_result['rwa_floor_benefit']:.0%}")

    # 2. SRT Test
    print("\n\n2. SIGNIFICANT RISK TRANSFER TEST")
    print("-" * 40)

    tranches = [
        SecuritizationTranche("Equity", 0.00, 0.05, 5_000_000, is_retained=True),
        SecuritizationTranche("Mezz-B", 0.05, 0.10, 5_000_000, is_retained=True),
        SecuritizationTranche("Mezz-A", 0.10, 0.20, 10_000_000, is_retained=False),
        SecuritizationTranche("Senior", 0.20, 1.00, 80_000_000, is_retained=False),
    ]

    srt_assessment = SRTAssessment(
        transaction_id="CLO-2024-001",
        total_pool_amount=100_000_000,
        pool_rwa_if_not_securitized=70_000_000,  # 70% RW density
        tranches=tranches,
        first_loss_retention=1.0,  # 100% of first loss retained
        mezzanine_retention=0.5,   # 50% of mezzanine retained
    )

    srt_result = perform_srt_quantitative_test(
        srt_assessment,
        pd_pool=0.02,   # 2% pool PD
        lgd_pool=0.40,  # 40% pool LGD
    )

    print(f"Transaction: {srt_result['transaction_id']}")
    print(f"Pool Kirb: {srt_result['kirb']:.2%}")
    print(f"\nRWA if held directly: EUR {srt_result['rwa_if_held_directly']:,.0f}")
    print(f"RWA for retained: EUR {srt_result['rwa_retained_positions']:,.0f}")
    print(f"Risk Transfer Ratio: {srt_result['risk_transfer_ratio']:.1%}")

    print(f"\nRetained Position Analysis:")
    print(f"  Retention Ratio: {srt_result['retained_analysis']['retention_ratio']:.1%}")
    print(f"  First Loss Retention: {srt_result['retained_analysis']['first_loss_retention_ratio']:.1%}")

    print(f"\nTest Results:")
    for test, passed in srt_result['tests_passed'].items():
        status = "✓ Pass" if passed else "✗ Fail"
        print(f"  {test.replace('_', ' ').title()}: {status}")

    print(f"\nSRT Achieved: {srt_result['srt_achieved']}")
    print(f"Capital Relief Available: {srt_result['capital_relief_available']}")
    if srt_result['capital_relief_available']:
        print(f"Estimated Capital Relief: EUR {srt_result['estimated_capital_relief']:,.0f}")

    # 3. Qualitative Requirements
    print("\n\n3. SRT QUALITATIVE REQUIREMENTS")
    print("-" * 40)

    qual_result = check_srt_qualitative_requirements(
        has_clean_sale=True,
        no_implicit_support=True,
        no_call_options_before_maturity=True,
        adequate_disclosure=True,
        third_party_verification=True,
    )

    print("Requirements Check:")
    for req, met in qual_result['requirements_met'].items():
        status = "✓" if met else "✗"
        print(f"  {req.replace('_', ' ').title()}: {status}")

    print(f"\nQualitative Pass: {qual_result['qualitative_pass']}")

    # Combined result
    print("\n\n4. OVERALL SRT DETERMINATION")
    print("-" * 40)
    overall_srt = srt_result['srt_achieved'] and qual_result['qualitative_pass']
    print(f"Quantitative Test: {'Pass' if srt_result['srt_achieved'] else 'Fail'}")
    print(f"Qualitative Test: {'Pass' if qual_result['qualitative_pass'] else 'Fail'}")
    print(f"\nOVERALL SRT STATUS: {'ACHIEVED' if overall_srt else 'NOT ACHIEVED'}")
