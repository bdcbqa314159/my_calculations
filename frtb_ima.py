"""
FRTB Internal Models Approach (IMA) — MAR30–33

Implements:
- Expected Shortfall (ES) with liquidity horizons — MAR31
- Stressed Expected Shortfall (SES) — MAR31
- Non-Modellable Risk Factor (NMRF) charge — MAR31.24–31
- Internal Default Risk Charge (DRC) — MAR32
- Backtesting evaluation — MAR33
- P&L Attribution Test (PLA) — MAR33

Capital formula:
    IMA Capital = IMCC + DRC_IMA
    IMCC = max(ES_{t-1}, m_c * ES_avg) + max(SES_{t-1}, m_c * SES_avg) + NMRF
    m_c  = 1.5 * (1 + plus_factor)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional

from market_risk import calculate_frtb_sa
from ratings import RATING_TO_PD


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class ESRiskFactor:
    """A single risk factor for Expected Shortfall calculation."""
    risk_class: str            # "IR", "EQ", "FX", "CR", "COM"
    sub_category: str          # "major", "large_cap", "IG_sovereign", etc.
    es_10day: float            # ES at 10-day horizon for this factor
    is_modellable: bool = True
    stressed_es_10day: Optional[float] = None  # for NMRF stress scenario


@dataclass
class DRCPosition:
    """A single position for the internal DRC model."""
    position_id: str
    obligor: str
    notional: float
    market_value: float
    pd: float
    lgd: float = 0.45
    seniority: str = "senior_unsecured"
    sector: str = "corporate"
    systematic_factor: float = 0.20   # correlation to systematic factor
    is_long: bool = True


@dataclass
class DeskPLA:
    """P&L Attribution Test results for a single desk."""
    desk_id: str
    spearman_correlation: float
    kl_divergence: float


@dataclass
class FRTBIMAConfig:
    """Configuration for the FRTB-IMA calculation."""
    multiplication_factor: float = 1.5
    plus_factor: float = 0.0          # from backtesting (0.0 – 0.5)
    es_confidence: float = 0.975
    drc_confidence: float = 0.999
    drc_horizon_years: float = 1.0
    drc_num_simulations: int = 50_000
    backtesting_exceptions: int = 0


# =============================================================================
# Liquidity Horizons — MAR31.13
# =============================================================================

# (risk_class, sub_category) -> liquidity horizon in days
LIQUIDITY_HORIZONS = {
    # 10-day bucket
    ("IR", "major"):                10,
    # 20-day bucket
    ("IR", "other"):                20,
    ("CR", "IG_sovereign"):         20,
    # 40-day bucket
    ("EQ", "large_cap"):            40,
    ("FX", "major"):                40,
    ("CR", "IG_corporate"):         40,
    # 60-day bucket
    ("EQ", "small_cap"):            60,
    ("FX", "other"):                60,
    ("COM", "energy"):              60,
    ("COM", "precious_metals"):     60,
    ("CR", "HY"):                   60,
    # 120-day bucket
    ("EQ", "other"):               120,
    ("COM", "other"):              120,
    ("CR", "other"):               120,
}

# Ordered liquidity-horizon steps used in the cascade formula
LH_STEPS = [10, 20, 40, 60, 120]


def get_liquidity_horizon(risk_class: str, sub_category: str) -> int:
    """
    Map (risk_class, sub_category) to a liquidity horizon in days (MAR31.13).

    Falls back to 120 days for unmapped combinations.
    """
    return LIQUIDITY_HORIZONS.get((risk_class, sub_category), 120)


# =============================================================================
# Expected Shortfall — MAR31
# =============================================================================

def calculate_liquidity_adjusted_es(
    risk_factors: list[ESRiskFactor],
) -> dict:
    """
    Calculate liquidity-adjusted Expected Shortfall.

    Formula (MAR31.12):
        ES = sqrt( sum_j  [ ES_j(T=10) * sqrt((LH_j - LH_{j-1}) / 10) ]^2 )

    where the sum runs over the five liquidity-horizon steps and ES_j(T=10)
    is the aggregate 10-day ES for all factors whose liquidity horizon >= LH_j.

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        Only modellable factors are included in the ES; non-modellable ones
        are handled by the NMRF charge.

    Returns
    -------
    dict
        es_total, es_by_bucket, and constituent breakdown.
    """
    modellable = [rf for rf in risk_factors if rf.is_modellable]
    if not modellable:
        return {"es_total": 0.0, "es_by_bucket": {}}

    # Assign each factor to its liquidity-horizon step
    factor_lh = {}
    for rf in modellable:
        lh = get_liquidity_horizon(rf.risk_class, rf.sub_category)
        factor_lh.setdefault(lh, []).append(rf)

    # Build cascading ES: at each step j, include all factors with LH >= LH_j
    es_by_bucket = {}
    variance_sum = 0.0
    prev_lh = 0

    for lh in LH_STEPS:
        # Factors whose liquidity horizon is exactly this step
        factors_at_lh = factor_lh.get(lh, [])
        es_10 = sum(rf.es_10day for rf in factors_at_lh)

        if es_10 > 0:
            scale = math.sqrt((lh - prev_lh) / 10.0)
            contribution = (es_10 * scale) ** 2
            variance_sum += contribution
            es_by_bucket[lh] = {
                "es_10day_sum": es_10,
                "scale_factor": scale,
                "contribution": contribution,
            }

        prev_lh = lh

    es_total = math.sqrt(variance_sum) if variance_sum > 0 else 0.0

    return {
        "es_total": es_total,
        "es_by_bucket": es_by_bucket,
        "num_factors": len(modellable),
    }


def calculate_stressed_es(
    risk_factors: list[ESRiskFactor],
    es_full_current: float,
    es_reduced_current: float,
) -> dict:
    """
    Calculate Stressed Expected Shortfall (MAR31.16–18).

    Uses ratio-based scaling:
        SES = ES_reduced_stressed * (ES_full_current / ES_reduced_current)

    The stressed ES is computed on a reduced set of risk factors evaluated
    on their stressed 10-day ES values.

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        Factors with stressed_es_10day populated for the reduced set.
    es_full_current : float
        Full-set current-period ES (from calculate_liquidity_adjusted_es).
    es_reduced_current : float
        Reduced-set current-period ES.

    Returns
    -------
    dict
        ses_total, ratio, and underlying stressed ES.
    """
    # Build stressed ES from the reduced factor set
    stressed_factors = [
        ESRiskFactor(
            risk_class=rf.risk_class,
            sub_category=rf.sub_category,
            es_10day=rf.stressed_es_10day if rf.stressed_es_10day is not None else rf.es_10day,
            is_modellable=rf.is_modellable,
        )
        for rf in risk_factors
        if rf.is_modellable and rf.stressed_es_10day is not None
    ]

    if not stressed_factors or es_reduced_current <= 0:
        return {"ses_total": 0.0, "ratio": 0.0, "es_reduced_stressed": 0.0}

    stressed_result = calculate_liquidity_adjusted_es(stressed_factors)
    es_reduced_stressed = stressed_result["es_total"]

    ratio = es_full_current / es_reduced_current if es_reduced_current > 0 else 1.0
    ses_total = es_reduced_stressed * ratio

    return {
        "ses_total": ses_total,
        "ratio": ratio,
        "es_reduced_stressed": es_reduced_stressed,
        "es_full_current": es_full_current,
        "es_reduced_current": es_reduced_current,
    }


def calculate_nmrf_charge(
    risk_factors: list[ESRiskFactor],
) -> dict:
    """
    Calculate the Non-Modellable Risk Factor add-on (MAR31.24–31).

    For each non-modellable factor the bank computes a stressed sensitivity
    charge.  These are aggregated with *zero diversification* (simple sum).

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        Non-modellable factors (is_modellable=False) should have
        stressed_es_10day populated; others are ignored.

    Returns
    -------
    dict
        nmrf_total and per-factor breakdown.
    """
    nmrf_factors = [rf for rf in risk_factors if not rf.is_modellable]
    if not nmrf_factors:
        return {"nmrf_total": 0.0, "factors": []}

    details = []
    total = 0.0
    for rf in nmrf_factors:
        charge = rf.stressed_es_10day if rf.stressed_es_10day is not None else rf.es_10day
        lh = get_liquidity_horizon(rf.risk_class, rf.sub_category)
        # Scale to appropriate horizon
        scaled = charge * math.sqrt(lh / 10.0)
        total += scaled
        details.append({
            "risk_class": rf.risk_class,
            "sub_category": rf.sub_category,
            "charge_10day": charge,
            "liquidity_horizon": lh,
            "scaled_charge": scaled,
        })

    return {
        "nmrf_total": total,
        "num_factors": len(nmrf_factors),
        "factors": details,
    }


# =============================================================================
# Internal DRC Model — MAR32
# =============================================================================

def simulate_drc_portfolio(
    positions: list[DRCPosition],
    num_simulations: int = 50_000,
    seed: int = 42,
) -> list[float]:
    """
    Monte Carlo simulation of portfolio default losses using a two-factor
    Gaussian copula (MAR32).

    Each obligor's default is driven by:
        Z_i = rho_i * X + sqrt(1 - rho_i^2) * epsilon_i

    where X is the systematic factor, epsilon_i is idiosyncratic, and the
    obligor defaults when Z_i < Phi^{-1}(PD_i).

    Long/short netting is applied only within the same obligor.

    Parameters
    ----------
    positions : list[DRCPosition]
        Portfolio of positions.
    num_simulations : int
        Number of Monte Carlo paths.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    list[float]
        Simulated portfolio losses (one per simulation).
    """
    rng = random.Random(seed)

    # Pre-compute default thresholds (Phi^{-1}(PD))
    def _norm_inv(p):
        """Rational approximation to the inverse normal CDF."""
        if p <= 0:
            return -6.0
        if p >= 1:
            return 6.0
        # Beasley-Springer-Moro algorithm (abridged)
        a = (-3.969683028665376e1, 2.209460984245205e2,
             -2.759285104469687e2, 1.383577518672690e2,
             -3.066479806614716e1, 2.506628277459239e0)
        b = (-5.447609879822406e1, 1.615858368580409e2,
             -1.556989798598866e2, 6.680131188771972e1,
             -1.328068155288572e1)
        c = (-7.784894002430293e-3, -3.223964580411365e-1,
             -2.400758277161838e0, -2.549732539343734e0,
              4.374664141464968e0, 2.938163982698783e0)
        d = (7.784695709041462e-3, 3.224671290700398e-1,
             2.445134137142996e0, 3.754408661907416e0)

        p_low = 0.02425
        p_high = 1.0 - p_low

        if p < p_low:
            q = math.sqrt(-2.0 * math.log(p))
            return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                   ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
                   (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0)
        else:
            q = math.sqrt(-2.0 * math.log(1.0 - p))
            return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                    ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0)

    # Group positions by obligor for netting
    obligor_positions: dict[str, list[DRCPosition]] = {}
    for pos in positions:
        obligor_positions.setdefault(pos.obligor, []).append(pos)

    # Pre-compute thresholds per obligor
    obligor_info = {}
    for obligor, pos_list in obligor_positions.items():
        pd = pos_list[0].pd
        rho = pos_list[0].systematic_factor
        threshold = _norm_inv(pd)
        obligor_info[obligor] = {
            "threshold": threshold,
            "rho": rho,
            "positions": pos_list,
        }

    def _std_normal():
        """Box-Muller transform for standard normal variate."""
        u1 = rng.random()
        u2 = rng.random()
        return math.sqrt(-2.0 * math.log(max(u1, 1e-15))) * math.cos(2.0 * math.pi * u2)

    losses = []
    for _ in range(num_simulations):
        systematic = _std_normal()
        portfolio_loss = 0.0

        for obligor, info in obligor_info.items():
            idio = _std_normal()
            rho = info["rho"]
            z = rho * systematic + math.sqrt(1.0 - rho * rho) * idio

            if z < info["threshold"]:
                # Obligor defaults — net long/short within this obligor
                net_loss = 0.0
                for pos in info["positions"]:
                    sign = 1.0 if pos.is_long else -1.0
                    net_loss += sign * pos.notional * pos.lgd
                portfolio_loss += max(net_loss, 0.0)

        losses.append(portfolio_loss)

    return losses


def calculate_ima_drc(
    positions: list[DRCPosition],
    config: FRTBIMAConfig = None,
) -> dict:
    """
    Calculate the internal DRC charge (MAR32).

    Runs Monte Carlo simulation and takes the 99.9th percentile of the
    loss distribution.

    Parameters
    ----------
    positions : list[DRCPosition]
        Portfolio of DRC positions.
    config : FRTBIMAConfig
        Configuration (confidence level, number of simulations).

    Returns
    -------
    dict
        drc_charge, mean_loss, percentile info, and simulation stats.
    """
    if config is None:
        config = FRTBIMAConfig()

    if not positions:
        return {"drc_charge": 0.0, "mean_loss": 0.0, "num_simulations": 0}

    losses = simulate_drc_portfolio(
        positions,
        num_simulations=config.drc_num_simulations,
    )

    losses_sorted = sorted(losses)
    n = len(losses_sorted)
    idx_999 = min(int(n * config.drc_confidence), n - 1)
    drc_charge = losses_sorted[idx_999]

    mean_loss = sum(losses) / n
    idx_99 = min(int(n * 0.99), n - 1)
    idx_95 = min(int(n * 0.95), n - 1)

    return {
        "drc_charge": drc_charge,
        "mean_loss": mean_loss,
        "percentile_95": losses_sorted[idx_95],
        "percentile_99": losses_sorted[idx_99],
        "percentile_999": drc_charge,
        "max_loss": losses_sorted[-1],
        "num_simulations": n,
        "num_positions": len(positions),
        "num_obligors": len({p.obligor for p in positions}),
    }


# =============================================================================
# Backtesting — MAR33
# =============================================================================

# Plus-factor table (MAR33.6) — based on number of exceptions at 99% VaR
PLUS_FACTOR_TABLE = {
    # exceptions: plus_factor
    0: 0.00, 1: 0.00, 2: 0.00, 3: 0.00, 4: 0.00,   # green zone
    5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85,    # yellow zone
}
# 10+ exceptions → red zone, plus_factor = 1.0


def evaluate_backtesting(
    num_exceptions: int,
    num_observations: int = 250,
) -> dict:
    """
    Evaluate backtesting results and determine the zone / plus factor (MAR33).

    Parameters
    ----------
    num_exceptions : int
        Number of days where actual loss exceeded the VaR/ES estimate
        over the observation period.
    num_observations : int
        Number of trading days in the observation window (default 250).

    Returns
    -------
    dict
        zone (green/yellow/red), plus_factor, and exception rate.
    """
    if num_exceptions <= 4:
        zone = "green"
    elif num_exceptions <= 9:
        zone = "yellow"
    else:
        zone = "red"

    plus_factor = PLUS_FACTOR_TABLE.get(num_exceptions, 1.0)
    exception_rate = num_exceptions / num_observations if num_observations > 0 else 0.0

    return {
        "zone": zone,
        "plus_factor": plus_factor,
        "num_exceptions": num_exceptions,
        "num_observations": num_observations,
        "exception_rate_pct": exception_rate * 100,
    }


# =============================================================================
# P&L Attribution Test (PLA) — MAR33
# =============================================================================

# PLA thresholds (MAR33.37)
PLA_THRESHOLDS = {
    "spearman": {"green": 0.80, "amber": 0.70},
    "kl_divergence": {"green": 0.09, "amber": 0.12},
}


def evaluate_pla(
    desks: list[DeskPLA],
) -> dict:
    """
    Evaluate P&L Attribution Test for each desk (MAR33).

    Two metrics are tested:
    - Spearman rank correlation >= 0.80 (green), >= 0.70 (amber), else red
    - KL divergence <= 0.09 (green), <= 0.12 (amber), else red

    A desk must pass both metrics to achieve a given zone.  Red desks must
    fall back to FRTB-SA.

    Parameters
    ----------
    desks : list[DeskPLA]
        PLA results per desk.

    Returns
    -------
    dict
        Per-desk and summary results.
    """
    results = []
    summary = {"green": 0, "amber": 0, "red": 0}

    for desk in desks:
        # Spearman test
        if desk.spearman_correlation >= PLA_THRESHOLDS["spearman"]["green"]:
            spearman_zone = "green"
        elif desk.spearman_correlation >= PLA_THRESHOLDS["spearman"]["amber"]:
            spearman_zone = "amber"
        else:
            spearman_zone = "red"

        # KL divergence test (lower is better)
        if desk.kl_divergence <= PLA_THRESHOLDS["kl_divergence"]["green"]:
            kl_zone = "green"
        elif desk.kl_divergence <= PLA_THRESHOLDS["kl_divergence"]["amber"]:
            kl_zone = "amber"
        else:
            kl_zone = "red"

        # Overall desk zone: worst of the two tests
        zone_order = {"green": 0, "amber": 1, "red": 2}
        overall_zone = max([spearman_zone, kl_zone], key=lambda z: zone_order[z])

        results.append({
            "desk_id": desk.desk_id,
            "spearman_correlation": desk.spearman_correlation,
            "spearman_zone": spearman_zone,
            "kl_divergence": desk.kl_divergence,
            "kl_zone": kl_zone,
            "overall_zone": overall_zone,
            "ima_eligible": overall_zone != "red",
        })
        summary[overall_zone] += 1

    return {
        "desks": results,
        "summary": summary,
        "total_desks": len(desks),
        "ima_eligible_desks": summary["green"] + summary["amber"],
        "sa_fallback_desks": summary["red"],
    }


# =============================================================================
# IMCC and Total IMA Capital
# =============================================================================

def calculate_imcc(
    risk_factors: list[ESRiskFactor],
    es_current: float,
    ses: float,
    es_avg_60: float = None,
    ses_avg_60: float = None,
    config: FRTBIMAConfig = None,
) -> dict:
    """
    Calculate the Internal Models Capital Charge (IMCC).

    IMCC = max(ES_{t-1}, m_c * ES_avg_60)
         + max(SES_{t-1}, m_c * SES_avg_60)
         + NMRF

    where m_c = 1.5 * (1 + plus_factor).

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        All risk factors (modellable + non-modellable).
    es_current : float
        Most recent day's liquidity-adjusted ES.
    ses : float
        Stressed ES for the most recent day.
    es_avg_60 : float
        60-day average ES (defaults to es_current if not supplied).
    ses_avg_60 : float
        60-day average SES (defaults to ses if not supplied).
    config : FRTBIMAConfig
        Configuration with multiplication and plus factors.

    Returns
    -------
    dict
        IMCC breakdown: es_component, ses_component, nmrf, total.
    """
    if config is None:
        config = FRTBIMAConfig()

    if es_avg_60 is None:
        es_avg_60 = es_current
    if ses_avg_60 is None:
        ses_avg_60 = ses

    m_c = config.multiplication_factor * (1.0 + config.plus_factor)

    es_component = max(es_current, m_c * es_avg_60)
    ses_component = max(ses, m_c * ses_avg_60)

    nmrf_result = calculate_nmrf_charge(risk_factors)
    nmrf = nmrf_result["nmrf_total"]

    imcc = es_component + ses_component + nmrf

    return {
        "imcc": imcc,
        "es_component": es_component,
        "ses_component": ses_component,
        "nmrf": nmrf,
        "multiplication_factor_mc": m_c,
        "es_current": es_current,
        "ses_current": ses,
        "es_avg_60": es_avg_60,
        "ses_avg_60": ses_avg_60,
        "nmrf_detail": nmrf_result,
    }


def calculate_frtb_ima_capital(
    risk_factors: list[ESRiskFactor],
    drc_positions: list[DRCPosition],
    config: FRTBIMAConfig = None,
    es_avg_60: float = None,
    ses_avg_60: float = None,
    desks: list[DeskPLA] = None,
) -> dict:
    """
    Calculate total FRTB-IMA capital.

    IMA Capital = IMCC + DRC_IMA

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        All risk factors (modellable and non-modellable).
    drc_positions : list[DRCPosition]
        DRC portfolio positions.
    config : FRTBIMAConfig
        Configuration for the calculation.
    es_avg_60 : float
        60-day average ES (optional).
    ses_avg_60 : float
        60-day average SES (optional).
    desks : list[DeskPLA]
        PLA desk results (optional — for reporting).

    Returns
    -------
    dict
        Full IMA capital breakdown.
    """
    if config is None:
        config = FRTBIMAConfig()

    # --- Expected Shortfall ---
    es_result = calculate_liquidity_adjusted_es(risk_factors)
    es_current = es_result["es_total"]

    # --- Stressed ES ---
    # Build reduced set: factors with stressed values
    reduced_factors = [rf for rf in risk_factors if rf.stressed_es_10day is not None]
    if reduced_factors:
        reduced_current = calculate_liquidity_adjusted_es(reduced_factors)["es_total"]
    else:
        reduced_current = es_current

    ses_result = calculate_stressed_es(risk_factors, es_current, reduced_current)
    ses = ses_result["ses_total"]

    # --- IMCC ---
    imcc_result = calculate_imcc(
        risk_factors, es_current, ses,
        es_avg_60=es_avg_60, ses_avg_60=ses_avg_60,
        config=config,
    )

    # --- DRC ---
    drc_result = calculate_ima_drc(drc_positions, config)

    # --- Backtesting ---
    bt_result = evaluate_backtesting(config.backtesting_exceptions)

    # --- PLA ---
    pla_result = evaluate_pla(desks) if desks else None

    # --- Total ---
    total_capital = imcc_result["imcc"] + drc_result["drc_charge"]
    total_rwa = total_capital * 12.5

    return {
        "approach": "FRTB-IMA",
        "total_capital": total_capital,
        "total_rwa": total_rwa,
        "imcc": imcc_result["imcc"],
        "imcc_detail": imcc_result,
        "es": es_result,
        "ses": ses_result,
        "drc_charge": drc_result["drc_charge"],
        "drc_detail": drc_result,
        "backtesting": bt_result,
        "pla": pla_result,
        "config": {
            "multiplication_factor": config.multiplication_factor,
            "plus_factor": config.plus_factor,
            "es_confidence": config.es_confidence,
            "drc_confidence": config.drc_confidence,
            "drc_num_simulations": config.drc_num_simulations,
        },
    }


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_frtb_ima(
    es_10day_total: float,
    stressed_es_10day_total: float,
    drc_positions: list[dict] = None,
    plus_factor: float = 0.0,
) -> dict:
    """
    Quick FRTB-IMA estimate from minimal inputs.

    Parameters
    ----------
    es_10day_total : float
        Aggregate 10-day ES across all modellable risk factors.
    stressed_es_10day_total : float
        Aggregate stressed 10-day ES.
    drc_positions : list[dict]
        Simplified DRC positions (obligor, notional, pd, lgd).
    plus_factor : float
        Backtesting plus factor (0.0 – 0.5).

    Returns
    -------
    dict
        Simplified IMA capital breakdown.
    """
    config = FRTBIMAConfig(plus_factor=plus_factor)

    # Build a single aggregate risk factor
    rf = ESRiskFactor(
        risk_class="IR", sub_category="major",
        es_10day=es_10day_total,
        stressed_es_10day=stressed_es_10day_total,
    )

    # Build DRC positions
    drc_pos = []
    if drc_positions:
        for i, p in enumerate(drc_positions):
            drc_pos.append(DRCPosition(
                position_id=p.get("position_id", f"pos_{i}"),
                obligor=p.get("obligor", f"obligor_{i}"),
                notional=p.get("notional", 0),
                market_value=p.get("market_value", p.get("notional", 0)),
                pd=p.get("pd", RATING_TO_PD.get(p.get("rating", "BBB"), 0.004)),
                lgd=p.get("lgd", 0.45),
                is_long=p.get("is_long", True),
            ))

    return calculate_frtb_ima_capital([rf], drc_pos, config)


def compare_ima_vs_sa(
    risk_factors: list[ESRiskFactor],
    drc_positions_ima: list[DRCPosition],
    delta_positions_sa: dict,
    drc_positions_sa: list[dict] = None,
    config: FRTBIMAConfig = None,
) -> dict:
    """
    Side-by-side comparison of FRTB-IMA vs FRTB-SA capital.

    Parameters
    ----------
    risk_factors : list[ESRiskFactor]
        Risk factors for IMA ES calculation.
    drc_positions_ima : list[DRCPosition]
        DRC positions for IMA.
    delta_positions_sa : dict
        Delta positions for SA, keyed by risk class.
    drc_positions_sa : list[dict]
        DRC positions for SA.
    config : FRTBIMAConfig
        IMA configuration.

    Returns
    -------
    dict
        IMA result, SA result, and comparison metrics.
    """
    ima_result = calculate_frtb_ima_capital(risk_factors, drc_positions_ima, config)

    sa_result = calculate_frtb_sa(
        delta_positions=delta_positions_sa,
        drc_positions=drc_positions_sa or [],
    )

    ima_capital = ima_result["total_capital"]
    sa_capital = sa_result["total_capital"]
    ratio = ima_capital / sa_capital if sa_capital > 0 else float("inf")

    return {
        "ima": ima_result,
        "sa": sa_result,
        "ima_capital": ima_capital,
        "sa_capital": sa_capital,
        "ima_to_sa_ratio": ratio,
        "ima_savings_pct": (1.0 - ratio) * 100 if ratio < float("inf") else 0.0,
    }


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("FRTB Internal Models Approach (IMA) — Full Calculation")
    print("=" * 70)

    # --- Risk factors for ES ---
    risk_factors = [
        ESRiskFactor("IR", "major",      es_10day=2_500_000, stressed_es_10day=4_000_000),
        ESRiskFactor("IR", "other",      es_10day=800_000,   stressed_es_10day=1_200_000),
        ESRiskFactor("CR", "IG_sovereign", es_10day=600_000, stressed_es_10day=1_000_000),
        ESRiskFactor("CR", "IG_corporate", es_10day=1_200_000, stressed_es_10day=2_000_000),
        ESRiskFactor("CR", "HY",         es_10day=900_000,   stressed_es_10day=1_800_000),
        ESRiskFactor("EQ", "large_cap",  es_10day=1_500_000, stressed_es_10day=3_000_000),
        ESRiskFactor("EQ", "small_cap",  es_10day=400_000,   stressed_es_10day=800_000),
        ESRiskFactor("FX", "major",      es_10day=700_000,   stressed_es_10day=1_100_000),
        ESRiskFactor("COM", "energy",    es_10day=500_000,   stressed_es_10day=1_000_000),
        # Non-modellable factors
        ESRiskFactor("CR", "other", es_10day=300_000,
                     is_modellable=False, stressed_es_10day=600_000),
        ESRiskFactor("COM", "other", es_10day=150_000,
                     is_modellable=False, stressed_es_10day=350_000),
    ]

    # --- DRC positions ---
    drc_positions = [
        DRCPosition("bond_1", "Corp_A", 10_000_000, 9_800_000, pd=0.004, lgd=0.45,
                     sector="financial", systematic_factor=0.20),
        DRCPosition("bond_2", "Corp_A", 5_000_000, 4_900_000, pd=0.004, lgd=0.45,
                     sector="financial", systematic_factor=0.20, is_long=False),
        DRCPosition("bond_3", "Corp_B", 8_000_000, 7_600_000, pd=0.02, lgd=0.45,
                     sector="energy", systematic_factor=0.18),
        DRCPosition("bond_4", "Corp_C", 6_000_000, 5_700_000, pd=0.055, lgd=0.60,
                     seniority="subordinated", sector="tech", systematic_factor=0.22),
        DRCPosition("bond_5", "Corp_D", 12_000_000, 11_500_000, pd=0.009, lgd=0.45,
                     sector="financial", systematic_factor=0.20),
        DRCPosition("cds_1", "Corp_B", 4_000_000, 3_900_000, pd=0.02, lgd=0.45,
                     sector="energy", systematic_factor=0.18, is_long=False),
    ]

    # --- Desk PLA ---
    desks = [
        DeskPLA("rates_desk", spearman_correlation=0.92, kl_divergence=0.05),
        DeskPLA("credit_desk", spearman_correlation=0.85, kl_divergence=0.08),
        DeskPLA("equity_desk", spearman_correlation=0.78, kl_divergence=0.10),
        DeskPLA("fx_desk", spearman_correlation=0.60, kl_divergence=0.15),
    ]

    config = FRTBIMAConfig(
        plus_factor=0.0,
        drc_num_simulations=50_000,
        backtesting_exceptions=3,
    )

    result = calculate_frtb_ima_capital(
        risk_factors, drc_positions, config, desks=desks,
    )

    # --- Print results ---
    print("\n  Expected Shortfall (ES)")
    print(f"    Liquidity-adjusted ES:   ${result['es']['es_total']:>14,.0f}")
    print(f"    Modellable factors:      {result['es']['num_factors']:>14}")
    if result['es']['es_by_bucket']:
        print("    By liquidity horizon:")
        for lh, info in sorted(result['es']['es_by_bucket'].items()):
            print(f"      {lh:>3}d:  ES_10d=${info['es_10day_sum']:>12,.0f}  "
                  f"scale={info['scale_factor']:.3f}  "
                  f"contrib=${info['contribution']:>12,.0f}")

    print(f"\n  Stressed ES (SES)")
    print(f"    SES:                     ${result['ses']['ses_total']:>14,.0f}")
    print(f"    Ratio (full/reduced):    {result['ses']['ratio']:>14.3f}")

    imcc = result['imcc_detail']
    print(f"\n  IMCC Breakdown")
    print(f"    ES component:            ${imcc['es_component']:>14,.0f}")
    print(f"    SES component:           ${imcc['ses_component']:>14,.0f}")
    print(f"    NMRF add-on:             ${imcc['nmrf']:>14,.0f}")
    print(f"    m_c (mult factor):       {imcc['multiplication_factor_mc']:>14.2f}")
    print(f"    IMCC total:              ${imcc['imcc']:>14,.0f}")

    drc = result['drc_detail']
    print(f"\n  Internal DRC (Monte Carlo)")
    print(f"    Simulations:             {drc['num_simulations']:>14,}")
    print(f"    Obligors:                {drc['num_obligors']:>14}")
    print(f"    Mean loss:               ${drc['mean_loss']:>14,.0f}")
    print(f"    95th percentile:         ${drc['percentile_95']:>14,.0f}")
    print(f"    99th percentile:         ${drc['percentile_99']:>14,.0f}")
    print(f"    99.9th percentile (DRC): ${drc['drc_charge']:>14,.0f}")

    bt = result['backtesting']
    print(f"\n  Backtesting")
    print(f"    Exceptions:              {bt['num_exceptions']:>14}")
    print(f"    Zone:                    {bt['zone']:>14}")
    print(f"    Plus factor:             {bt['plus_factor']:>14.2f}")

    if result['pla']:
        pla = result['pla']
        print(f"\n  P&L Attribution Test")
        print(f"    Total desks:             {pla['total_desks']:>14}")
        print(f"    IMA eligible:            {pla['ima_eligible_desks']:>14}")
        print(f"    SA fallback:             {pla['sa_fallback_desks']:>14}")
        for d in pla['desks']:
            status = "PASS" if d['ima_eligible'] else "FAIL->SA"
            print(f"      {d['desk_id']:<16} Spearman={d['spearman_correlation']:.2f} "
                  f"KL={d['kl_divergence']:.3f}  [{d['overall_zone']:>5}] {status}")

    print(f"\n  {'='*50}")
    print(f"  TOTAL IMA CAPITAL:         ${result['total_capital']:>14,.0f}")
    print(f"  TOTAL IMA RWA:             ${result['total_rwa']:>14,.0f}")
    print(f"  {'='*50}")

    # =================================================================
    # Example 2: IMA vs SA comparison
    # =================================================================
    print("\n\n" + "=" * 70)
    print("FRTB IMA vs SA Comparison")
    print("=" * 70)

    # SA delta positions (matching the IMA risk factors above)
    delta_positions_sa = {
        "EQ": [
            {"bucket": "large_cap_developed", "sensitivity": 1_500_000, "risk_weight": 20},
            {"bucket": "small_cap_developed", "sensitivity": 400_000, "risk_weight": 30},
        ],
        "FX": [
            {"bucket": "USD_EUR", "sensitivity": 700_000, "risk_weight": 15},
        ],
    }

    drc_positions_sa = [
        {"obligor": "Corp_A", "notional": 10_000_000, "rating": "BBB",
         "seniority": "senior", "sector": "financial", "is_long": True},
        {"obligor": "Corp_A", "notional": 5_000_000, "rating": "BBB",
         "seniority": "senior", "sector": "financial", "is_long": False},
        {"obligor": "Corp_B", "notional": 8_000_000, "rating": "BB",
         "seniority": "senior", "sector": "energy", "is_long": True},
        {"obligor": "Corp_C", "notional": 6_000_000, "rating": "B",
         "seniority": "subordinated", "sector": "tech", "is_long": True},
        {"obligor": "Corp_D", "notional": 12_000_000, "rating": "A",
         "seniority": "senior", "sector": "financial", "is_long": True},
        {"obligor": "Corp_B", "notional": 4_000_000, "rating": "BB",
         "seniority": "senior", "sector": "energy", "is_long": False},
    ]

    comparison = compare_ima_vs_sa(
        risk_factors=risk_factors,
        drc_positions_ima=drc_positions,
        delta_positions_sa=delta_positions_sa,
        drc_positions_sa=drc_positions_sa,
        config=config,
    )

    print(f"\n  IMA Capital:               ${comparison['ima_capital']:>14,.0f}")
    print(f"  SA Capital:                ${comparison['sa_capital']:>14,.0f}")
    print(f"  IMA / SA ratio:            {comparison['ima_to_sa_ratio']:>14.2f}")
    if comparison['ima_to_sa_ratio'] < 1.0:
        print(f"  IMA savings:               {comparison['ima_savings_pct']:>13.1f}%")
    else:
        print(f"  IMA excess:                {-comparison['ima_savings_pct']:>13.1f}%")
