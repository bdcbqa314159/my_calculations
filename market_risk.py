"""
Market Risk - FRTB Standardised Approach

Implements:
- SbM: Sensitivities-based Method (delta, vega, curvature)
- DRC: Default Risk Charge
- RRAO: Residual Risk Add-On
"""

import math
from typing import Optional


# =============================================================================
# FRTB Risk Weights and Correlations (MAR21)
# =============================================================================

# GIRR (General Interest Rate Risk) - MAR21.42-45
GIRR_RISK_WEIGHTS = {
    # Vertex (years): risk weight in %
    0.25: 1.7,
    0.5: 1.7,
    1: 1.6,
    2: 1.3,
    3: 1.2,
    5: 1.1,
    10: 1.1,
    15: 1.1,
    20: 1.1,
    30: 1.1,
}

GIRR_INFLATION_RW = 1.6
GIRR_CROSS_CURRENCY_RW = 1.6

# CSR (Credit Spread Risk) - Non-securitization - MAR21.53
CSR_RISK_WEIGHTS = {
    # Bucket: (1Y, 3Y, 5Y, 10Y)
    "sovereign_IG": (0.5, 0.5, 0.5, 0.5),
    "sovereign_HY": (3.0, 3.0, 3.0, 3.0),
    "corporate_IG": (1.0, 1.0, 1.0, 1.0),
    "corporate_HY": (5.0, 5.0, 5.0, 5.0),
    "financial_IG": (1.5, 1.5, 1.5, 1.5),
    "financial_HY": (7.5, 7.5, 7.5, 7.5),
    "covered_bond": (1.0, 1.0, 1.0, 1.0),
}

# EQ (Equity Risk) - MAR21.77
EQ_RISK_WEIGHTS = {
    # Bucket: (spot RW, repo RW)
    "large_cap_developed": (20, 0.55),
    "large_cap_emerging": (30, 0.60),
    "small_cap_developed": (30, 0.60),
    "small_cap_emerging": (50, 0.75),
    "volatility_index": (70, 0.10),
    "other": (50, 0.75),
}

# FX Risk - MAR21.88
FX_RISK_WEIGHT = 15.0  # 15% for all currency pairs
FX_LIQUID_PAIRS_RW = 11.25  # Reduced for liquid pairs (USD/EUR, USD/JPY, etc.)

# Commodity Risk - MAR21.82
COM_RISK_WEIGHTS = {
    "energy_solid": 30,
    "energy_liquid": 25,
    "energy_electricity": 60,
    "freight": 80,
    "metals_precious": 20,
    "metals_non_precious": 30,
    "agriculture_grains": 25,
    "agriculture_softs": 30,
    "other": 50,
}

# Correlations (simplified - representative values)
CORRELATIONS = {
    "GIRR_same_curve": 0.99,
    "GIRR_different_curve": 0.50,
    "CSR_same_bucket": 0.75,
    "CSR_different_bucket": 0.25,
    "EQ_same_bucket": 0.20,
    "EQ_different_bucket": 0.15,
    "FX": 0.60,
    "COM_same_bucket": 0.55,
    "COM_different_bucket": 0.20,
}


# =============================================================================
# Sensitivities-based Method (SbM) - MAR21
# =============================================================================

def calculate_delta_sensitivity(
    position_value: float,
    risk_factor_shift: float = 0.01,  # 1bp or 1%
    shifted_value: float = None,
    sensitivity_type: str = "IR"
) -> float:
    """
    Calculate delta sensitivity.

    For IR: s = dV/dr (PV01)
    For EQ/FX: s = dV/dS * S (delta * spot)
    """
    if shifted_value is not None:
        return (shifted_value - position_value) / risk_factor_shift

    # Default: assume 1% sensitivity
    return position_value * risk_factor_shift


def calculate_vega_sensitivity(
    option_value: float,
    volatility: float,
    volatility_shift: float = 0.01  # 1% vol shift
) -> float:
    """
    Calculate vega sensitivity.

    vega = dV/d(sigma) * sigma
    """
    return option_value * volatility * volatility_shift


def calculate_curvature_sensitivity(
    position_value: float,
    up_shifted_value: float,
    down_shifted_value: float,
    risk_factor_shift: float = 0.01
) -> tuple:
    """
    Calculate curvature sensitivities.

    CVR_up = -V_up + V_0 + RW * s
    CVR_down = -V_down + V_0 - RW * s
    CVR = max(CVR_up, CVR_down, 0)
    """
    delta = (up_shifted_value - down_shifted_value) / (2 * risk_factor_shift)

    cvr_up = -up_shifted_value + position_value + risk_factor_shift * delta
    cvr_down = -down_shifted_value + position_value - risk_factor_shift * delta

    cvr = max(cvr_up, cvr_down, 0)

    return cvr, cvr_up, cvr_down


