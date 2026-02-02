"""
Stress Testing Framework - Basel III/IV
BCBS 239 (January 2013), BCBS Stress Testing Principles

Stress testing components:
- Macroeconomic scenario design
- Credit risk stress (PD/LGD migration)
- Market risk stress (VaR shocked)
- Operational risk stress
- Liquidity stress
- Capital impact assessment

Reference: BCBS Principles for effective risk data aggregation and risk reporting
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


class ScenarioType(Enum):
    """Types of stress scenarios."""
    BASELINE = "baseline"
    ADVERSE = "adverse"
    SEVERELY_ADVERSE = "severely_adverse"
    CUSTOM = "custom"


class MacroVariable(Enum):
    """Key macroeconomic variables for stress testing."""
    GDP_GROWTH = "gdp_growth"
    UNEMPLOYMENT = "unemployment"
    INFLATION = "inflation"
    INTEREST_RATE = "interest_rate"
    HOUSE_PRICES = "house_prices"
    EQUITY_PRICES = "equity_prices"
    CREDIT_SPREADS = "credit_spreads"
    FX_RATE = "fx_rate"


# Standard scenario parameters (example - EBA/Fed style)
STANDARD_SCENARIOS = {
    ScenarioType.BASELINE: {
        MacroVariable.GDP_GROWTH: 0.02,       # 2% growth
        MacroVariable.UNEMPLOYMENT: 0.05,     # 5% unemployment
        MacroVariable.INFLATION: 0.02,        # 2% inflation
        MacroVariable.INTEREST_RATE: 0.03,    # 3% rate
        MacroVariable.HOUSE_PRICES: 0.03,     # 3% growth
        MacroVariable.EQUITY_PRICES: 0.05,    # 5% growth
        MacroVariable.CREDIT_SPREADS: 0.01,   # 100bps
        MacroVariable.FX_RATE: 0.0,           # No change
    },
    ScenarioType.ADVERSE: {
        MacroVariable.GDP_GROWTH: -0.02,      # -2% contraction
        MacroVariable.UNEMPLOYMENT: 0.08,     # 8% unemployment
        MacroVariable.INFLATION: 0.00,        # 0% inflation
        MacroVariable.INTEREST_RATE: 0.01,    # 1% rate
        MacroVariable.HOUSE_PRICES: -0.15,    # -15% decline
        MacroVariable.EQUITY_PRICES: -0.25,   # -25% decline
        MacroVariable.CREDIT_SPREADS: 0.03,   # 300bps
        MacroVariable.FX_RATE: -0.10,         # 10% depreciation
    },
    ScenarioType.SEVERELY_ADVERSE: {
        MacroVariable.GDP_GROWTH: -0.05,      # -5% deep recession
        MacroVariable.UNEMPLOYMENT: 0.12,     # 12% unemployment
        MacroVariable.INFLATION: -0.01,       # -1% deflation
        MacroVariable.INTEREST_RATE: 0.00,    # 0% rate (ZLB)
        MacroVariable.HOUSE_PRICES: -0.30,    # -30% crash
        MacroVariable.EQUITY_PRICES: -0.50,   # -50% crash
        MacroVariable.CREDIT_SPREADS: 0.06,   # 600bps
        MacroVariable.FX_RATE: -0.20,         # 20% depreciation
    },
}


@dataclass
class StressScenario:
    """A stress test scenario."""
    name: str
    scenario_type: ScenarioType
    horizon_years: int  # Usually 3 years
    macro_paths: Dict[MacroVariable, List[float]]  # Year-by-year paths
    description: str = ""


@dataclass
class PortfolioData:
    """Portfolio data for stress testing."""
    credit_exposure: float
    credit_rwa: float
    average_pd: float
    average_lgd: float
    market_var: float
    market_exposure: float
    operational_bir: float  # Business Indicator
    liquidity_hqla: float
    liquidity_outflows: float


@dataclass
class StressTestResult:
    """Results from a stress test."""
    scenario: StressScenario
    year: int
    stressed_pd: float
    stressed_lgd: float
    credit_losses: float
    credit_rwa_stressed: float
    market_losses: float
    market_rwa_stressed: float
    operational_losses: float
    total_losses: float
    capital_impact: float
    capital_ratio_impact: float


# =============================================================================
# CREDIT RISK STRESS
# =============================================================================

def calculate_pd_stress_multiplier(
    gdp_growth: float,
    unemployment: float,
    house_prices: float,
) -> float:
    """
    Calculate PD stress multiplier based on macro scenario.

    Empirical relationship: PD increases with economic deterioration.

    Args:
        gdp_growth: GDP growth rate (negative = contraction)
        unemployment: Unemployment rate
        house_prices: House price change

    Returns:
        Multiplier to apply to baseline PD
    """
    # Baseline assumptions
    base_gdp = 0.02
    base_unemployment = 0.05
    base_hp = 0.03

    # Sensitivities (calibrated to historical data)
    gdp_sensitivity = -5.0       # 1% GDP drop -> 5% PD increase
    unemp_sensitivity = 2.0      # 1% unemployment increase -> 2% PD increase
    hp_sensitivity = -1.5        # 1% HP drop -> 1.5% PD increase

    # Calculate impact
    gdp_impact = (gdp_growth - base_gdp) * gdp_sensitivity
    unemp_impact = (unemployment - base_unemployment) * unemp_sensitivity
    hp_impact = (house_prices - base_hp) * hp_sensitivity

    # Total multiplier (minimum 1.0, no improvement in stress)
    multiplier = 1.0 - (gdp_impact + unemp_impact + hp_impact)
    multiplier = max(1.0, min(multiplier, 10.0))  # Cap at 10x

    return multiplier


def calculate_lgd_stress_multiplier(
    house_prices: float,
    credit_spreads: float,
) -> float:
    """
    Calculate LGD stress multiplier based on collateral values and recovery rates.

    Args:
        house_prices: House price change
        credit_spreads: Credit spread level

    Returns:
        Multiplier to apply to baseline LGD
    """
    base_hp = 0.03
    base_spreads = 0.01

    # Sensitivities
    hp_sensitivity = -0.8       # HP drop increases LGD
    spread_sensitivity = 3.0    # Wider spreads = lower recovery

    hp_impact = (house_prices - base_hp) * hp_sensitivity
    spread_impact = (credit_spreads - base_spreads) * spread_sensitivity

    multiplier = 1.0 - (hp_impact) + spread_impact
    multiplier = max(1.0, min(multiplier, 2.0))  # Cap at 2x LGD

    return multiplier


def stress_credit_portfolio(
    portfolio: PortfolioData,
    scenario: StressScenario,
    year: int,
) -> Dict:
    """
    Apply credit stress to portfolio.

    Args:
        portfolio: Portfolio data
        scenario: Stress scenario
        year: Year in the scenario horizon (0-indexed)

    Returns:
        Dict with stressed credit metrics
    """
    # Get macro variables for the year
    gdp = scenario.macro_paths[MacroVariable.GDP_GROWTH][year]
    unemp = scenario.macro_paths[MacroVariable.UNEMPLOYMENT][year]
    hp = scenario.macro_paths[MacroVariable.HOUSE_PRICES][year]
    spreads = scenario.macro_paths[MacroVariable.CREDIT_SPREADS][year]

    # Calculate stress multipliers
    pd_mult = calculate_pd_stress_multiplier(gdp, unemp, hp)
    lgd_mult = calculate_lgd_stress_multiplier(hp, spreads)

    # Apply stress
    stressed_pd = min(portfolio.average_pd * pd_mult, 1.0)
    stressed_lgd = min(portfolio.average_lgd * lgd_mult, 1.0)

    # Expected loss = PD * LGD * EAD
    baseline_el = portfolio.average_pd * portfolio.average_lgd * portfolio.credit_exposure
    stressed_el = stressed_pd * stressed_lgd * portfolio.credit_exposure

    # Credit loss increase
    credit_losses = stressed_el - baseline_el

    # RWA impact (simplified: assume linear relationship)
    rwa_multiplier = (stressed_pd / portfolio.average_pd) * math.sqrt(stressed_lgd / portfolio.average_lgd)
    stressed_rwa = portfolio.credit_rwa * rwa_multiplier

    return {
        "pd_multiplier": pd_mult,
        "lgd_multiplier": lgd_mult,
        "baseline_pd": portfolio.average_pd,
        "stressed_pd": stressed_pd,
        "baseline_lgd": portfolio.average_lgd,
        "stressed_lgd": stressed_lgd,
        "baseline_el": baseline_el,
        "stressed_el": stressed_el,
        "incremental_losses": credit_losses,
        "baseline_rwa": portfolio.credit_rwa,
        "stressed_rwa": stressed_rwa,
        "rwa_increase": stressed_rwa - portfolio.credit_rwa,
    }


# =============================================================================
# MARKET RISK STRESS
# =============================================================================

def stress_market_portfolio(
    portfolio: PortfolioData,
    scenario: StressScenario,
    year: int,
) -> Dict:
    """
    Apply market risk stress to portfolio.

    Args:
        portfolio: Portfolio data
        scenario: Stress scenario
        year: Year in scenario

    Returns:
        Dict with stressed market risk metrics
    """
    equity = scenario.macro_paths[MacroVariable.EQUITY_PRICES][year]
    rates = scenario.macro_paths[MacroVariable.INTEREST_RATE][year]
    fx = scenario.macro_paths[MacroVariable.FX_RATE][year]

    # Market loss estimation (simplified)
    # Assume portfolio has equity, rate, and FX sensitivity
    equity_sensitivity = 0.40   # 40% equity exposure
    rate_sensitivity = 0.30     # 30% rate exposure
    fx_sensitivity = 0.15       # 15% FX exposure

    # Calculate P&L impact
    equity_pnl = portfolio.market_exposure * equity_sensitivity * equity
    rate_pnl = portfolio.market_exposure * rate_sensitivity * (rates - 0.03) * -2  # Duration ~2
    fx_pnl = portfolio.market_exposure * fx_sensitivity * fx

    total_market_loss = -(equity_pnl + rate_pnl + fx_pnl)  # Negative = loss

    # VaR scaling under stress (VaR typically increases in stressed periods)
    volatility_multiplier = 1.0 + abs(equity) + abs(fx)
    stressed_var = portfolio.market_var * volatility_multiplier

    return {
        "equity_shock": equity,
        "rate_shock": rates,
        "fx_shock": fx,
        "equity_pnl": equity_pnl,
        "rate_pnl": rate_pnl,
        "fx_pnl": fx_pnl,
        "total_market_loss": max(0, total_market_loss),
        "baseline_var": portfolio.market_var,
        "stressed_var": stressed_var,
    }


# =============================================================================
# OPERATIONAL RISK STRESS
# =============================================================================

def stress_operational_risk(
    portfolio: PortfolioData,
    scenario: StressScenario,
    year: int,
) -> Dict:
    """
    Apply operational risk stress.

    Under stress, operational losses may increase due to:
    - Increased fraud in recessions
    - System failures under load
    - Conduct issues

    Args:
        portfolio: Portfolio data
        scenario: Stress scenario
        year: Year in scenario

    Returns:
        Dict with stressed operational risk
    """
    gdp = scenario.macro_paths[MacroVariable.GDP_GROWTH][year]

    # Operational loss increases in downturns
    # Baseline: use SMA formula (12% of BIC)
    baseline_op_loss = portfolio.operational_bir * 0.12

    # Stress multiplier based on GDP
    # Recession -> higher fraud, misconduct
    if gdp < 0:
        stress_mult = 1.0 + abs(gdp) * 10  # -5% GDP -> 1.5x losses
    else:
        stress_mult = 1.0

    stressed_op_loss = baseline_op_loss * stress_mult

    return {
        "baseline_op_loss": baseline_op_loss,
        "stress_multiplier": stress_mult,
        "stressed_op_loss": stressed_op_loss,
        "incremental_loss": stressed_op_loss - baseline_op_loss,
    }


# =============================================================================
# LIQUIDITY STRESS
# =============================================================================

def stress_liquidity(
    portfolio: PortfolioData,
    scenario: StressScenario,
    year: int,
) -> Dict:
    """
    Apply liquidity stress.

    Under stress:
    - HQLA values decline (haircuts increase)
    - Outflows accelerate
    - Inflows decrease

    Args:
        portfolio: Portfolio data
        scenario: Stress scenario
        year: Year in scenario

    Returns:
        Dict with stressed liquidity metrics
    """
    equity = scenario.macro_paths[MacroVariable.EQUITY_PRICES][year]
    spreads = scenario.macro_paths[MacroVariable.CREDIT_SPREADS][year]

    # HQLA haircut increases
    base_haircut = 0.05  # 5% baseline
    stress_haircut = base_haircut + abs(equity) * 0.10 + spreads * 2
    stressed_hqla = portfolio.liquidity_hqla * (1 - stress_haircut)

    # Outflows accelerate in stress
    outflow_multiplier = 1.0 + spreads * 10  # Higher spreads = more outflows
    stressed_outflows = portfolio.liquidity_outflows * outflow_multiplier

    # LCR calculation
    baseline_lcr = portfolio.liquidity_hqla / portfolio.liquidity_outflows
    stressed_lcr = stressed_hqla / stressed_outflows

    return {
        "baseline_hqla": portfolio.liquidity_hqla,
        "stressed_hqla": stressed_hqla,
        "hqla_haircut": stress_haircut,
        "baseline_outflows": portfolio.liquidity_outflows,
        "stressed_outflows": stressed_outflows,
        "outflow_multiplier": outflow_multiplier,
        "baseline_lcr": baseline_lcr,
        "stressed_lcr": stressed_lcr,
        "lcr_decline": baseline_lcr - stressed_lcr,
    }


# =============================================================================
# INTEGRATED STRESS TEST
# =============================================================================

def create_scenario_paths(
    scenario_type: ScenarioType,
    horizon_years: int = 3,
) -> StressScenario:
    """
    Create a stress scenario with year-by-year macro paths.

    Args:
        scenario_type: Type of scenario
        horizon_years: Number of years

    Returns:
        StressScenario with paths
    """
    base_params = STANDARD_SCENARIOS[scenario_type]

    # Create paths (simplified: linear interpolation from base to stress)
    macro_paths = {}
    baseline = STANDARD_SCENARIOS[ScenarioType.BASELINE]

    for var in MacroVariable:
        if scenario_type == ScenarioType.BASELINE:
            # Baseline stays constant
            macro_paths[var] = [base_params[var]] * horizon_years
        else:
            # Interpolate from baseline to stressed level
            start = baseline[var]
            end = base_params[var]
            path = [
                start + (end - start) * (i + 1) / horizon_years
                for i in range(horizon_years)
            ]
            macro_paths[var] = path

    return StressScenario(
        name=f"{scenario_type.value}_scenario",
        scenario_type=scenario_type,
        horizon_years=horizon_years,
        macro_paths=macro_paths,
        description=f"Standard {scenario_type.value} scenario over {horizon_years} years",
    )


def run_integrated_stress_test(
    portfolio: PortfolioData,
    scenario: StressScenario,
    cet1_capital: float,
    total_rwa: float,
) -> List[StressTestResult]:
    """
    Run integrated stress test across all risk types.

    Args:
        portfolio: Portfolio data
        scenario: Stress scenario
        cet1_capital: Starting CET1 capital
        total_rwa: Starting total RWA

    Returns:
        List of StressTestResult for each year
    """
    results = []
    running_capital = cet1_capital
    running_rwa = total_rwa

    for year in range(scenario.horizon_years):
        # Credit stress
        credit_result = stress_credit_portfolio(portfolio, scenario, year)

        # Market stress
        market_result = stress_market_portfolio(portfolio, scenario, year)

        # Operational stress
        op_result = stress_operational_risk(portfolio, scenario, year)

        # Liquidity stress
        liq_result = stress_liquidity(portfolio, scenario, year)

        # Total losses
        total_losses = (
            credit_result["incremental_losses"] +
            market_result["total_market_loss"] +
            op_result["incremental_loss"]
        )

        # Capital impact
        running_capital -= total_losses

        # RWA impact
        rwa_increase = credit_result["rwa_increase"]
        running_rwa += rwa_increase

        # Capital ratio
        new_cet1_ratio = running_capital / running_rwa if running_rwa > 0 else 0
        original_ratio = cet1_capital / total_rwa if total_rwa > 0 else 0

        result = StressTestResult(
            scenario=scenario,
            year=year + 1,
            stressed_pd=credit_result["stressed_pd"],
            stressed_lgd=credit_result["stressed_lgd"],
            credit_losses=credit_result["incremental_losses"],
            credit_rwa_stressed=credit_result["stressed_rwa"],
            market_losses=market_result["total_market_loss"],
            market_rwa_stressed=market_result["stressed_var"] * 12.5,  # Simplified
            operational_losses=op_result["incremental_loss"],
            total_losses=total_losses,
            capital_impact=cet1_capital - running_capital,
            capital_ratio_impact=original_ratio - new_cet1_ratio,
        )
        results.append(result)

    return results


def generate_stress_test_report(
    results: List[StressTestResult],
    cet1_capital: float,
    total_rwa: float,
    min_cet1_ratio: float = 0.045,
) -> Dict:
    """
    Generate stress test summary report.

    Args:
        results: List of year-by-year results
        cet1_capital: Starting capital
        total_rwa: Starting RWA
        min_cet1_ratio: Minimum CET1 requirement

    Returns:
        Dict with summary report
    """
    if not results:
        return {"error": "No results provided"}

    scenario = results[0].scenario
    final_result = results[-1]

    # Calculate ending position
    cumulative_losses = sum(r.total_losses for r in results)
    ending_capital = cet1_capital - cumulative_losses
    ending_rwa = total_rwa + sum(
        r.credit_rwa_stressed - total_rwa / len(results)
        for r in results
    ) / len(results) * len(results)  # Simplified

    ending_ratio = ending_capital / total_rwa if total_rwa > 0 else 0
    starting_ratio = cet1_capital / total_rwa if total_rwa > 0 else 0

    # Buffer analysis
    buffer_available = ending_ratio - min_cet1_ratio
    buffer_depleted = buffer_available < 0

    return {
        "scenario": scenario.name,
        "scenario_type": scenario.scenario_type.value,
        "horizon_years": scenario.horizon_years,
        "starting_position": {
            "cet1_capital": cet1_capital,
            "total_rwa": total_rwa,
            "cet1_ratio": starting_ratio,
        },
        "ending_position": {
            "cet1_capital": ending_capital,
            "total_rwa": ending_rwa,
            "cet1_ratio": ending_ratio,
        },
        "cumulative_impact": {
            "total_losses": cumulative_losses,
            "credit_losses": sum(r.credit_losses for r in results),
            "market_losses": sum(r.market_losses for r in results),
            "operational_losses": sum(r.operational_losses for r in results),
            "capital_ratio_decline": starting_ratio - ending_ratio,
        },
        "year_by_year": [
            {
                "year": r.year,
                "losses": r.total_losses,
                "cumulative_losses": sum(results[i].total_losses for i in range(r.year)),
            }
            for r in results
        ],
        "buffer_analysis": {
            "minimum_requirement": min_cet1_ratio,
            "ending_buffer": buffer_available,
            "buffer_depleted": buffer_depleted,
            "capital_shortfall": abs(buffer_available * total_rwa) if buffer_depleted else 0,
        },
        "pass_fail": "PASS" if not buffer_depleted else "FAIL",
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("STRESS TESTING FRAMEWORK - EXAMPLES")
    print("=" * 70)

    # 1. Create scenarios
    print("\n1. SCENARIO DESIGN")
    print("-" * 40)

    baseline = create_scenario_paths(ScenarioType.BASELINE, 3)
    adverse = create_scenario_paths(ScenarioType.ADVERSE, 3)
    severe = create_scenario_paths(ScenarioType.SEVERELY_ADVERSE, 3)

    print(f"Scenario: {severe.name}")
    print(f"Horizon: {severe.horizon_years} years")
    print("\nMacro Variable Paths (Year 1 -> Year 3):")
    for var in [MacroVariable.GDP_GROWTH, MacroVariable.UNEMPLOYMENT, MacroVariable.EQUITY_PRICES]:
        path = severe.macro_paths[var]
        print(f"  {var.value}: {path[0]:.2%} -> {path[-1]:.2%}")

    # 2. Portfolio data
    print("\n\n2. PORTFOLIO DATA")
    print("-" * 40)

    portfolio = PortfolioData(
        credit_exposure=500_000_000_000,  # 500bn
        credit_rwa=200_000_000_000,       # 200bn
        average_pd=0.02,                  # 2%
        average_lgd=0.40,                 # 40%
        market_var=500_000_000,           # 500mn
        market_exposure=50_000_000_000,   # 50bn
        operational_bir=10_000_000_000,   # 10bn BIC
        liquidity_hqla=100_000_000_000,   # 100bn HQLA
        liquidity_outflows=80_000_000_000, # 80bn outflows
    )

    print(f"Credit Exposure: EUR {portfolio.credit_exposure/1e9:.0f}bn")
    print(f"Credit RWA: EUR {portfolio.credit_rwa/1e9:.0f}bn")
    print(f"Average PD: {portfolio.average_pd:.2%}")
    print(f"Average LGD: {portfolio.average_lgd:.2%}")

    # 3. Run stress test
    print("\n\n3. SEVERELY ADVERSE STRESS TEST")
    print("-" * 40)

    cet1 = 30_000_000_000  # 30bn CET1
    rwa = 250_000_000_000  # 250bn RWA

    results = run_integrated_stress_test(portfolio, severe, cet1, rwa)

    for result in results:
        print(f"\nYear {result.year}:")
        print(f"  Stressed PD: {result.stressed_pd:.2%} (vs {portfolio.average_pd:.2%})")
        print(f"  Stressed LGD: {result.stressed_lgd:.2%} (vs {portfolio.average_lgd:.2%})")
        print(f"  Credit Losses: EUR {result.credit_losses/1e9:.2f}bn")
        print(f"  Market Losses: EUR {result.market_losses/1e9:.2f}bn")
        print(f"  Op Losses: EUR {result.operational_losses/1e9:.2f}bn")
        print(f"  Total Losses: EUR {result.total_losses/1e9:.2f}bn")

    # 4. Summary report
    print("\n\n4. STRESS TEST REPORT")
    print("-" * 40)

    report = generate_stress_test_report(results, cet1, rwa)

    print(f"Scenario: {report['scenario']}")
    print(f"\nStarting Position:")
    print(f"  CET1 Capital: EUR {report['starting_position']['cet1_capital']/1e9:.1f}bn")
    print(f"  CET1 Ratio: {report['starting_position']['cet1_ratio']:.2%}")

    print(f"\nEnding Position:")
    print(f"  CET1 Capital: EUR {report['ending_position']['cet1_capital']/1e9:.1f}bn")
    print(f"  CET1 Ratio: {report['ending_position']['cet1_ratio']:.2%}")

    print(f"\nCumulative Impact:")
    print(f"  Total Losses: EUR {report['cumulative_impact']['total_losses']/1e9:.1f}bn")
    print(f"  - Credit: EUR {report['cumulative_impact']['credit_losses']/1e9:.1f}bn")
    print(f"  - Market: EUR {report['cumulative_impact']['market_losses']/1e9:.1f}bn")
    print(f"  - Operational: EUR {report['cumulative_impact']['operational_losses']/1e9:.1f}bn")
    print(f"  CET1 Ratio Decline: {report['cumulative_impact']['capital_ratio_decline']:.2%}")

    print(f"\nBuffer Analysis:")
    print(f"  Minimum Requirement: {report['buffer_analysis']['minimum_requirement']:.2%}")
    print(f"  Ending Buffer: {report['buffer_analysis']['ending_buffer']:.2%}")
    print(f"  Buffer Depleted: {report['buffer_analysis']['buffer_depleted']}")

    print(f"\n{'='*40}")
    print(f"STRESS TEST RESULT: {report['pass_fail']}")
    print(f"{'='*40}")

    # 5. Compare scenarios
    print("\n\n5. SCENARIO COMPARISON")
    print("-" * 40)

    for scenario in [baseline, adverse, severe]:
        results = run_integrated_stress_test(portfolio, scenario, cet1, rwa)
        report = generate_stress_test_report(results, cet1, rwa)

        print(f"\n{scenario.scenario_type.value.upper()}:")
        print(f"  Cumulative Losses: EUR {report['cumulative_impact']['total_losses']/1e9:.1f}bn")
        print(f"  Ending CET1 Ratio: {report['ending_position']['cet1_ratio']:.2%}")
        print(f"  Result: {report['pass_fail']}")
