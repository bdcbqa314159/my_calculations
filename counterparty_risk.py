"""
Counterparty Credit Risk - SA-CCR and CVA

Implements:
- SA-CCR: Standardised Approach for Counterparty Credit Risk
- BA-CVA: Basic Approach for Credit Valuation Adjustment
- SA-CVA: Standardised Approach for CVA
"""

import math
from typing import Optional


# =============================================================================
# SA-CCR (Standardised Approach for Counterparty Credit Risk) - CRE52
# =============================================================================

# Supervisory factors by asset class (CRE52.72)
SA_CCR_SUPERVISORY_FACTORS = {
    # Interest Rate
    "IR": {"SF": 0.50, "correlation": 1.0},

    # Foreign Exchange
    "FX": {"SF": 4.0, "correlation": 1.0},

    # Credit (single name)
    "CR_AAA_AA": {"SF": 0.38, "correlation": 0.50},
    "CR_A": {"SF": 0.42, "correlation": 0.50},
    "CR_BBB": {"SF": 0.54, "correlation": 0.50},
    "CR_BB": {"SF": 1.06, "correlation": 0.50},
    "CR_B": {"SF": 1.6, "correlation": 0.50},
    "CR_CCC": {"SF": 6.0, "correlation": 0.50},

    # Credit (index - IG)
    "CR_INDEX_IG": {"SF": 0.38, "correlation": 0.80},
    # Credit (index - SG)
    "CR_INDEX_SG": {"SF": 1.06, "correlation": 0.80},

    # Equity (single name)
    "EQ_SINGLE": {"SF": 32.0, "correlation": 0.50},
    # Equity (index)
    "EQ_INDEX": {"SF": 20.0, "correlation": 0.80},

    # Commodity
    "COM_ELECTRICITY": {"SF": 40.0, "correlation": 0.40},
    "COM_OIL_GAS": {"SF": 18.0, "correlation": 0.40},
    "COM_METALS": {"SF": 18.0, "correlation": 0.40},
    "COM_AGRICULTURAL": {"SF": 18.0, "correlation": 0.40},
    "COM_OTHER": {"SF": 18.0, "correlation": 0.40},
}

# Supervisory option volatilities (CRE52.74)
SA_CCR_OPTION_VOLATILITY = {
    "IR": 0.50,
    "FX": 0.15,
    "CR": 1.00,
    "EQ": 1.20,
    "COM": 1.50,
}

# Maturity factors
SA_CCR_MPOR = {
    "bilateral_no_margin": 1.0,  # Assumed 1 year
    "bilateral_margin": 10/250,  # 10 business days
    "ccp_margin": 5/250,  # 5 business days
    "disputed": 20/250,  # 20 business days
}


def calculate_maturity_factor(
    maturity: float,
    start_date: float = 0,
    is_margined: bool = False,
    mpor_days: int = 10
) -> float:
    """
    Calculate the maturity factor MF for SA-CCR.

    Parameters:
    -----------
    maturity : float
        Time to maturity in years
    start_date : float
        Start date for forward-starting transactions (years from now)
    is_margined : bool
        Whether the trade is subject to margin agreement
    mpor_days : int
        Margin period of risk in business days (for margined trades)

    Returns:
    --------
    float
        Maturity factor
    """
    if is_margined:
        # For margined trades: MF = 1.5 * sqrt(MPOR / 1 year)
        mpor_years = mpor_days / 250
        mf = 1.5 * math.sqrt(mpor_years)
    else:
        # For unmargined trades: MF = sqrt(min(M, 1) / 1 year)
        # where M = max(10 days, remaining maturity)
        m = max(10/250, min(maturity - start_date, 1))
        mf = math.sqrt(m)

    return mf