def aggregate_sensitivities_within_bucket(
    sensitivities: list[float],
    correlation: float = 0.50
) -> float:
    """
    Aggregate sensitivities within a bucket using correlation.

    K_b = sqrt(sum(s_i^2) + 2 * rho * sum_{i<j}(s_i * s_j))
        = sqrt(sum(s_i^2) + rho * ((sum(s_i))^2 - sum(s_i^2)))
    """
    sum_s = sum(sensitivities)
    sum_s_sq = sum(s**2 for s in sensitivities)

    k_b = math.sqrt(max(sum_s_sq + correlation * (sum_s**2 - sum_s_sq), 0))
    return k_b


def aggregate_across_buckets(
    bucket_capitals: dict,
    bucket_sensitivities: dict,
    inter_bucket_correlation: float = 0.25
) -> float:
    """
    Aggregate across buckets.

    K = sqrt(sum(K_b^2) + 2 * sum_{b<c}(gamma_{bc} * S_b * S_c))
    """
    buckets = list(bucket_capitals.keys())
    sum_k_sq = sum(k**2 for k in bucket_capitals.values())

    cross_term = 0
    for i, b1 in enumerate(buckets):
        for b2 in buckets[i+1:]:
            s_b = bucket_sensitivities.get(b1, 0)
            s_c = bucket_sensitivities.get(b2, 0)
            cross_term += inter_bucket_correlation * s_b * s_c

    k_total = math.sqrt(max(sum_k_sq + 2 * cross_term, 0))
    return k_total


def calculate_delta_capital(
    positions: list[dict],
    risk_class: str = "GIRR"
) -> dict:
    """
    Calculate delta capital for a risk class.

    Parameters:
    -----------
    positions : list of dict
        Each should have: bucket, vertex (for IR), sensitivity, risk_weight
    risk_class : str
        GIRR, CSR, EQ, FX, or COM

    Returns:
    --------
    dict
        Delta capital calculation results
    """
    # Get appropriate risk weights and correlations
    if risk_class == "GIRR":
        risk_weights = GIRR_RISK_WEIGHTS
        intra_corr = CORRELATIONS["GIRR_same_curve"]
        inter_corr = CORRELATIONS["GIRR_different_curve"]
    elif risk_class == "CSR":
        intra_corr = CORRELATIONS["CSR_same_bucket"]
        inter_corr = CORRELATIONS["CSR_different_bucket"]
    elif risk_class == "EQ":
        intra_corr = CORRELATIONS["EQ_same_bucket"]
        inter_corr = CORRELATIONS["EQ_different_bucket"]
    elif risk_class == "FX":
        intra_corr = CORRELATIONS["FX"]
        inter_corr = CORRELATIONS["FX"]
    else:  # COM
        intra_corr = CORRELATIONS["COM_same_bucket"]
        inter_corr = CORRELATIONS["COM_different_bucket"]

    # Group positions by bucket
    buckets = {}
    for pos in positions:
        bucket = pos.get("bucket", "default")
        if bucket not in buckets:
            buckets[bucket] = []

        # Calculate weighted sensitivity
        sensitivity = pos.get("sensitivity", 0)
        rw = pos.get("risk_weight", 1.0) / 100  # Convert from %
        weighted_sens = sensitivity * rw

        buckets[bucket].append({
            "sensitivity": sensitivity,
            "risk_weight": rw,
            "weighted_sensitivity": weighted_sens,
        })

    # Calculate bucket-level capital
    bucket_capitals = {}
    bucket_net_sens = {}

    for bucket, positions_in_bucket in buckets.items():
        weighted_sens = [p["weighted_sensitivity"] for p in positions_in_bucket]
        k_b = aggregate_sensitivities_within_bucket(weighted_sens, intra_corr)
        bucket_capitals[bucket] = k_b
        bucket_net_sens[bucket] = sum(weighted_sens)

    # Aggregate across buckets
    k_delta = aggregate_across_buckets(bucket_capitals, bucket_net_sens, inter_corr)

    return {
        "risk_class": risk_class,
        "component": "delta",
        "capital": k_delta,
        "bucket_capitals": bucket_capitals,
        "bucket_net_sensitivities": bucket_net_sens,
    }


