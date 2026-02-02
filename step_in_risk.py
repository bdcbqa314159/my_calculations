"""
Step-In Risk Framework - Basel III/IV
BCBS 398 (October 2017)

Step-in risk: Risk that a bank may provide financial support to
an unconsolidated entity beyond contractual obligations, due to
reputational concerns or implicit commitments.

Key Components:
- Identification of entities with step-in risk
- Assessment of step-in indicators
- Capital and liquidity impact assessment
- Disclosure requirements

Reference: BCBS 398 - Guidelines on Step-in Risk
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import date


class EntityType(Enum):
    """Types of entities subject to step-in risk assessment."""
    SECURITIZATION_VEHICLE = "securitization_vehicle"
    INVESTMENT_FUND = "investment_fund"
    MONEY_MARKET_FUND = "mmf"
    PENSION_FUND = "pension_fund"
    STRUCTURED_ENTITY = "structured_entity"
    CONDUIT = "conduit"
    JOINT_VENTURE = "joint_venture"
    ASSOCIATE = "associate"
    OTHER_SPV = "other_spv"


class StepInIndicator(Enum):
    """Indicators that may suggest step-in risk."""
    SPONSORSHIP = "sponsorship"              # Bank sponsors the entity
    IMPLICIT_SUPPORT = "implicit_support"    # Past support or market expectation
    INVOLVEMENT = "involvement"              # Degree of involvement in entity
    REPUTATION = "reputation"                # Reputational impact of failure
    INVESTOR_EXPECTATIONS = "investor_expectations"
    NAME_ASSOCIATION = "name_association"    # Entity uses bank's name
    CREDIT_ENHANCEMENT = "credit_enhancement"
    LIQUIDITY_SUPPORT = "liquidity_support"
    REVENUE_DEPENDENCE = "revenue_dependence"


# Step-in risk indicator weights
INDICATOR_WEIGHTS = {
    StepInIndicator.SPONSORSHIP: 0.20,
    StepInIndicator.IMPLICIT_SUPPORT: 0.25,
    StepInIndicator.INVOLVEMENT: 0.10,
    StepInIndicator.REPUTATION: 0.15,
    StepInIndicator.INVESTOR_EXPECTATIONS: 0.15,
    StepInIndicator.NAME_ASSOCIATION: 0.05,
    StepInIndicator.CREDIT_ENHANCEMENT: 0.05,
    StepInIndicator.LIQUIDITY_SUPPORT: 0.03,
    StepInIndicator.REVENUE_DEPENDENCE: 0.02,
}


# Capital treatment based on step-in risk level
CAPITAL_TREATMENT = {
    "high": {
        "approach": "full_consolidation",
        "description": "Full consolidation or equivalent capital treatment",
        "capital_charge_factor": 1.0,
    },
    "medium": {
        "approach": "proportional",
        "description": "Proportional capital charge based on exposure",
        "capital_charge_factor": 0.5,
    },
    "low": {
        "approach": "monitoring",
        "description": "Monitoring and disclosure only",
        "capital_charge_factor": 0.0,
    },
}


@dataclass
class UnconsolidatedEntity:
    """An unconsolidated entity subject to step-in risk assessment."""
    entity_id: str
    entity_name: str
    entity_type: EntityType
    total_assets: float
    is_sponsored: bool
    uses_bank_name: bool
    contractual_exposure: float  # Direct exposure (loans, facilities)
    ownership_percentage: float
    provides_services: bool  # Bank provides services to entity
    past_support_provided: bool
    creation_date: Optional[date] = None


@dataclass
class StepInAssessment:
    """Assessment of step-in risk for an entity."""
    entity: UnconsolidatedEntity
    indicator_scores: Dict[StepInIndicator, float] = field(default_factory=dict)
    overall_score: float = 0.0
    risk_level: str = "low"
    notes: List[str] = field(default_factory=list)


def assess_step_in_indicators(
    entity: UnconsolidatedEntity,
    has_implicit_support_expectation: bool = False,
    involvement_level: float = 0.0,  # 0-1 scale
    reputational_impact: float = 0.0,  # 0-1 scale
    investor_expectation_level: float = 0.0,  # 0-1 scale
    provides_credit_enhancement: bool = False,
    provides_liquidity_support: bool = False,
    revenue_from_entity_significant: bool = False,
) -> StepInAssessment:
    """
    Assess step-in risk indicators for an entity.

    Args:
        entity: The unconsolidated entity
        has_implicit_support_expectation: Market expects bank to support
        involvement_level: Degree of bank's involvement (0-1)
        reputational_impact: Impact if entity fails (0-1)
        investor_expectation_level: Investor expectation of support (0-1)
        provides_credit_enhancement: Bank provides credit enhancement
        provides_liquidity_support: Bank provides liquidity facilities
        revenue_from_entity_significant: Significant revenue from entity

    Returns:
        StepInAssessment with scored indicators
    """
    assessment = StepInAssessment(entity=entity)

    # Score each indicator
    indicator_scores = {}

    # Sponsorship - binary based on entity attribute
    indicator_scores[StepInIndicator.SPONSORSHIP] = 1.0 if entity.is_sponsored else 0.0

    # Implicit support
    indicator_scores[StepInIndicator.IMPLICIT_SUPPORT] = (
        1.0 if has_implicit_support_expectation or entity.past_support_provided else 0.0
    )

    # Involvement level
    indicator_scores[StepInIndicator.INVOLVEMENT] = involvement_level

    # Reputation
    indicator_scores[StepInIndicator.REPUTATION] = reputational_impact

    # Investor expectations
    indicator_scores[StepInIndicator.INVESTOR_EXPECTATIONS] = investor_expectation_level

    # Name association
    indicator_scores[StepInIndicator.NAME_ASSOCIATION] = 1.0 if entity.uses_bank_name else 0.0

    # Credit enhancement
    indicator_scores[StepInIndicator.CREDIT_ENHANCEMENT] = 1.0 if provides_credit_enhancement else 0.0

    # Liquidity support
    indicator_scores[StepInIndicator.LIQUIDITY_SUPPORT] = 1.0 if provides_liquidity_support else 0.0

    # Revenue dependence
    indicator_scores[StepInIndicator.REVENUE_DEPENDENCE] = 1.0 if revenue_from_entity_significant else 0.0

    assessment.indicator_scores = indicator_scores

    # Calculate weighted overall score
    overall_score = sum(
        score * INDICATOR_WEIGHTS.get(indicator, 0)
        for indicator, score in indicator_scores.items()
    )

    assessment.overall_score = overall_score

    # Determine risk level
    if overall_score >= 0.6:
        assessment.risk_level = "high"
    elif overall_score >= 0.3:
        assessment.risk_level = "medium"
    else:
        assessment.risk_level = "low"

    # Add notes
    if entity.is_sponsored:
        assessment.notes.append("Bank sponsors this entity")
    if entity.past_support_provided:
        assessment.notes.append("Bank has provided support in the past")
    if entity.uses_bank_name:
        assessment.notes.append("Entity uses bank's name/brand")

    return assessment


def calculate_step_in_capital_impact(
    assessment: StepInAssessment,
    entity_rwa_if_consolidated: float,
) -> Dict:
    """
    Calculate capital impact of step-in risk.

    Args:
        assessment: Step-in risk assessment
        entity_rwa_if_consolidated: RWA if entity were fully consolidated

    Returns:
        Dict with capital impact analysis
    """
    treatment = CAPITAL_TREATMENT[assessment.risk_level]

    # Capital charge based on risk level
    capital_charge_factor = treatment["capital_charge_factor"]
    implied_rwa = entity_rwa_if_consolidated * capital_charge_factor

    # Capital requirement (8% of RWA)
    capital_requirement = implied_rwa * 0.08

    return {
        "entity_id": assessment.entity.entity_id,
        "entity_name": assessment.entity.entity_name,
        "step_in_risk_level": assessment.risk_level,
        "overall_score": assessment.overall_score,
        "treatment_approach": treatment["approach"],
        "treatment_description": treatment["description"],
        "capital_charge_factor": capital_charge_factor,
        "entity_assets": assessment.entity.total_assets,
        "entity_rwa_if_consolidated": entity_rwa_if_consolidated,
        "implied_rwa": implied_rwa,
        "capital_requirement": capital_requirement,
        "contractual_exposure": assessment.entity.contractual_exposure,
    }


def calculate_liquidity_impact(
    assessment: StepInAssessment,
    entity_liquidity_needs: float,
    available_liquidity_facilities: float,
) -> Dict:
    """
    Calculate liquidity impact of step-in risk.

    Under stressed conditions, bank may need to provide
    liquidity support beyond contractual commitments.

    Args:
        assessment: Step-in risk assessment
        entity_liquidity_needs: Entity's potential liquidity needs
        available_liquidity_facilities: Committed liquidity facilities

    Returns:
        Dict with liquidity impact analysis
    """
    # Stress factors by risk level
    stress_factors = {
        "high": 0.80,    # 80% of liquidity needs may crystallize
        "medium": 0.40,  # 40% of liquidity needs
        "low": 0.10,     # 10% of liquidity needs
    }

    stress_factor = stress_factors[assessment.risk_level]

    # Potential liquidity outflow
    potential_outflow = entity_liquidity_needs * stress_factor

    # Net additional liquidity (beyond committed facilities)
    additional_liquidity = max(0, potential_outflow - available_liquidity_facilities)

    return {
        "entity_id": assessment.entity.entity_id,
        "step_in_risk_level": assessment.risk_level,
        "entity_liquidity_needs": entity_liquidity_needs,
        "committed_facilities": available_liquidity_facilities,
        "stress_factor": stress_factor,
        "potential_outflow": potential_outflow,
        "additional_liquidity_needed": additional_liquidity,
        "lcr_impact": additional_liquidity,  # Should be included in LCR outflows
    }


def generate_step_in_risk_report(
    assessments: List[StepInAssessment],
    bank_tier1_capital: float,
) -> Dict:
    """
    Generate consolidated step-in risk report for all entities.

    Args:
        assessments: List of step-in assessments
        bank_tier1_capital: Bank's Tier 1 capital

    Returns:
        Dict with consolidated report
    """
    # Categorize by risk level
    by_risk_level = {"high": [], "medium": [], "low": []}
    for assessment in assessments:
        by_risk_level[assessment.risk_level].append(assessment)

    # Summary statistics
    total_entities = len(assessments)
    total_assets = sum(a.entity.total_assets for a in assessments)
    total_contractual = sum(a.entity.contractual_exposure for a in assessments)

    # High-risk entities
    high_risk_assets = sum(a.entity.total_assets for a in by_risk_level["high"])
    high_risk_percentage = high_risk_assets / total_assets if total_assets > 0 else 0

    # Calculate aggregate capital impact (simplified)
    aggregate_rwa_impact = sum(
        a.entity.total_assets * 0.35 * CAPITAL_TREATMENT[a.risk_level]["capital_charge_factor"]
        for a in assessments
    )

    return {
        "summary": {
            "total_entities_assessed": total_entities,
            "high_risk_entities": len(by_risk_level["high"]),
            "medium_risk_entities": len(by_risk_level["medium"]),
            "low_risk_entities": len(by_risk_level["low"]),
        },
        "exposure_analysis": {
            "total_entity_assets": total_assets,
            "total_contractual_exposure": total_contractual,
            "high_risk_assets": high_risk_assets,
            "high_risk_percentage": high_risk_percentage,
        },
        "capital_impact": {
            "aggregate_rwa_impact": aggregate_rwa_impact,
            "aggregate_capital_impact": aggregate_rwa_impact * 0.08,
            "as_percentage_of_tier1": (aggregate_rwa_impact * 0.08) / bank_tier1_capital if bank_tier1_capital > 0 else 0,
        },
        "entities_by_risk_level": {
            level: [
                {
                    "entity_id": a.entity.entity_id,
                    "entity_name": a.entity.entity_name,
                    "entity_type": a.entity.entity_type.value,
                    "assets": a.entity.total_assets,
                    "score": a.overall_score,
                }
                for a in entities
            ]
            for level, entities in by_risk_level.items()
        },
        "recommended_actions": generate_recommendations(by_risk_level),
    }


def generate_recommendations(
    by_risk_level: Dict[str, List[StepInAssessment]],
) -> List[str]:
    """Generate recommendations based on step-in risk profile."""
    recommendations = []

    if by_risk_level["high"]:
        recommendations.append(
            "HIGH PRIORITY: Review consolidation treatment for high-risk entities"
        )
        recommendations.append(
            "Assess whether capital and liquidity buffers adequately cover step-in risk"
        )

    if by_risk_level["medium"]:
        recommendations.append(
            "MEDIUM PRIORITY: Monitor medium-risk entities and establish early warning triggers"
        )

    if len(by_risk_level["high"]) + len(by_risk_level["medium"]) > 5:
        recommendations.append(
            "Consider reducing sponsorship activities or rebranding entities"
        )

    recommendations.append(
        "Ensure step-in risk is included in Pillar 3 disclosures"
    )

    return recommendations


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("STEP-IN RISK FRAMEWORK - EXAMPLES")
    print("=" * 70)

    # 1. Create sample entities
    entities = [
        UnconsolidatedEntity(
            entity_id="SPV001",
            entity_name="ABC Funding Vehicle",
            entity_type=EntityType.SECURITIZATION_VEHICLE,
            total_assets=500_000_000,
            is_sponsored=True,
            uses_bank_name=True,
            contractual_exposure=25_000_000,
            ownership_percentage=0,
            provides_services=True,
            past_support_provided=True,
        ),
        UnconsolidatedEntity(
            entity_id="MMF001",
            entity_name="XYZ Money Market Fund",
            entity_type=EntityType.MONEY_MARKET_FUND,
            total_assets=2_000_000_000,
            is_sponsored=True,
            uses_bank_name=True,
            contractual_exposure=0,
            ownership_percentage=0,
            provides_services=True,
            past_support_provided=False,
        ),
        UnconsolidatedEntity(
            entity_id="JV001",
            entity_name="Regional Mortgage JV",
            entity_type=EntityType.JOINT_VENTURE,
            total_assets=100_000_000,
            is_sponsored=False,
            uses_bank_name=False,
            contractual_exposure=30_000_000,
            ownership_percentage=0.40,
            provides_services=False,
            past_support_provided=False,
        ),
    ]

    # 2. Assess each entity
    print("\n1. INDIVIDUAL ENTITY ASSESSMENTS")
    print("-" * 40)

    assessments = []

    # SPV Assessment - High risk expected
    spv_assessment = assess_step_in_indicators(
        entity=entities[0],
        has_implicit_support_expectation=True,
        involvement_level=0.8,
        reputational_impact=0.9,
        investor_expectation_level=0.85,
        provides_credit_enhancement=True,
        provides_liquidity_support=True,
        revenue_from_entity_significant=False,
    )
    assessments.append(spv_assessment)

    print(f"\nEntity: {spv_assessment.entity.entity_name}")
    print(f"Type: {spv_assessment.entity.entity_type.value}")
    print(f"Overall Score: {spv_assessment.overall_score:.2f}")
    print(f"Risk Level: {spv_assessment.risk_level.upper()}")
    print("Key Indicators:")
    for indicator, score in spv_assessment.indicator_scores.items():
        if score > 0:
            print(f"  - {indicator.value}: {score:.2f}")

    # MMF Assessment - Medium risk
    mmf_assessment = assess_step_in_indicators(
        entity=entities[1],
        has_implicit_support_expectation=True,
        involvement_level=0.5,
        reputational_impact=0.7,
        investor_expectation_level=0.6,
        provides_credit_enhancement=False,
        provides_liquidity_support=True,
        revenue_from_entity_significant=True,
    )
    assessments.append(mmf_assessment)

    print(f"\nEntity: {mmf_assessment.entity.entity_name}")
    print(f"Type: {mmf_assessment.entity.entity_type.value}")
    print(f"Overall Score: {mmf_assessment.overall_score:.2f}")
    print(f"Risk Level: {mmf_assessment.risk_level.upper()}")

    # JV Assessment - Low risk
    jv_assessment = assess_step_in_indicators(
        entity=entities[2],
        has_implicit_support_expectation=False,
        involvement_level=0.3,
        reputational_impact=0.2,
        investor_expectation_level=0.1,
        provides_credit_enhancement=False,
        provides_liquidity_support=False,
        revenue_from_entity_significant=False,
    )
    assessments.append(jv_assessment)

    print(f"\nEntity: {jv_assessment.entity.entity_name}")
    print(f"Type: {jv_assessment.entity.entity_type.value}")
    print(f"Overall Score: {jv_assessment.overall_score:.2f}")
    print(f"Risk Level: {jv_assessment.risk_level.upper()}")

    # 3. Capital Impact
    print("\n\n2. CAPITAL IMPACT ANALYSIS")
    print("-" * 40)

    for assessment in assessments:
        # Assume 35% RW density if consolidated
        rwa_if_consolidated = assessment.entity.total_assets * 0.35 * 12.5

        capital_impact = calculate_step_in_capital_impact(
            assessment,
            entity_rwa_if_consolidated=rwa_if_consolidated,
        )

        print(f"\n{capital_impact['entity_name']}:")
        print(f"  Risk Level: {capital_impact['step_in_risk_level'].upper()}")
        print(f"  Treatment: {capital_impact['treatment_approach']}")
        print(f"  Implied RWA: EUR {capital_impact['implied_rwa']:,.0f}")
        print(f"  Capital Requirement: EUR {capital_impact['capital_requirement']:,.0f}")

    # 4. Liquidity Impact
    print("\n\n3. LIQUIDITY IMPACT ANALYSIS")
    print("-" * 40)

    for assessment in assessments:
        liquidity_impact = calculate_liquidity_impact(
            assessment,
            entity_liquidity_needs=assessment.entity.total_assets * 0.10,
            available_liquidity_facilities=assessment.entity.contractual_exposure,
        )

        print(f"\n{assessment.entity.entity_name}:")
        print(f"  Potential Outflow: EUR {liquidity_impact['potential_outflow']:,.0f}")
        print(f"  Additional Liquidity: EUR {liquidity_impact['additional_liquidity_needed']:,.0f}")

    # 5. Consolidated Report
    print("\n\n4. CONSOLIDATED STEP-IN RISK REPORT")
    print("-" * 40)

    report = generate_step_in_risk_report(
        assessments,
        bank_tier1_capital=10_000_000_000,  # EUR 10bn Tier 1
    )

    print(f"\nSummary:")
    print(f"  Total Entities: {report['summary']['total_entities_assessed']}")
    print(f"  High Risk: {report['summary']['high_risk_entities']}")
    print(f"  Medium Risk: {report['summary']['medium_risk_entities']}")
    print(f"  Low Risk: {report['summary']['low_risk_entities']}")

    print(f"\nExposure Analysis:")
    print(f"  Total Entity Assets: EUR {report['exposure_analysis']['total_entity_assets']:,.0f}")
    print(f"  High Risk %: {report['exposure_analysis']['high_risk_percentage']:.1%}")

    print(f"\nCapital Impact:")
    print(f"  Aggregate RWA Impact: EUR {report['capital_impact']['aggregate_rwa_impact']:,.0f}")
    print(f"  Capital Impact: EUR {report['capital_impact']['aggregate_capital_impact']:,.0f}")
    print(f"  % of Tier 1: {report['capital_impact']['as_percentage_of_tier1']:.2%}")

    print(f"\nRecommendations:")
    for rec in report['recommended_actions']:
        print(f"  • {rec}")
