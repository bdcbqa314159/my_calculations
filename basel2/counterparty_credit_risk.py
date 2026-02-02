"""
Basel II Counterparty Credit Risk (CCR)

Implements the Basel II CCR methodologies:
1. Current Exposure Method (CEM) - Para 186-194
2. Standardised Method (SM) - Para 195-214
3. Internal Model Method (IMM) - Para 215-284
4. Settlement Risk - Para 187-188

Key differences from Basel III:
- Basel II uses CEM with add-on factors; Basel III uses SA-CCR
- Different add-on percentages and calculation methodology
- No alpha factor in CEM (alpha=1.4 is SA-CCR)
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional


# =============================================================================
# Current Exposure Method (CEM) - Para 186-194
# =============================================================================

class DerivativeType(Enum):
    """Derivative instrument types for CEM add-on calculation."""
    INTEREST_RATE = "interest_rate"
    FX_GOLD = "fx_gold"
    EQUITY = "equity"
    PRECIOUS_METALS = "precious_metals"  # Except gold
    OTHER_COMMODITIES = "other_commodities"
    CREDIT_DERIVATIVE = "credit_derivative"


# CEM Add-on Factors (Para 187) - Percentage of notional
# Format: {derivative_type: {maturity_bucket: add_on_factor}}
CEM_ADDON_FACTORS = {
    DerivativeType.INTEREST_RATE: {
        "up_to_1y": 0.00,      # 0%
        "1y_to_5y": 0.005,     # 0.5%
        "over_5y": 0.015,      # 1.5%
    },
    DerivativeType.FX_GOLD: {
        "up_to_1y": 0.01,      # 1%
        "1y_to_5y": 0.05,      # 5%
        "over_5y": 0.075,      # 7.5%
    },
    DerivativeType.EQUITY: {
        "up_to_1y": 0.06,      # 6%
        "1y_to_5y": 0.08,      # 8%
        "over_5y": 0.10,       # 10%
    },
    DerivativeType.PRECIOUS_METALS: {
        "up_to_1y": 0.07,      # 7%
        "1y_to_5y": 0.07,      # 7%
        "over_5y": 0.08,       # 8%
    },
    DerivativeType.OTHER_COMMODITIES: {
        "up_to_1y": 0.10,      # 10%
        "1y_to_5y": 0.12,      # 12%
        "over_5y": 0.15,       # 15%
    },
    DerivativeType.CREDIT_DERIVATIVE: {
        # Protection buyer
        "up_to_1y_protection_buyer": 0.05,   # 5%
        "1y_to_5y_protection_buyer": 0.05,   # 5%
        "over_5y_protection_buyer": 0.05,    # 5%
        # Protection seller (qualifying reference)
        "up_to_1y_protection_seller_qual": 0.05,
        "1y_to_5y_protection_seller_qual": 0.05,
        "over_5y_protection_seller_qual": 0.05,
        # Protection seller (non-qualifying reference)
        "up_to_1y_protection_seller_non_qual": 0.10,
        "1y_to_5y_protection_seller_non_qual": 0.10,
        "over_5y_protection_seller_non_qual": 0.10,
    },
}


@dataclass
class DerivativeTrade:
    """A single derivative trade for CCR calculation."""
    trade_id: str
    derivative_type: DerivativeType
    notional: float
    mark_to_market: float  # Current MTM value (positive = asset)
    residual_maturity: float  # Years
    counterparty_id: str
    is_protection_seller: bool = False  # For credit derivatives
    is_qualifying_reference: bool = True  # For credit derivatives
    netting_set_id: str = None  # For netting


def get_maturity_bucket(residual_maturity: float) -> str:
    """Determine maturity bucket for add-on factor lookup."""
    if residual_maturity <= 1:
        return "up_to_1y"
    elif residual_maturity <= 5:
        return "1y_to_5y"
    else:
        return "over_5y"


def get_cem_addon_factor(
    derivative_type: DerivativeType,
    residual_maturity: float,
    is_protection_seller: bool = False,
    is_qualifying_reference: bool = True
) -> float:
    """
    Get CEM add-on factor for a derivative.

    Parameters:
    -----------
    derivative_type : DerivativeType
        Type of derivative
    residual_maturity : float
        Residual maturity in years
    is_protection_seller : bool
        For credit derivatives: whether bank is protection seller
    is_qualifying_reference : bool
        For credit derivatives: whether reference entity is qualifying

    Returns:
    --------
    float
        Add-on factor as decimal
    """
    bucket = get_maturity_bucket(residual_maturity)

    if derivative_type == DerivativeType.CREDIT_DERIVATIVE:
        if is_protection_seller:
            if is_qualifying_reference:
                key = f"{bucket}_protection_seller_qual"
            else:
                key = f"{bucket}_protection_seller_non_qual"
        else:
            key = f"{bucket}_protection_buyer"
        return CEM_ADDON_FACTORS[derivative_type].get(key, 0.10)
    else:
        return CEM_ADDON_FACTORS[derivative_type].get(bucket, 0.15)


def calculate_cem_ead_single(trade: DerivativeTrade) -> dict:
    """
    Calculate CEM EAD for a single derivative trade (no netting).

    EAD = max(0, MTM) + Add-on

    Parameters:
    -----------
    trade : DerivativeTrade
        Single derivative trade

    Returns:
    --------
    dict
        CEM calculation results
    """
    # Current exposure (replacement cost)
    current_exposure = max(0, trade.mark_to_market)

    # Add-on for potential future exposure
    addon_factor = get_cem_addon_factor(
        trade.derivative_type,
        trade.residual_maturity,
        trade.is_protection_seller,
        trade.is_qualifying_reference
    )
    addon = trade.notional * addon_factor

    # Total EAD
    ead = current_exposure + addon

    return {
        "trade_id": trade.trade_id,
        "derivative_type": trade.derivative_type.value,
        "notional": trade.notional,
        "mark_to_market": trade.mark_to_market,
        "residual_maturity": trade.residual_maturity,
        "current_exposure": current_exposure,
        "addon_factor": addon_factor,
        "addon": addon,
        "ead": ead,
    }


def calculate_cem_ead_with_netting(
    trades: list[DerivativeTrade],
    netting_set_id: str = None
) -> dict:
    """
    Calculate CEM EAD for a netting set with bilateral netting agreement.

    Net EAD = Net Current Exposure + A_net
    A_net = 0.4 × A_gross + 0.6 × NGR × A_gross

    Where:
    - Net Current Exposure = max(0, sum of MTM)
    - A_gross = sum of individual add-ons
    - NGR = Net-to-Gross Ratio = Net CE / Gross CE

    Parameters:
    -----------
    trades : list of DerivativeTrade
        Trades in the netting set
    netting_set_id : str
        Netting set identifier

    Returns:
    --------
    dict
        CEM calculation with netting benefit
    """
    if not trades:
        return {"ead": 0, "trades": []}

    # Calculate individual trade metrics
    trade_results = []
    total_mtm = 0
    gross_positive_mtm = 0
    gross_addon = 0

    for trade in trades:
        result = calculate_cem_ead_single(trade)
        trade_results.append(result)

        total_mtm += trade.mark_to_market
        if trade.mark_to_market > 0:
            gross_positive_mtm += trade.mark_to_market
        gross_addon += result["addon"]

    # Net current exposure
    net_current_exposure = max(0, total_mtm)

    # Gross current exposure
    gross_current_exposure = gross_positive_mtm

    # Net-to-Gross Ratio (NGR)
    if gross_current_exposure > 0:
        ngr = net_current_exposure / gross_current_exposure
    else:
        ngr = 1.0  # No positive MTM trades

    # Adjusted add-on with netting benefit
    # A_net = 0.4 × A_gross + 0.6 × NGR × A_gross
    net_addon = 0.4 * gross_addon + 0.6 * ngr * gross_addon

    # Total EAD with netting
    net_ead = net_current_exposure + net_addon

    # EAD without netting (sum of individual EADs)
    gross_ead = sum(r["ead"] for r in trade_results)

    # Netting benefit
    netting_benefit = gross_ead - net_ead

    return {
        "approach": "CEM with Netting",
        "netting_set_id": netting_set_id,
        "trade_count": len(trades),
        "total_mtm": total_mtm,
        "net_current_exposure": net_current_exposure,
        "gross_current_exposure": gross_current_exposure,
        "ngr": ngr,
        "gross_addon": gross_addon,
        "net_addon": net_addon,
        "gross_ead": gross_ead,
        "net_ead": net_ead,
        "netting_benefit": netting_benefit,
        "netting_benefit_pct": (netting_benefit / gross_ead * 100) if gross_ead > 0 else 0,
        "trades": trade_results,
    }


def calculate_cem_ead_counterparty(
    trades: list[DerivativeTrade],
    counterparty_id: str,
    has_netting_agreement: bool = True
) -> dict:
    """
    Calculate CEM EAD for all trades with a counterparty.

    Parameters:
    -----------
    trades : list of DerivativeTrade
        All trades with counterparty
    counterparty_id : str
        Counterparty identifier
    has_netting_agreement : bool
        Whether legally enforceable netting agreement exists

    Returns:
    --------
    dict
        Counterparty-level EAD
    """
    # Filter trades for this counterparty
    cp_trades = [t for t in trades if t.counterparty_id == counterparty_id]

    if not cp_trades:
        return {"counterparty_id": counterparty_id, "ead": 0}

    if has_netting_agreement:
        # Group by netting set
        netting_sets = {}
        for trade in cp_trades:
            ns_id = trade.netting_set_id or "default"
            if ns_id not in netting_sets:
                netting_sets[ns_id] = []
            netting_sets[ns_id].append(trade)

        # Calculate EAD per netting set
        total_ead = 0
        netting_set_results = []

        for ns_id, ns_trades in netting_sets.items():
            ns_result = calculate_cem_ead_with_netting(ns_trades, ns_id)
            netting_set_results.append(ns_result)
            total_ead += ns_result["net_ead"]

        return {
            "approach": "CEM",
            "counterparty_id": counterparty_id,
            "has_netting_agreement": has_netting_agreement,
            "netting_sets": netting_set_results,
            "total_ead": total_ead,
        }
    else:
        # No netting - sum individual EADs
        total_ead = 0
        trade_results = []

        for trade in cp_trades:
            result = calculate_cem_ead_single(trade)
            trade_results.append(result)
            total_ead += result["ead"]

        return {
            "approach": "CEM",
            "counterparty_id": counterparty_id,
            "has_netting_agreement": has_netting_agreement,
            "trades": trade_results,
            "total_ead": total_ead,
        }


def calculate_cem_rwa(
    trades: list[DerivativeTrade],
    counterparty_id: str,
    counterparty_rw: float,
    has_netting_agreement: bool = True
) -> dict:
    """
    Calculate CCR RWA using CEM.

    Parameters:
    -----------
    trades : list of DerivativeTrade
        Trades with counterparty
    counterparty_id : str
        Counterparty identifier
    counterparty_rw : float
        Counterparty risk weight (%)
    has_netting_agreement : bool
        Whether netting agreement exists

    Returns:
    --------
    dict
        CCR RWA calculation
    """
    ead_result = calculate_cem_ead_counterparty(
        trades, counterparty_id, has_netting_agreement
    )

    ead = ead_result["total_ead"]
    rwa = ead * counterparty_rw / 100
    capital = rwa * 0.08

    return {
        **ead_result,
        "counterparty_rw": counterparty_rw,
        "rwa": rwa,
        "capital_requirement": capital,
    }


# =============================================================================
# Standardised Method (SM) - Para 195-214
# =============================================================================

# SM Risk Position factors by asset class
SM_RISK_POSITION_FACTORS = {
    DerivativeType.INTEREST_RATE: {
        "up_to_1y": 0.002,    # 0.2%
        "1y_to_5y": 0.004,    # 0.4%
        "over_5y": 0.006,     # 0.6%
    },
    DerivativeType.FX_GOLD: {
        "any": 0.025,         # 2.5%
    },
    DerivativeType.EQUITY: {
        "any": 0.07,          # 7%
    },
    DerivativeType.PRECIOUS_METALS: {
        "any": 0.085,         # 8.5%
    },
    DerivativeType.OTHER_COMMODITIES: {
        "any": 0.10,          # 10%
    },
    DerivativeType.CREDIT_DERIVATIVE: {
        "any": 0.05,          # 5% (simplified)
    },
}

# SM Correlation factors (CCF) for hedging sets
SM_CORRELATION_FACTORS = {
    DerivativeType.INTEREST_RATE: 0.0,      # Fully offsetting within currency
    DerivativeType.FX_GOLD: 0.0,            # Fully offsetting
    DerivativeType.EQUITY: 0.5,             # Partial offsetting
    DerivativeType.PRECIOUS_METALS: 0.5,
    DerivativeType.OTHER_COMMODITIES: 0.5,
    DerivativeType.CREDIT_DERIVATIVE: 0.5,
}


def calculate_sm_ead(
    trades: list[DerivativeTrade],
    counterparty_id: str
) -> dict:
    """
    Calculate EAD using Standardised Method (SM).

    The SM uses risk positions and hedging set aggregation.

    EAD = β × max(CMV, Σ|RPT_j| - Σ|RPC_j| + Σ CCF_k × |RPT_k|)

    Where:
    - β = 1.4 (supervisory scaling factor)
    - CMV = Current Market Value (net)
    - RPT = Risk Position from Transactions
    - RPC = Risk Position from Collateral
    - CCF = Correlation factors for hedging sets

    Parameters:
    -----------
    trades : list of DerivativeTrade
        Trades with counterparty
    counterparty_id : str
        Counterparty identifier

    Returns:
    --------
    dict
        SM EAD calculation
    """
    beta = 1.4  # Supervisory scaling factor

    cp_trades = [t for t in trades if t.counterparty_id == counterparty_id]

    if not cp_trades:
        return {"counterparty_id": counterparty_id, "ead": 0}

    # Current market value (net MTM)
    cmv = sum(t.mark_to_market for t in cp_trades)

    # Calculate risk positions by hedging set (derivative type)
    hedging_sets = {}

    for trade in cp_trades:
        dtype = trade.derivative_type
        if dtype not in hedging_sets:
            hedging_sets[dtype] = {
                "long": 0,
                "short": 0,
                "trades": [],
            }

        # Risk position = notional × risk position factor
        bucket = get_maturity_bucket(trade.residual_maturity)
        factors = SM_RISK_POSITION_FACTORS.get(dtype, {"any": 0.10})
        rp_factor = factors.get(bucket, factors.get("any", 0.10))

        risk_position = trade.notional * rp_factor

        if trade.mark_to_market >= 0:
            hedging_sets[dtype]["long"] += risk_position
        else:
            hedging_sets[dtype]["short"] += risk_position

        hedging_sets[dtype]["trades"].append({
            "trade_id": trade.trade_id,
            "notional": trade.notional,
            "rp_factor": rp_factor,
            "risk_position": risk_position,
        })

    # Aggregate risk positions with correlation
    total_risk_position = 0

    for dtype, hs_data in hedging_sets.items():
        ccf = SM_CORRELATION_FACTORS.get(dtype, 0.5)

        # Net risk position within hedging set
        net_rp = abs(hs_data["long"] - hs_data["short"])

        # Gross risk position
        gross_rp = hs_data["long"] + hs_data["short"]

        # Hedging set contribution = net + CCF × (gross - net)
        hs_contribution = net_rp + ccf * (gross_rp - net_rp)
        total_risk_position += hs_contribution

        hs_data["net_risk_position"] = net_rp
        hs_data["gross_risk_position"] = gross_rp
        hs_data["ccf"] = ccf
        hs_data["contribution"] = hs_contribution

    # EAD = β × max(CMV, Total Risk Position)
    ead = beta * max(cmv, total_risk_position)

    return {
        "approach": "SM",
        "counterparty_id": counterparty_id,
        "beta": beta,
        "cmv": cmv,
        "total_risk_position": total_risk_position,
        "hedging_sets": {k.value: v for k, v in hedging_sets.items()},
        "ead": ead,
    }


# =============================================================================
# Internal Model Method (IMM) - Para 215-284
# =============================================================================

@dataclass
class IMMParameters:
    """Parameters for IMM calculation."""
    effective_epe: float  # Effective Expected Positive Exposure
    alpha: float = 1.4    # Supervisory alpha (can be bank-specific with approval)
    maturity: float = 1.0  # M parameter (typically 1 year for IMM)


def calculate_imm_ead(
    imm_params: IMMParameters,
    use_bank_alpha: bool = False,
    bank_alpha: float = None
) -> dict:
    """
    Calculate EAD using Internal Model Method (IMM).

    EAD = α × Effective EPE

    Where:
    - α = 1.4 (or bank-specific if approved)
    - Effective EPE = time-weighted average of Effective EE over 1 year

    Parameters:
    -----------
    imm_params : IMMParameters
        IMM model parameters
    use_bank_alpha : bool
        Whether to use bank-specific alpha
    bank_alpha : float
        Bank-specific alpha (if approved, typically 1.2-1.6)

    Returns:
    --------
    dict
        IMM EAD calculation
    """
    if use_bank_alpha and bank_alpha is not None:
        alpha = bank_alpha
    else:
        alpha = imm_params.alpha

    ead = alpha * imm_params.effective_epe

    return {
        "approach": "IMM",
        "effective_epe": imm_params.effective_epe,
        "alpha": alpha,
        "alpha_source": "bank_specific" if use_bank_alpha else "supervisory",
        "maturity": imm_params.maturity,
        "ead": ead,
    }


# =============================================================================
# Settlement Risk - Para 187-188
# =============================================================================

def calculate_settlement_risk_charge(
    transaction_value: float,
    days_overdue: int,
    is_dvp: bool = True
) -> dict:
    """
    Calculate settlement risk capital charge.

    For DVP (Delivery vs Payment) transactions that remain unsettled
    after the settlement date.

    Parameters:
    -----------
    transaction_value : float
        Value of the unsettled transaction
    days_overdue : int
        Business days past settlement date
    is_dvp : bool
        Whether transaction is DVP (vs free delivery)

    Returns:
    --------
    dict
        Settlement risk charge
    """
    if is_dvp:
        # DVP settlement risk factors (Para 188)
        if days_overdue <= 4:
            risk_factor = 0.00  # No charge
        elif days_overdue <= 15:
            risk_factor = 0.08  # 8%
        elif days_overdue <= 30:
            risk_factor = 0.50  # 50%
        elif days_overdue <= 45:
            risk_factor = 0.75  # 75%
        else:
            risk_factor = 1.00  # 100%

        exposure = transaction_value * risk_factor
        charge = exposure * 0.08  # 8% capital charge

    else:
        # Free delivery (non-DVP) - full exposure
        # Treat as loan from settlement date
        exposure = transaction_value
        risk_factor = 1.00
        charge = exposure * 0.08  # Apply counterparty RW

    return {
        "transaction_value": transaction_value,
        "days_overdue": days_overdue,
        "is_dvp": is_dvp,
        "risk_factor": risk_factor,
        "exposure": exposure,
        "capital_charge": charge,
    }


# =============================================================================
# Wrong-Way Risk (WWR) - Para 78-83
# =============================================================================

def assess_wrong_way_risk(
    counterparty_sector: str,
    derivative_type: DerivativeType,
    underlying_sector: str = None,
    correlation_estimate: float = 0.0
) -> dict:
    """
    Assess wrong-way risk for a derivative position.

    Wrong-way risk occurs when exposure increases as counterparty
    credit quality deteriorates.

    Specific WWR: Direct relationship (e.g., put on own stock)
    General WWR: Correlation with economic factors

    Parameters:
    -----------
    counterparty_sector : str
        Counterparty's industry sector
    derivative_type : DerivativeType
        Type of derivative
    underlying_sector : str
        Sector of underlying (for specific WWR)
    correlation_estimate : float
        Estimated correlation for general WWR

    Returns:
    --------
    dict
        WWR assessment
    """
    # Specific wrong-way risk indicators
    specific_wwr = False
    specific_wwr_reason = None

    if underlying_sector and underlying_sector == counterparty_sector:
        specific_wwr = True
        specific_wwr_reason = "Underlying in same sector as counterparty"

    # Credit derivatives on counterparty or related entity
    if derivative_type == DerivativeType.CREDIT_DERIVATIVE:
        specific_wwr = True
        specific_wwr_reason = "Credit derivative may reference counterparty"

    # General wrong-way risk assessment
    general_wwr_level = "low"
    if abs(correlation_estimate) > 0.5:
        general_wwr_level = "high"
    elif abs(correlation_estimate) > 0.25:
        general_wwr_level = "medium"

    # Recommended add-on multiplier
    if specific_wwr:
        addon_multiplier = 2.0  # Double the add-on
    elif general_wwr_level == "high":
        addon_multiplier = 1.5
    elif general_wwr_level == "medium":
        addon_multiplier = 1.25
    else:
        addon_multiplier = 1.0

    return {
        "specific_wrong_way_risk": specific_wwr,
        "specific_wwr_reason": specific_wwr_reason,
        "general_wwr_level": general_wwr_level,
        "correlation_estimate": correlation_estimate,
        "recommended_addon_multiplier": addon_multiplier,
    }


# =============================================================================
# Comparison Function
# =============================================================================

def compare_ccr_approaches(
    trades: list[DerivativeTrade],
    counterparty_id: str,
    counterparty_rw: float,
    has_netting: bool = True,
    imm_params: IMMParameters = None
) -> dict:
    """
    Compare CEM, SM, and IMM approaches for CCR.

    Parameters:
    -----------
    trades : list of DerivativeTrade
        Trades with counterparty
    counterparty_id : str
        Counterparty identifier
    counterparty_rw : float
        Counterparty risk weight (%)
    has_netting : bool
        Whether netting agreement exists
    imm_params : IMMParameters
        IMM parameters if available

    Returns:
    --------
    dict
        Comparison results
    """
    # CEM
    cem_result = calculate_cem_rwa(trades, counterparty_id, counterparty_rw, has_netting)

    # SM
    sm_ead = calculate_sm_ead(trades, counterparty_id)
    sm_rwa = sm_ead["ead"] * counterparty_rw / 100

    # IMM (if parameters provided)
    if imm_params:
        imm_ead = calculate_imm_ead(imm_params)
        imm_rwa = imm_ead["ead"] * counterparty_rw / 100
    else:
        imm_ead = None
        imm_rwa = None

    results = [
        ("CEM", cem_result["total_ead"], cem_result["rwa"]),
        ("SM", sm_ead["ead"], sm_rwa),
    ]
    if imm_rwa is not None:
        results.append(("IMM", imm_ead["ead"], imm_rwa))

    results_sorted = sorted(results, key=lambda x: x[2], reverse=True)

    return {
        "counterparty_id": counterparty_id,
        "counterparty_rw": counterparty_rw,
        "cem": {
            "ead": cem_result["total_ead"],
            "rwa": cem_result["rwa"],
            "details": cem_result,
        },
        "sm": {
            "ead": sm_ead["ead"],
            "rwa": sm_rwa,
            "details": sm_ead,
        },
        "imm": {
            "ead": imm_ead["ead"] if imm_ead else None,
            "rwa": imm_rwa,
            "details": imm_ead,
        } if imm_params else None,
        "most_conservative": results_sorted[0][0],
        "least_conservative": results_sorted[-1][0],
        "ranking": [r[0] for r in results_sorted],
    }


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Basel II Counterparty Credit Risk (CCR)")
    print("=" * 70)

    # Sample trades
    trades = [
        DerivativeTrade("T1", DerivativeType.INTEREST_RATE, 10_000_000, 150_000, 3.0, "CP001"),
        DerivativeTrade("T2", DerivativeType.INTEREST_RATE, 8_000_000, -50_000, 2.0, "CP001"),
        DerivativeTrade("T3", DerivativeType.FX_GOLD, 5_000_000, 200_000, 1.5, "CP001"),
        DerivativeTrade("T4", DerivativeType.EQUITY, 2_000_000, 100_000, 2.5, "CP001"),
        DerivativeTrade("T5", DerivativeType.FX_GOLD, 3_000_000, -80_000, 0.5, "CP001"),
    ]

    # CEM calculation
    print("\n  Current Exposure Method (CEM):")
    cem = calculate_cem_rwa(trades, "CP001", 50, has_netting_agreement=True)

    print(f"\n  Trade-level results:")
    print(f"  {'Trade':<8} {'Type':<15} {'Notional':>12} {'MTM':>10} {'Add-on':>10} {'EAD':>12}")
    print(f"  {'-'*8} {'-'*15} {'-'*12} {'-'*10} {'-'*10} {'-'*12}")

    for ns in cem.get("netting_sets", []):
        for t in ns.get("trades", []):
            print(f"  {t['trade_id']:<8} {t['derivative_type']:<15} "
                  f"${t['notional']:>10,.0f} ${t['mark_to_market']:>8,.0f} "
                  f"${t['addon']:>8,.0f} ${t['ead']:>10,.0f}")

    print(f"\n  Netting set summary:")
    for ns in cem.get("netting_sets", []):
        print(f"  Net Current Exposure: ${ns['net_current_exposure']:,.0f}")
        print(f"  NGR: {ns['ngr']:.2%}")
        print(f"  Gross Add-on: ${ns['gross_addon']:,.0f}")
        print(f"  Net Add-on: ${ns['net_addon']:,.0f}")
        print(f"  Netting Benefit: ${ns['netting_benefit']:,.0f} ({ns['netting_benefit_pct']:.1f}%)")

    print(f"\n  Total EAD: ${cem['total_ead']:,.0f}")
    print(f"  RWA (50% RW): ${cem['rwa']:,.0f}")
    print(f"  Capital: ${cem['capital_requirement']:,.0f}")

    # SM calculation
    print("\n" + "=" * 70)
    print("Standardised Method (SM)")
    print("=" * 70)

    sm = calculate_sm_ead(trades, "CP001")
    print(f"\n  Beta: {sm['beta']}")
    print(f"  CMV: ${sm['cmv']:,.0f}")
    print(f"  Total Risk Position: ${sm['total_risk_position']:,.0f}")
    print(f"  EAD: ${sm['ead']:,.0f}")

    # Comparison
    print("\n" + "=" * 70)
    print("Approach Comparison")
    print("=" * 70)

    comp = compare_ccr_approaches(trades, "CP001", 50, has_netting=True)

    print(f"\n  {'Approach':<10} {'EAD':>15} {'RWA':>15}")
    print(f"  {'-'*10} {'-'*15} {'-'*15}")
    print(f"  {'CEM':<10} ${comp['cem']['ead']:>13,.0f} ${comp['cem']['rwa']:>13,.0f}")
    print(f"  {'SM':<10} ${comp['sm']['ead']:>13,.0f} ${comp['sm']['rwa']:>13,.0f}")
    print(f"\n  Most conservative: {comp['most_conservative']}")