def calculate_vega_capital(
    positions: list[dict],
    risk_class: str = "EQ"
) -> dict:
    """
    Calculate vega capital for a risk class.

    Similar structure to delta but uses vega sensitivities.
    """
    # Vega risk weights are generally higher
    vega_multiplier = 1.0  # Liquidity horizon adjustment

    buckets = {}
    for pos in positions:
        bucket = pos.get("bucket", "default")
        if bucket not in buckets:
            buckets[bucket] = []

        vega = pos.get("vega", 0)
        rw = pos.get("vega_risk_weight", 50) / 100
        weighted_vega = vega * rw * vega_multiplier

        buckets[bucket].append({"weighted_vega": weighted_vega})

    # Get correlations
    if risk_class == "EQ":
        intra_corr = 0.60
        inter_corr = 0.20
    else:
        intra_corr = 0.50
        inter_corr = 0.25

    bucket_capitals = {}
    bucket_net_vega = {}

    for bucket, positions_in_bucket in buckets.items():
        weighted_vegas = [p["weighted_vega"] for p in positions_in_bucket]
        k_b = aggregate_sensitivities_within_bucket(weighted_vegas, intra_corr)
        bucket_capitals[bucket] = k_b
        bucket_net_vega[bucket] = sum(weighted_vegas)

    k_vega = aggregate_across_buckets(bucket_capitals, bucket_net_vega, inter_corr)

    return {
        "risk_class": risk_class,
        "component": "vega",
        "capital": k_vega,
        "bucket_capitals": bucket_capitals,
    }


def calculate_curvature_capital(
    positions: list[dict],
    risk_class: str = "EQ"
) -> dict:
    """
    Calculate curvature capital for a risk class.
    """
    buckets = {}
    for pos in positions:
        bucket = pos.get("bucket", "default")
        if bucket not in buckets:
            buckets[bucket] = {"cvr_up": 0, "cvr_down": 0}

        cvr_up = pos.get("cvr_up", 0)
        cvr_down = pos.get("cvr_down", 0)

        buckets[bucket]["cvr_up"] += cvr_up
        buckets[bucket]["cvr_down"] += cvr_down

    bucket_capitals = {}
    for bucket, cvrs in buckets.items():
        k_b = max(cvrs["cvr_up"], cvrs["cvr_down"], 0)
        bucket_capitals[bucket] = k_b

    # Cross-bucket aggregation (simplified)
    k_curvature = sum(bucket_capitals.values())

    return {
        "risk_class": risk_class,
        "component": "curvature",
        "capital": k_curvature,
        "bucket_capitals": bucket_capitals,
    }


def calculate_sbm_capital(
    delta_positions: list[dict],
    vega_positions: list[dict] = None,
    curvature_positions: list[dict] = None,
    risk_class: str = "EQ"
) -> dict:
    """
    Calculate total SbM capital for a risk class.

    K_total = K_delta + K_vega + K_curvature
    """
    vega_positions = vega_positions or []
    curvature_positions = curvature_positions or []

    delta_result = calculate_delta_capital(delta_positions, risk_class)
    vega_result = calculate_vega_capital(vega_positions, risk_class) if vega_positions else {"capital": 0}
    curvature_result = calculate_curvature_capital(curvature_positions, risk_class) if curvature_positions else {"capital": 0}

    total_capital = (
        delta_result["capital"] +
        vega_result.get("capital", 0) +
        curvature_result.get("capital", 0)
    )

    return {
        "risk_class": risk_class,
        "approach": "SbM",
        "delta_capital": delta_result["capital"],
        "vega_capital": vega_result.get("capital", 0),
        "curvature_capital": curvature_result.get("capital", 0),
        "total_capital": total_capital,
        "delta_detail": delta_result,
        "vega_detail": vega_result,
        "curvature_detail": curvature_result,
    }


# =============================================================================
# Default Risk Charge (DRC) - MAR22
# =============================================================================

# DRC Risk Weights by rating (MAR22.12)
DRC_RISK_WEIGHTS = {
    "AAA": 0.5,
    "AA": 0.5,
    "A": 1.0,
    "BBB": 2.0,
    "BB": 5.0,
    "B": 10.0,
    "CCC": 15.0,
    "D": 30.0,
    "unrated": 15.0,
}

# DRC LGD (MAR22.14)
DRC_LGD = {
    "senior": 0.75,      # 25% recovery
    "subordinated": 1.0,  # 0% recovery
    "covered_bond": 0.625,  # 37.5% recovery
    "equity": 1.0,       # 0% recovery
}

# DRC Correlations (MAR22.19)
DRC_CORRELATIONS = {
    "same_obligor": 1.0,
    "different_obligor_same_sector": 0.50,
    "different_sector": 0.25,
}