def calculate_supervisory_delta(
    position_type: str,
    is_long: bool,
    is_option: bool = False,
    option_type: str = None,  # "call" or "put"
    underlying_price: float = None,
    strike: float = None,
    time_to_expiry: float = None,
    volatility: float = None
) -> float:
    """
    Calculate the supervisory delta adjustment.

    For non-options: +1 (long) or -1 (short)
    For options: Uses supervisory formula based on option type
    """
    if not is_option:
        return 1.0 if is_long else -1.0

    # For options, calculate supervisory delta
    if option_type == "call":
        sign = 1 if is_long else -1
    else:  # put
        sign = -1 if is_long else 1

    # Simplified Black-Scholes delta approximation
    if underlying_price and strike and time_to_expiry and volatility:
        from scipy.stats import norm
        d1 = (math.log(underlying_price / strike) + 0.5 * volatility**2 * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
        if option_type == "call":
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        return sign * abs(delta)

    # Default supervisory delta for options
    return sign * 0.5


def calculate_adjusted_notional(
    notional: float,
    asset_class: str,
    maturity: float = 1.0,
    is_margined: bool = False,
    mpor_days: int = 10,
    supervisory_duration: float = None
) -> float:
    """
    Calculate the adjusted notional for SA-CCR.

    For IR and CR: d = notional * supervisory_duration
    For others: d = notional * maturity_factor
    """
    mf = calculate_maturity_factor(maturity, is_margined=is_margined, mpor_days=mpor_days)

    if asset_class.startswith("IR") or asset_class.startswith("CR"):
        # Use supervisory duration
        if supervisory_duration is None:
            # SD = (1 - exp(-0.05 * M)) / 0.05
            supervisory_duration = (1 - math.exp(-0.05 * maturity)) / 0.05
        return notional * supervisory_duration
    else:
        return notional * mf


def calculate_addon_single_trade(
    notional: float,
    asset_class: str,
    maturity: float = 1.0,
    delta: float = 1.0,
    is_margined: bool = False
) -> float:
    """
    Calculate the add-on for a single trade.

    AddOn = SF * |delta| * d
    """
    sf_data = SA_CCR_SUPERVISORY_FACTORS.get(asset_class, {"SF": 0.15, "correlation": 0.50})
    sf = sf_data["SF"] / 100  # Convert from percentage

    adjusted_notional = calculate_adjusted_notional(notional, asset_class, maturity, is_margined)

    addon = sf * abs(delta) * adjusted_notional
    return addon


def calculate_replacement_cost(
    mtm: float,
    collateral_held: float = 0,
    collateral_posted: float = 0,
    is_margined: bool = False,
    threshold: float = 0,
    mta: float = 0,
    nica: float = 0
) -> float:
    """
    Calculate Replacement Cost (RC) for SA-CCR.

    For unmargined: RC = max(V - C, 0)
    For margined: RC = max(V - C, TH + MTA - NICA, 0)

    Parameters:
    -----------
    mtm : float
        Current mark-to-market value (positive = asset)
    collateral_held : float
        Collateral received from counterparty
    collateral_posted : float
        Collateral posted to counterparty
    is_margined : bool
        Whether subject to margin agreement
    threshold : float
        Threshold amount (TH)
    mta : float
        Minimum transfer amount
    nica : float
        Net independent collateral amount
    """
    # Net collateral
    c = collateral_held - collateral_posted
    v = mtm

    if is_margined:
        rc = max(v - c, threshold + mta - nica, 0)
    else:
        rc = max(v - c, 0)

    return rc


def calculate_pfe_multiplier(
    mtm: float,
    collateral: float,
    addon_aggregate: float,
    floor: float = 0.05
) -> float:
    """
    Calculate the PFE multiplier.

    multiplier = min(1, floor + (1-floor) * exp((V-C) / (2*(1-floor)*AddOn)))
    """
    v_minus_c = mtm - collateral

    if addon_aggregate <= 0:
        return 1.0

    if v_minus_c >= 0:
        return 1.0

    exponent = v_minus_c / (2 * (1 - floor) * addon_aggregate)
    multiplier = min(1, floor + (1 - floor) * math.exp(exponent))

    return multiplier


def calculate_sa_ccr_ead(
    trades: list[dict],
    collateral_held: float = 0,
    collateral_posted: float = 0,
    is_margined: bool = False,
    threshold: float = 0,
    mta: float = 0,
    nica: float = 0,
    alpha: float = 1.4
) -> dict:
    """
    Calculate EAD using SA-CCR.

    EAD = alpha * (RC + PFE)

    Parameters:
    -----------
    trades : list of dict
        Each trade should have: notional, asset_class, maturity, mtm, delta
    collateral_held : float
        Collateral received
    collateral_posted : float
        Collateral posted
    is_margined : bool
        Whether margined
    alpha : float
        Alpha factor (default 1.4)

    Returns:
    --------
    dict
        EAD calculation results
    """
    # Calculate total MTM
    total_mtm = sum(t.get("mtm", 0) for t in trades)

    # Calculate RC
    rc = calculate_replacement_cost(
        total_mtm, collateral_held, collateral_posted,
        is_margined, threshold, mta, nica
    )

    # Calculate add-ons by asset class and aggregate
    addons_by_class = {}
    for t in trades:
        asset_class = t["asset_class"]
        addon = calculate_addon_single_trade(
            t["notional"],
            asset_class,
            t.get("maturity", 1.0),
            t.get("delta", 1.0),
            is_margined
        )
        if asset_class not in addons_by_class:
            addons_by_class[asset_class] = 0
        addons_by_class[asset_class] += addon

    # Aggregate add-on (simplified - sum of asset class add-ons)
    addon_aggregate = sum(addons_by_class.values())

    # Calculate multiplier
    net_collateral = collateral_held - collateral_posted
    multiplier = calculate_pfe_multiplier(total_mtm, net_collateral, addon_aggregate)

    # PFE = multiplier * AddOn_aggregate
    pfe = multiplier * addon_aggregate

    # EAD = alpha * (RC + PFE)
    ead = alpha * (rc + pfe)

    return {
        "approach": "SA-CCR",
        "replacement_cost": rc,
        "pfe": pfe,
        "addon_aggregate": addon_aggregate,
        "addons_by_class": addons_by_class,
        "multiplier": multiplier,
        "alpha": alpha,
        "ead": ead,
        "total_mtm": total_mtm,
        "net_collateral": net_collateral,
    }


# =============================================================================
# CVA (Credit Valuation Adjustment) - MAR50
# =============================================================================

# Risk weights for BA-CVA by rating (MAR50.17)
BA_CVA_RISK_WEIGHTS = {
    "AAA": 0.007,
    "AA": 0.007,
    "A": 0.008,
    "BBB": 0.010,
    "BB": 0.020,
    "B": 0.030,
    "CCC": 0.100,
    "unrated": 0.015,  # For corporates
    "unrated_financial": 0.010,  # For financials
}

# Supervisory correlation for BA-CVA
BA_CVA_CORRELATION = 0.5

# Discount factor supervisory rate
CVA_DISCOUNT_RATE = 0.05


def calculate_effective_maturity_cva(
    trades: list[dict]
) -> float:
    """
    Calculate effective maturity for CVA.

    M_eff = sum(EE_i * delta_t_i * df_i) / sum(EE_i * delta_t_i * df_i)

    Simplified: weighted average maturity
    """
    if not trades:
        return 1.0

    total_ead = sum(t.get("ead", t.get("notional", 0)) for t in trades)
    if total_ead == 0:
        return 1.0

    weighted_maturity = sum(
        t.get("maturity", 1.0) * t.get("ead", t.get("notional", 0))
        for t in trades
    )

    return weighted_maturity / total_ead


def calculate_supervisory_discount(maturity: float) -> float:
    """
    Calculate supervisory discount factor for CVA.

    DF = (1 - exp(-0.05 * M)) / (0.05 * M)
    """
    if maturity <= 0:
        return 1.0

    df = (1 - math.exp(-CVA_DISCOUNT_RATE * maturity)) / (CVA_DISCOUNT_RATE * maturity)
    return df


def calculate_ba_cva(
    counterparties: list[dict]
) -> dict:
    """
    Calculate CVA capital using Basic Approach (BA-CVA).

    K_CVA = 2.33 * sqrt(sum(S_c^2 * CVA_c^2) + rho^2 * (sum(S_c * CVA_c))^2)

    Parameters:
    -----------
    counterparties : list of dict
        Each should have: ead, rating, maturity

    Returns:
    --------
    dict
        BA-CVA calculation results
    """
    results = []
    sum_squared = 0
    sum_weighted = 0

    for cp in counterparties:
        ead = cp.get("ead", 0)
        rating = cp.get("rating", "unrated")
        maturity = cp.get("maturity", 1.0)

        # Get risk weight
        rw = BA_CVA_RISK_WEIGHTS.get(rating, BA_CVA_RISK_WEIGHTS["unrated"])

        # Calculate discount factor
        df = calculate_supervisory_discount(maturity)

        # CVA = EAD * (1 - exp(-spread * M)) / (1 - recovery)
        # Simplified: CVA ≈ EAD * spread * M * DF
        # Using RW as proxy for spread
        cva_estimate = ead * rw * maturity * df

        # Weighted CVA
        s_c = rw
        cva_c = cva_estimate

        sum_squared += (s_c * cva_c) ** 2
        sum_weighted += s_c * cva_c

        results.append({
            "ead": ead,
            "rating": rating,
            "maturity": maturity,
            "risk_weight": rw,
            "discount_factor": df,
            "cva_estimate": cva_estimate,
            "weighted_cva": s_c * cva_c,
        })

    # K_CVA formula
    rho = BA_CVA_CORRELATION
    k_cva = 2.33 * math.sqrt(sum_squared + rho**2 * sum_weighted**2)

    # RWA = K * 12.5
    rwa = k_cva * 12.5

    return {
        "approach": "BA-CVA",
        "k_cva": k_cva,
        "rwa": rwa,
        "counterparties": results,
        "sum_squared": sum_squared,
        "sum_weighted": sum_weighted,
        "correlation": rho,
    }


# SA-CVA Risk weights by sector (MAR50.37)
SA_CVA_RISK_WEIGHTS = {
    "sovereign_IG": 0.005,
    "sovereign_HY": 0.020,
    "financial_IG": 0.005,
    "financial_HY": 0.012,
    "basic_materials": 0.010,
    "consumer": 0.010,
    "tech_telecom": 0.010,
    "health_utilities": 0.005,
    "other": 0.010,
}

SA_CVA_CORRELATIONS = {
    "intra_bucket": 0.50,
    "inter_bucket": 0.25,
}


def calculate_sa_cva(
    counterparties: list[dict],
    hedges: list[dict] = None
) -> dict:
    """
    Calculate CVA capital using Standardised Approach (SA-CVA).

    More risk-sensitive than BA-CVA, allows for hedging recognition.

    Parameters:
    -----------
    counterparties : list of dict
        Each should have: ead, sector, rating, maturity
    hedges : list of dict
        CVA hedges (CDS, index hedges)

    Returns:
    --------
    dict
        SA-CVA calculation results
    """
    hedges = hedges or []

    # Group by sector (bucket)
    buckets = {}
    for cp in counterparties:
        sector = cp.get("sector", "other")
        if sector not in buckets:
            buckets[sector] = []

        ead = cp.get("ead", 0)
        maturity = cp.get("maturity", 1.0)
        rating = cp.get("rating", "BBB")

        # Determine if IG or HY
        ig_ratings = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"]
        is_ig = rating in ig_ratings

        # Get risk weight
        if sector.startswith("sovereign"):
            rw_key = "sovereign_IG" if is_ig else "sovereign_HY"
        elif sector.startswith("financial"):
            rw_key = "financial_IG" if is_ig else "financial_HY"
        else:
            rw_key = sector

        rw = SA_CVA_RISK_WEIGHTS.get(rw_key, 0.010)

        # Calculate CVA sensitivity
        df = calculate_supervisory_discount(maturity)
        cva_sensitivity = ead * maturity * df * rw

        buckets[sector].append({
            "ead": ead,
            "maturity": maturity,
            "rating": rating,
            "risk_weight": rw,
            "cva_sensitivity": cva_sensitivity,
        })

    # Calculate bucket-level capital
    bucket_capitals = {}
    total_bucket_k = 0

    rho_intra = SA_CVA_CORRELATIONS["intra_bucket"]

    for sector, exposures in buckets.items():
        sensitivities = [e["cva_sensitivity"] for e in exposures]

        # Within-bucket aggregation with correlation
        sum_sens = sum(sensitivities)
        sum_sens_sq = sum(s**2 for s in sensitivities)

        k_bucket = math.sqrt(
            sum_sens_sq +
            rho_intra**2 * (sum_sens**2 - sum_sens_sq)
        )

        bucket_capitals[sector] = k_bucket
        total_bucket_k += k_bucket

    # Cross-bucket aggregation
    rho_inter = SA_CVA_CORRELATIONS["inter_bucket"]
    bucket_k_values = list(bucket_capitals.values())

    sum_k = sum(bucket_k_values)
    sum_k_sq = sum(k**2 for k in bucket_k_values)

    k_cva = math.sqrt(
        sum_k_sq +
        rho_inter**2 * (sum_k**2 - sum_k_sq)
    )

    # Apply hedge benefit (simplified)
    hedge_benefit = sum(h.get("notional", 0) * h.get("effectiveness", 0.5)
                       for h in hedges)
    k_cva_hedged = max(k_cva - hedge_benefit * 0.01, k_cva * 0.25)

    rwa = k_cva_hedged * 12.5

    return {
        "approach": "SA-CVA",
        "k_cva_gross": k_cva,
        "hedge_benefit": hedge_benefit * 0.01,
        "k_cva": k_cva_hedged,
        "rwa": rwa,
        "bucket_capitals": bucket_capitals,
        "buckets": buckets,
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("SA-CCR Example")
    print("=" * 70)

    trades = [
        {"notional": 10_000_000, "asset_class": "IR", "maturity": 5.0, "mtm": 100_000, "delta": 1.0},
        {"notional": 5_000_000, "asset_class": "FX", "maturity": 1.0, "mtm": 50_000, "delta": 1.0},
        {"notional": 2_000_000, "asset_class": "CR_BBB", "maturity": 3.0, "mtm": -20_000, "delta": -1.0},
    ]

    result = calculate_sa_ccr_ead(
        trades,
        collateral_held=50_000,
        is_margined=True,
        threshold=100_000,
        mta=10_000
    )

    print(f"\n  Portfolio MTM:        ${result['total_mtm']:,.0f}")
    print(f"  Net Collateral:       ${result['net_collateral']:,.0f}")
    print(f"  Replacement Cost:     ${result['replacement_cost']:,.0f}")
    print(f"  Add-on Aggregate:     ${result['addon_aggregate']:,.0f}")
    print(f"  PFE Multiplier:       {result['multiplier']:.3f}")
    print(f"  PFE:                  ${result['pfe']:,.0f}")
    print(f"  EAD (alpha={result['alpha']}):      ${result['ead']:,.0f}")

    print("\n" + "=" * 70)
    print("BA-CVA Example")
    print("=" * 70)

    counterparties = [
        {"ead": 5_000_000, "rating": "A", "maturity": 3.0},
        {"ead": 3_000_000, "rating": "BBB", "maturity": 5.0},
        {"ead": 1_000_000, "rating": "BB", "maturity": 2.0},
    ]

    cva_result = calculate_ba_cva(counterparties)

    print(f"\n  K_CVA:                ${cva_result['k_cva']:,.0f}")
    print(f"  CVA RWA:              ${cva_result['rwa']:,.0f}")

    print("\n  By counterparty:")
    for cp in cva_result['counterparties']:
        print(f"    {cp['rating']}: EAD=${cp['ead']:,.0f}, RW={cp['risk_weight']*100:.1f}%, CVA=${cp['cva_estimate']:,.0f}")