def calculate_drc_charge(
    positions: list[dict]
) -> dict:
    """
    Calculate Default Risk Charge.

    DRC = sum(max(JTD_long * LGD, JTD_short * LGD, 0))

    With netting within same obligor and sector correlation.

    Parameters:
    -----------
    positions : list of dict
        Each should have: obligor, notional, rating, seniority, sector, is_long

    Returns:
    --------
    dict
        DRC calculation results
    """
    # Group by obligor
    obligors = {}
    for pos in positions:
        obligor = pos.get("obligor", "default")
        if obligor not in obligors:
            obligors[obligor] = {
                "positions": [],
                "sector": pos.get("sector", "other"),
                "rating": pos.get("rating", "BBB"),
            }
        obligors[obligor]["positions"].append(pos)

    # Calculate JTD for each obligor
    obligor_jtds = {}
    for obligor, data in obligors.items():
        jtd_long = 0
        jtd_short = 0

        for pos in data["positions"]:
            notional = pos["notional"]
            seniority = pos.get("seniority", "senior")
            lgd = DRC_LGD.get(seniority, 0.75)
            is_long = pos.get("is_long", True)

            jtd = notional * lgd
            if is_long:
                jtd_long += jtd
            else:
                jtd_short += jtd

        # Net JTD for obligor
        net_jtd = jtd_long - jtd_short
        obligor_jtds[obligor] = {
            "jtd_long": jtd_long,
            "jtd_short": jtd_short,
            "net_jtd": net_jtd,
            "sector": data["sector"],
            "rating": data["rating"],
        }

    # Apply risk weights and aggregate
    drc_by_obligor = {}
    total_drc = 0

    for obligor, jtd_data in obligor_jtds.items():
        rating = jtd_data["rating"]
        rw = DRC_RISK_WEIGHTS.get(rating, DRC_RISK_WEIGHTS["unrated"]) / 100

        # DRC = max(net_JTD, 0) * RW
        drc = max(jtd_data["net_jtd"], 0) * rw

        drc_by_obligor[obligor] = {
            "net_jtd": jtd_data["net_jtd"],
            "risk_weight": rw,
            "drc": drc,
        }
        total_drc += drc

    return {
        "approach": "DRC",
        "total_drc": total_drc,
        "rwa": total_drc * 12.5,
        "obligors": drc_by_obligor,
    }


# =============================================================================
# Residual Risk Add-On (RRAO) - MAR23
# =============================================================================

# RRAO percentages (MAR23.3)
RRAO_EXOTIC_RATE = 0.01  # 1% for exotic underlyings
RRAO_OTHER_RATE = 0.001  # 0.1% for other residual risks


def calculate_rrao(
    positions: list[dict]
) -> dict:
    """
    Calculate Residual Risk Add-On.

    For instruments with exotic underlyings or bearing other residual risks.

    Parameters:
    -----------
    positions : list of dict
        Each should have: notional, is_exotic, has_other_residual_risk

    Returns:
    --------
    dict
        RRAO calculation results
    """
    exotic_notional = 0
    other_notional = 0

    for pos in positions:
        notional = pos.get("notional", 0)

        if pos.get("is_exotic", False):
            exotic_notional += notional
        elif pos.get("has_other_residual_risk", False):
            other_notional += notional

    exotic_charge = exotic_notional * RRAO_EXOTIC_RATE
    other_charge = other_notional * RRAO_OTHER_RATE

    total_rrao = exotic_charge + other_charge

    return {
        "approach": "RRAO",
        "exotic_notional": exotic_notional,
        "exotic_charge": exotic_charge,
        "other_notional": other_notional,
        "other_charge": other_charge,
        "total_rrao": total_rrao,
        "rwa": total_rrao * 12.5,
    }


# =============================================================================
# Total FRTB Standardised Approach
# =============================================================================

def calculate_frtb_sa(
    delta_positions: dict,  # {risk_class: [positions]}
    vega_positions: dict = None,
    curvature_positions: dict = None,
    drc_positions: list[dict] = None,
    rrao_positions: list[dict] = None
) -> dict:
    """
    Calculate total FRTB Standardised Approach capital.

    K_FRTB = K_SbM + K_DRC + K_RRAO

    Where K_SbM = sum of all risk class capitals

    Parameters:
    -----------
    delta_positions : dict
        Delta positions by risk class {GIRR: [...], EQ: [...], etc.}
    vega_positions : dict
        Vega positions by risk class
    curvature_positions : dict
        Curvature positions by risk class
    drc_positions : list
        Positions for DRC calculation
    rrao_positions : list
        Positions for RRAO calculation

    Returns:
    --------
    dict
        Total FRTB-SA calculation results
    """
    vega_positions = vega_positions or {}
    curvature_positions = curvature_positions or {}
    drc_positions = drc_positions or []
    rrao_positions = rrao_positions or []

    # Calculate SbM by risk class
    sbm_results = {}
    total_sbm = 0

    for risk_class, positions in delta_positions.items():
        vega = vega_positions.get(risk_class, [])
        curvature = curvature_positions.get(risk_class, [])

        result = calculate_sbm_capital(positions, vega, curvature, risk_class)
        sbm_results[risk_class] = result
        total_sbm += result["total_capital"]

    # Calculate DRC
    drc_result = calculate_drc_charge(drc_positions) if drc_positions else {"total_drc": 0, "rwa": 0}

    # Calculate RRAO
    rrao_result = calculate_rrao(rrao_positions) if rrao_positions else {"total_rrao": 0, "rwa": 0}

    # Total capital
    total_capital = total_sbm + drc_result["total_drc"] + rrao_result["total_rrao"]
    total_rwa = total_capital * 12.5

    return {
        "approach": "FRTB-SA",
        "sbm_capital": total_sbm,
        "sbm_by_risk_class": sbm_results,
        "drc_capital": drc_result["total_drc"],
        "drc_detail": drc_result,
        "rrao_capital": rrao_result["total_rrao"],
        "rrao_detail": rrao_result,
        "total_capital": total_capital,
        "total_rwa": total_rwa,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("FRTB Standardised Approach - SbM Example")
    print("=" * 70)

    # Equity delta positions
    eq_positions = [
        {"bucket": "large_cap_developed", "sensitivity": 1_000_000, "risk_weight": 20},
        {"bucket": "large_cap_developed", "sensitivity": -500_000, "risk_weight": 20},
        {"bucket": "large_cap_emerging", "sensitivity": 300_000, "risk_weight": 30},
    ]

    sbm_result = calculate_sbm_capital(eq_positions, risk_class="EQ")

    print(f"\n  Equity Delta Capital:    ${sbm_result['delta_capital']:,.0f}")
    print(f"  By bucket:")
    for bucket, k in sbm_result['delta_detail']['bucket_capitals'].items():
        print(f"    {bucket}: ${k:,.0f}")

    print("\n" + "=" * 70)
    print("DRC Example")
    print("=" * 70)

    drc_positions = [
        {"obligor": "Corp_A", "notional": 5_000_000, "rating": "A", "seniority": "senior", "sector": "financial", "is_long": True},
        {"obligor": "Corp_A", "notional": 2_000_000, "rating": "A", "seniority": "senior", "sector": "financial", "is_long": False},
        {"obligor": "Corp_B", "notional": 3_000_000, "rating": "BB", "seniority": "senior", "sector": "tech", "is_long": True},
    ]

    drc_result = calculate_drc_charge(drc_positions)

    print(f"\n  Total DRC:               ${drc_result['total_drc']:,.0f}")
    print(f"  DRC RWA:                 ${drc_result['rwa']:,.0f}")
    print(f"\n  By obligor:")
    for obligor, data in drc_result['obligors'].items():
        print(f"    {obligor}: Net JTD=${data['net_jtd']:,.0f}, RW={data['risk_weight']*100:.0f}%, DRC=${data['drc']:,.0f}")

    print("\n" + "=" * 70)
    print("RRAO Example")
    print("=" * 70)

    rrao_positions = [
        {"notional": 10_000_000, "is_exotic": True},
        {"notional": 50_000_000, "has_other_residual_risk": True},
    ]

    rrao_result = calculate_rrao(rrao_positions)

    print(f"\n  Exotic charge:           ${rrao_result['exotic_charge']:,.0f}")
    print(f"  Other charge:            ${rrao_result['other_charge']:,.0f}")
    print(f"  Total RRAO:              ${rrao_result['total_rrao']:,.0f}")

    print("\n" + "=" * 70)
    print("Total FRTB-SA")
    print("=" * 70)

    frtb_result = calculate_frtb_sa(
        delta_positions={"EQ": eq_positions},
        drc_positions=drc_positions,
        rrao_positions=rrao_positions
    )

    print(f"\n  SbM Capital:             ${frtb_result['sbm_capital']:,.0f}")
    print(f"  DRC Capital:             ${frtb_result['drc_capital']:,.0f}")
    print(f"  RRAO Capital:            ${frtb_result['rrao_capital']:,.0f}")
    print(f"  Total Capital:           ${frtb_result['total_capital']:,.0f}")
    print(f"  Total RWA:               ${frtb_result['total_rwa']:,.0f}")
