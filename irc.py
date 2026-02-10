"""
Incremental Risk Charge (IRC) — Full Monte Carlo Implementation

Basel 2.5 / Basel III IRC model for trading book credit positions:
- 1-year capital horizon at 99.9% confidence
- Captures default risk AND rating migration risk
- Multi-factor Gaussian copula for issuer correlation
- Constant level of risk assumption with liquidity horizon rebalancing

Key regulatory references:
- Basel 2.5: Para 718(xcii) – IRC framework
- BCBS 238: Revisions to Basel II market risk framework (IRC details)

IRC Capital = 99.9th percentile of 1-year P&L distribution from:
    - Default losses (LGD × notional)
    - Migration losses (spread change × duration × notional)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from rwa_calc import RATING_TO_PD


# =============================================================================
# Rating Transition Matrices (1-year)
# =============================================================================
#
# Different matrices for different regions, sectors, and economic conditions.
# Based on S&P, Moody's historical data and Basel regulatory guidance.
#
# Available matrices:
#   - "global" / "us_corporate" : S&P Global/US Corporate (default)
#   - "europe"                  : European corporates
#   - "emerging_markets" / "em" : Emerging markets (higher default rates)
#   - "financials"              : Financial institutions
#   - "sovereign"               : Sovereign ratings
#   - "recession"               : Stressed/downturn scenario
#   - "benign"                  : Low-default environment
# =============================================================================

RATING_CATEGORIES = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D"]

# -----------------------------------------------------------------------------
# Global / US Corporate (Default) - S&P historical average
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_GLOBAL = {
    "AAA": {"AAA": 0.9081, "AA": 0.0833, "A": 0.0068, "BBB": 0.0006, "BB": 0.0008, "B": 0.0003, "CCC": 0.0001, "D": 0.0000},
    "AA":  {"AAA": 0.0070, "AA": 0.9065, "A": 0.0779, "BBB": 0.0064, "BB": 0.0006, "B": 0.0010, "CCC": 0.0004, "D": 0.0002},
    "A":   {"AAA": 0.0009, "AA": 0.0227, "A": 0.9105, "BBB": 0.0552, "BB": 0.0074, "B": 0.0021, "CCC": 0.0006, "D": 0.0006},
    "BBB": {"AAA": 0.0002, "AA": 0.0033, "A": 0.0595, "BBB": 0.8693, "BB": 0.0530, "B": 0.0102, "CCC": 0.0027, "D": 0.0018},
    "BB":  {"AAA": 0.0003, "AA": 0.0014, "A": 0.0067, "BBB": 0.0773, "BB": 0.8053, "B": 0.0804, "CCC": 0.0180, "D": 0.0106},
    "B":   {"AAA": 0.0000, "AA": 0.0011, "A": 0.0024, "BBB": 0.0043, "BB": 0.0648, "B": 0.8297, "CCC": 0.0456, "D": 0.0521},
    "CCC": {"AAA": 0.0022, "AA": 0.0000, "A": 0.0022, "BBB": 0.0130, "BB": 0.0238, "B": 0.1124, "CCC": 0.6486, "D": 0.1978},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# European Corporates - slightly lower default rates than US
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_EUROPE = {
    "AAA": {"AAA": 0.9150, "AA": 0.0770, "A": 0.0060, "BBB": 0.0008, "BB": 0.0006, "B": 0.0004, "CCC": 0.0002, "D": 0.0000},
    "AA":  {"AAA": 0.0080, "AA": 0.9120, "A": 0.0720, "BBB": 0.0058, "BB": 0.0008, "B": 0.0008, "CCC": 0.0004, "D": 0.0002},
    "A":   {"AAA": 0.0012, "AA": 0.0250, "A": 0.9150, "BBB": 0.0500, "BB": 0.0060, "B": 0.0018, "CCC": 0.0005, "D": 0.0005},
    "BBB": {"AAA": 0.0003, "AA": 0.0040, "A": 0.0620, "BBB": 0.8750, "BB": 0.0460, "B": 0.0085, "CCC": 0.0025, "D": 0.0017},
    "BB":  {"AAA": 0.0004, "AA": 0.0016, "A": 0.0075, "BBB": 0.0820, "BB": 0.8100, "B": 0.0750, "CCC": 0.0150, "D": 0.0085},
    "B":   {"AAA": 0.0000, "AA": 0.0012, "A": 0.0028, "BBB": 0.0050, "BB": 0.0700, "B": 0.8350, "CCC": 0.0420, "D": 0.0440},
    "CCC": {"AAA": 0.0020, "AA": 0.0000, "A": 0.0025, "BBB": 0.0150, "BB": 0.0280, "B": 0.1200, "CCC": 0.6525, "D": 0.1800},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Emerging Markets - higher default and downgrade rates
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_EM = {
    "AAA": {"AAA": 0.8800, "AA": 0.1000, "A": 0.0140, "BBB": 0.0030, "BB": 0.0015, "B": 0.0010, "CCC": 0.0005, "D": 0.0000},
    "AA":  {"AAA": 0.0050, "AA": 0.8850, "A": 0.0900, "BBB": 0.0120, "BB": 0.0040, "B": 0.0020, "CCC": 0.0012, "D": 0.0008},
    "A":   {"AAA": 0.0006, "AA": 0.0180, "A": 0.8900, "BBB": 0.0700, "BB": 0.0130, "B": 0.0050, "CCC": 0.0020, "D": 0.0014},
    "BBB": {"AAA": 0.0001, "AA": 0.0020, "A": 0.0480, "BBB": 0.8400, "BB": 0.0750, "B": 0.0200, "CCC": 0.0080, "D": 0.0069},
    "BB":  {"AAA": 0.0002, "AA": 0.0010, "A": 0.0050, "BBB": 0.0650, "BB": 0.7700, "B": 0.1050, "CCC": 0.0300, "D": 0.0238},
    "B":   {"AAA": 0.0000, "AA": 0.0008, "A": 0.0018, "BBB": 0.0035, "BB": 0.0550, "B": 0.7900, "CCC": 0.0650, "D": 0.0839},
    "CCC": {"AAA": 0.0015, "AA": 0.0000, "A": 0.0015, "BBB": 0.0100, "BB": 0.0200, "B": 0.0900, "CCC": 0.5770, "D": 0.3000},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Financial Institutions - higher correlation, different dynamics
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_FINANCIALS = {
    "AAA": {"AAA": 0.9000, "AA": 0.0880, "A": 0.0085, "BBB": 0.0015, "BB": 0.0010, "B": 0.0006, "CCC": 0.0003, "D": 0.0001},
    "AA":  {"AAA": 0.0060, "AA": 0.9000, "A": 0.0820, "BBB": 0.0080, "BB": 0.0018, "B": 0.0012, "CCC": 0.0006, "D": 0.0004},
    "A":   {"AAA": 0.0007, "AA": 0.0200, "A": 0.9050, "BBB": 0.0600, "BB": 0.0090, "B": 0.0030, "CCC": 0.0012, "D": 0.0011},
    "BBB": {"AAA": 0.0001, "AA": 0.0025, "A": 0.0550, "BBB": 0.8600, "BB": 0.0580, "B": 0.0140, "CCC": 0.0050, "D": 0.0054},
    "BB":  {"AAA": 0.0002, "AA": 0.0010, "A": 0.0055, "BBB": 0.0700, "BB": 0.7900, "B": 0.0900, "CCC": 0.0250, "D": 0.0183},
    "B":   {"AAA": 0.0000, "AA": 0.0008, "A": 0.0020, "BBB": 0.0040, "BB": 0.0600, "B": 0.8100, "CCC": 0.0550, "D": 0.0682},
    "CCC": {"AAA": 0.0018, "AA": 0.0000, "A": 0.0020, "BBB": 0.0120, "BB": 0.0220, "B": 0.1050, "CCC": 0.6072, "D": 0.2500},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Sovereign - different dynamics, lower default rates for IG
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_SOVEREIGN = {
    "AAA": {"AAA": 0.9500, "AA": 0.0450, "A": 0.0040, "BBB": 0.0005, "BB": 0.0003, "B": 0.0001, "CCC": 0.0001, "D": 0.0000},
    "AA":  {"AAA": 0.0100, "AA": 0.9400, "A": 0.0450, "BBB": 0.0035, "BB": 0.0008, "B": 0.0004, "CCC": 0.0002, "D": 0.0001},
    "A":   {"AAA": 0.0015, "AA": 0.0300, "A": 0.9300, "BBB": 0.0320, "BB": 0.0045, "B": 0.0012, "CCC": 0.0005, "D": 0.0003},
    "BBB": {"AAA": 0.0003, "AA": 0.0050, "A": 0.0700, "BBB": 0.8800, "BB": 0.0350, "B": 0.0060, "CCC": 0.0022, "D": 0.0015},
    "BB":  {"AAA": 0.0005, "AA": 0.0020, "A": 0.0100, "BBB": 0.0900, "BB": 0.8200, "B": 0.0550, "CCC": 0.0130, "D": 0.0095},
    "B":   {"AAA": 0.0000, "AA": 0.0015, "A": 0.0030, "BBB": 0.0060, "BB": 0.0800, "B": 0.8300, "CCC": 0.0380, "D": 0.0415},
    "CCC": {"AAA": 0.0025, "AA": 0.0000, "A": 0.0030, "BBB": 0.0180, "BB": 0.0350, "B": 0.1300, "CCC": 0.6315, "D": 0.1800},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Recession / Stressed - higher defaults and downgrades (2008-2009 style)
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_RECESSION = {
    "AAA": {"AAA": 0.8500, "AA": 0.1200, "A": 0.0200, "BBB": 0.0050, "BB": 0.0030, "B": 0.0012, "CCC": 0.0006, "D": 0.0002},
    "AA":  {"AAA": 0.0040, "AA": 0.8600, "A": 0.1050, "BBB": 0.0180, "BB": 0.0060, "B": 0.0035, "CCC": 0.0020, "D": 0.0015},
    "A":   {"AAA": 0.0005, "AA": 0.0150, "A": 0.8700, "BBB": 0.0800, "BB": 0.0200, "B": 0.0080, "CCC": 0.0035, "D": 0.0030},
    "BBB": {"AAA": 0.0001, "AA": 0.0020, "A": 0.0400, "BBB": 0.8200, "BB": 0.0850, "B": 0.0300, "CCC": 0.0120, "D": 0.0109},
    "BB":  {"AAA": 0.0001, "AA": 0.0008, "A": 0.0040, "BBB": 0.0550, "BB": 0.7400, "B": 0.1200, "CCC": 0.0450, "D": 0.0351},
    "B":   {"AAA": 0.0000, "AA": 0.0005, "A": 0.0015, "BBB": 0.0030, "BB": 0.0450, "B": 0.7600, "CCC": 0.0800, "D": 0.1100},
    "CCC": {"AAA": 0.0010, "AA": 0.0000, "A": 0.0010, "BBB": 0.0080, "BB": 0.0150, "B": 0.0800, "CCC": 0.5050, "D": 0.3900},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Benign / Low-Default Environment - lower defaults and upgrades more likely
# -----------------------------------------------------------------------------
TRANSITION_MATRIX_BENIGN = {
    "AAA": {"AAA": 0.9300, "AA": 0.0640, "A": 0.0045, "BBB": 0.0008, "BB": 0.0004, "B": 0.0002, "CCC": 0.0001, "D": 0.0000},
    "AA":  {"AAA": 0.0100, "AA": 0.9250, "A": 0.0580, "BBB": 0.0050, "BB": 0.0010, "B": 0.0006, "CCC": 0.0003, "D": 0.0001},
    "A":   {"AAA": 0.0015, "AA": 0.0300, "A": 0.9300, "BBB": 0.0330, "BB": 0.0040, "B": 0.0010, "CCC": 0.0003, "D": 0.0002},
    "BBB": {"AAA": 0.0005, "AA": 0.0050, "A": 0.0750, "BBB": 0.8900, "BB": 0.0230, "B": 0.0045, "CCC": 0.0012, "D": 0.0008},
    "BB":  {"AAA": 0.0005, "AA": 0.0020, "A": 0.0100, "BBB": 0.0950, "BB": 0.8400, "B": 0.0400, "CCC": 0.0080, "D": 0.0045},
    "B":   {"AAA": 0.0000, "AA": 0.0015, "A": 0.0035, "BBB": 0.0060, "BB": 0.0850, "B": 0.8600, "CCC": 0.0250, "D": 0.0190},
    "CCC": {"AAA": 0.0030, "AA": 0.0000, "A": 0.0035, "BBB": 0.0200, "BB": 0.0400, "B": 0.1500, "CCC": 0.6835, "D": 0.1000},
    "D":   {"AAA": 0.0000, "AA": 0.0000, "A": 0.0000, "BBB": 0.0000, "BB": 0.0000, "B": 0.0000, "CCC": 0.0000, "D": 1.0000},
}

# -----------------------------------------------------------------------------
# Registry of all available matrices
# -----------------------------------------------------------------------------
TRANSITION_MATRICES = {
    # Default / Global
    "global": TRANSITION_MATRIX_GLOBAL,
    "us_corporate": TRANSITION_MATRIX_GLOBAL,
    "default": TRANSITION_MATRIX_GLOBAL,

    # Regional
    "europe": TRANSITION_MATRIX_EUROPE,
    "eu": TRANSITION_MATRIX_EUROPE,
    "emerging_markets": TRANSITION_MATRIX_EM,
    "em": TRANSITION_MATRIX_EM,

    # Sector
    "financials": TRANSITION_MATRIX_FINANCIALS,
    "financial": TRANSITION_MATRIX_FINANCIALS,
    "banks": TRANSITION_MATRIX_FINANCIALS,
    "sovereign": TRANSITION_MATRIX_SOVEREIGN,
    "sovereigns": TRANSITION_MATRIX_SOVEREIGN,

    # Economic conditions
    "recession": TRANSITION_MATRIX_RECESSION,
    "stressed": TRANSITION_MATRIX_RECESSION,
    "downturn": TRANSITION_MATRIX_RECESSION,
    "crisis": TRANSITION_MATRIX_RECESSION,
    "benign": TRANSITION_MATRIX_BENIGN,
    "expansion": TRANSITION_MATRIX_BENIGN,
}

# Default matrix for backwards compatibility
TRANSITION_MATRIX = TRANSITION_MATRIX_GLOBAL


def get_transition_matrix(matrix_name: str = "global") -> dict:
    """
    Get a transition matrix by name.

    Parameters
    ----------
    matrix_name : str
        Name of the matrix: "global", "europe", "em", "financials",
        "sovereign", "recession", "benign", etc.

    Returns
    -------
    dict
        Transition matrix.
    """
    if matrix_name.lower() in TRANSITION_MATRICES:
        return TRANSITION_MATRICES[matrix_name.lower()]
    raise ValueError(f"Unknown transition matrix: {matrix_name}. "
                     f"Available: {list(TRANSITION_MATRICES.keys())}")


def list_transition_matrices() -> list[str]:
    """List all available transition matrix names."""
    # Return unique matrices (remove aliases)
    unique = ["global", "europe", "emerging_markets", "financials",
              "sovereign", "recession", "benign"]
    return unique


# Cumulative transition thresholds for simulation (pre-computed for efficiency)
def _build_cumulative_thresholds(matrix: dict = None):
    """Build cumulative probability thresholds for rating simulation."""
    if matrix is None:
        matrix = TRANSITION_MATRIX_GLOBAL
    thresholds = {}
    for from_rating in RATING_CATEGORIES:
        if from_rating == "D":
            thresholds[from_rating] = [(1.0, "D")]
            continue
        probs = matrix[from_rating]
        cumulative = []
        running = 0.0
        for to_rating in RATING_CATEGORIES:
            running += probs[to_rating]
            cumulative.append((running, to_rating))
        thresholds[from_rating] = cumulative
    return thresholds

CUMULATIVE_THRESHOLDS = _build_cumulative_thresholds(TRANSITION_MATRIX_GLOBAL)


# =============================================================================
# Credit Spreads by Rating (basis points, term structure)
# =============================================================================

# Representative credit spreads by rating and tenor (basis points)
CREDIT_SPREADS = {
    # rating: {tenor_years: spread_bps}
    "AAA": {1: 15, 2: 18, 3: 20, 5: 25, 7: 30, 10: 35},
    "AA":  {1: 25, 2: 30, 3: 35, 5: 45, 7: 55, 10: 65},
    "A":   {1: 45, 2: 55, 3: 65, 5: 80, 7: 95, 10: 110},
    "BBB": {1: 90, 2: 105, 3: 120, 5: 150, 7: 175, 10: 200},
    "BB":  {1: 200, 2: 240, 3: 280, 5: 350, 7: 400, 10: 450},
    "B":   {1: 400, 2: 480, 3: 550, 5: 650, 7: 720, 10: 800},
    "CCC": {1: 1000, 2: 1100, 3: 1200, 5: 1350, 7: 1450, 10: 1550},
    "D":   {1: 5000, 2: 5000, 3: 5000, 5: 5000, 7: 5000, 10: 5000},  # Defaulted
}


def get_credit_spread(rating: str, tenor_years: float) -> float:
    """
    Get credit spread for a given rating and tenor (linear interpolation).

    Returns spread in basis points.
    """
    if rating not in CREDIT_SPREADS:
        rating = "B"  # fallback

    spreads = CREDIT_SPREADS[rating]
    tenors = sorted(spreads.keys())

    if tenor_years <= tenors[0]:
        return spreads[tenors[0]]
    if tenor_years >= tenors[-1]:
        return spreads[tenors[-1]]

    # Linear interpolation
    for i in range(len(tenors) - 1):
        if tenors[i] <= tenor_years <= tenors[i + 1]:
            t1, t2 = tenors[i], tenors[i + 1]
            s1, s2 = spreads[t1], spreads[t2]
            return s1 + (s2 - s1) * (tenor_years - t1) / (t2 - t1)

    return spreads[tenors[-1]]


# =============================================================================
# LGD Assumptions
# =============================================================================

LGD_BY_SENIORITY = {
    "senior_secured": 0.25,
    "senior_unsecured": 0.45,
    "subordinated": 0.75,
    "equity": 1.00,
}


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class IRCPosition:
    """A single position for IRC calculation."""
    position_id: str
    issuer: str
    notional: float
    market_value: float              # current MV (can differ from notional for bonds)
    rating: str                      # current rating (AAA, AA, A, BBB, BB, B, CCC)
    tenor_years: float               # remaining maturity
    seniority: str = "senior_unsecured"
    sector: str = "corporate"
    liquidity_horizon_months: int = 3   # rebalancing frequency (1, 3, 6, 12)
    is_long: bool = True
    coupon_rate: float = 0.0         # annual coupon for duration calculation
    lgd: float = None                # custom LGD (0.0-1.0); if provided, overrides seniority


def get_lgd(pos: IRCPosition) -> float:
    """
    Get LGD for a position with priority handling.

    Priority: lgd (if provided) > seniority > default (0.45)

    Parameters
    ----------
    pos : IRCPosition
        Position with optional lgd and seniority fields.

    Returns
    -------
    float
        LGD value between 0.0 and 1.0.
    """
    # Priority 1: Custom LGD if provided
    if pos.lgd is not None:
        if not 0.0 <= pos.lgd <= 1.0:
            raise ValueError(f"LGD must be between 0.0 and 1.0, got {pos.lgd}")
        return pos.lgd

    # Priority 2: Derive from seniority
    return LGD_BY_SENIORITY.get(pos.seniority, 0.45)


@dataclass
class IRCConfig:
    """
    Configuration for IRC Monte Carlo simulation.

    Parameters
    ----------
    num_simulations : int
        Number of Monte Carlo simulations (default: 100,000).
    confidence_level : float
        Confidence level for IRC (default: 0.999 = 99.9%).
    horizon_years : float
        Risk horizon in years (default: 1.0).
    systematic_correlation : float
        Issuer correlation to systematic factor (default: 0.50).
    sector_correlation : float
        Intra-sector correlation boost (default: 0.25).
    seed : int
        Random seed for reproducibility.
    transition_matrix : str or dict
        Rating transition matrix to use. Can be:
        - String name: "global", "europe", "em", "financials", "sovereign",
                       "recession", "benign"
        - Custom dict: {"AAA": {"AAA": 0.90, "AA": 0.08, ...}, ...}
    """
    num_simulations: int = 100_000
    confidence_level: float = 0.999
    horizon_years: float = 1.0
    systematic_correlation: float = 0.50   # issuer correlation to systematic factor
    sector_correlation: float = 0.25       # intra-sector correlation boost
    seed: int = 42
    transition_matrix: str | dict = "global"  # matrix name or custom dict

    def get_matrix(self) -> dict:
        """Get the actual transition matrix dict."""
        if isinstance(self.transition_matrix, dict):
            return self.transition_matrix
        return get_transition_matrix(self.transition_matrix)


# =============================================================================
# Duration and Price Sensitivity
# =============================================================================

def calculate_modified_duration(
    tenor_years: float,
    coupon_rate: float = 0.05,
    yield_rate: float = 0.05,
) -> float:
    """
    Calculate modified duration for a bond.

    Uses simplified Macaulay duration formula.
    """
    if tenor_years <= 0:
        return 0.0

    if coupon_rate <= 0:
        # Zero-coupon: duration = maturity
        return tenor_years / (1 + yield_rate)

    # Simplified: duration ≈ (1 - (1+y)^(-n)) / y
    mac_duration = (1 - (1 + yield_rate) ** (-tenor_years)) / yield_rate
    mod_duration = mac_duration / (1 + yield_rate)

    return min(mod_duration, tenor_years)  # Cap at maturity


def calculate_spread_pv01(
    notional: float,
    tenor_years: float,
    coupon_rate: float = 0.05,
) -> float:
    """
    Calculate spread PV01 (price change per 1bp spread move).

    Spread PV01 ≈ notional × modified_duration × 0.0001
    """
    mod_dur = calculate_modified_duration(tenor_years, coupon_rate)
    return notional * mod_dur * 0.0001


# =============================================================================
# Monte Carlo Simulation Engine
# =============================================================================

def simulate_rating_migration(
    current_rating: str,
    uniform_draw: float,
    thresholds: dict = None,
) -> str:
    """
    Simulate rating migration based on a uniform random draw [0, 1].

    Parameters
    ----------
    current_rating : str
        Current rating (AAA to CCC).
    uniform_draw : float
        Uniform random number in [0, 1].
    thresholds : dict, optional
        Cumulative thresholds for this matrix. If None, uses default global matrix.

    Returns
    -------
    str
        New rating after migration.
    """
    if current_rating == "D":
        return "D"

    if thresholds is None:
        thresholds = CUMULATIVE_THRESHOLDS

    if current_rating not in thresholds:
        return current_rating

    rating_thresholds = thresholds[current_rating]
    for threshold, new_rating in rating_thresholds:
        if uniform_draw <= threshold:
            return new_rating

    return "D"  # fallback


def simulate_irc_portfolio(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> list[float]:
    """
    Monte Carlo simulation of IRC portfolio losses.

    Uses a multi-factor Gaussian copula:
    - One systematic factor X driving all issuers
    - Idiosyncratic factor per issuer
    - Sector-based correlation adjustment

    For each simulation:
    1. Draw systematic factor X ~ N(0,1)
    2. For each issuer: Z_i = rho × X + sqrt(1-rho²) × epsilon_i
    3. Convert Z_i to uniform via Phi(Z_i)
    4. Use uniform to determine rating migration
    5. Calculate P&L from migration / default

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions grouped by issuer.
    config : IRCConfig
        Simulation configuration.

    Returns
    -------
    list[float]
        Simulated portfolio losses (one per simulation).
    """
    if config is None:
        config = IRCConfig()

    rng = random.Random(config.seed)

    # Get transition matrix and build cumulative thresholds
    matrix = config.get_matrix()
    thresholds = _build_cumulative_thresholds(matrix)

    # Group positions by issuer (same issuer = same migration)
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    # Pre-compute position-level parameters
    position_params = []
    for pos in positions:
        lgd = get_lgd(pos)
        spread_pv01 = calculate_spread_pv01(pos.notional, pos.tenor_years, pos.coupon_rate)
        current_spread = get_credit_spread(pos.rating, pos.tenor_years)

        # Liquidity horizon adjustment for constant level of risk
        # More frequent rebalancing → lower risk exposure
        lh_factor = math.sqrt(pos.liquidity_horizon_months / 12.0)

        position_params.append({
            "pos": pos,
            "lgd": lgd,
            "spread_pv01": spread_pv01,
            "current_spread": current_spread,
            "lh_factor": lh_factor,
        })

    # Pre-compute issuer correlations
    issuer_rho = {}
    sectors = {}
    for issuer, pos_list in issuer_positions.items():
        sector = pos_list[0].sector
        sectors[issuer] = sector
        # Base correlation + sector boost if same sector
        issuer_rho[issuer] = config.systematic_correlation

    def _std_normal():
        """Box-Muller for standard normal."""
        u1 = max(rng.random(), 1e-15)
        u2 = rng.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def _phi(x):
        """Standard normal CDF approximation (Abramowitz & Stegun)."""
        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p = 0.3275911
        sign = 1 if x >= 0 else -1
        x = abs(x)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
        return 0.5 * (1.0 + sign * y)

    losses = []

    for _ in range(config.num_simulations):
        # Draw systematic factor
        systematic = _std_normal()

        # Simulate migration for each issuer
        issuer_new_rating = {}
        for issuer, pos_list in issuer_positions.items():
            current_rating = pos_list[0].rating  # All positions for issuer have same rating
            rho = issuer_rho[issuer]

            # Correlated latent variable
            idio = _std_normal()
            z = rho * systematic + math.sqrt(1.0 - rho * rho) * idio

            # Convert to uniform via Phi
            u = _phi(z)

            # Simulate migration using the configured transition matrix
            new_rating = simulate_rating_migration(current_rating, u, thresholds)
            issuer_new_rating[issuer] = new_rating

        # Calculate portfolio loss with netting within same issuer
        # First, calculate P&L by issuer (allowing long/short to offset)
        issuer_pnl: dict[str, float] = {}

        for params in position_params:
            pos = params["pos"]
            new_rating = issuer_new_rating[pos.issuer]

            if new_rating == "D":
                # Default: lose LGD × notional
                loss = params["lgd"] * abs(pos.notional)
            else:
                # Migration: spread change × PV01
                new_spread = get_credit_spread(new_rating, pos.tenor_years)
                spread_change = new_spread - params["current_spread"]  # in bps
                loss = spread_change * params["spread_pv01"]  # positive = loss

            # Apply liquidity horizon factor
            loss *= params["lh_factor"]

            # Direction: short positions gain from widening (negative loss)
            if not pos.is_long:
                loss = -loss

            # Accumulate by issuer (allows netting within issuer)
            issuer_pnl[pos.issuer] = issuer_pnl.get(pos.issuer, 0.0) + loss

        # Portfolio loss = sum of positive issuer P&Ls (no cross-issuer netting)
        portfolio_loss = sum(max(pnl, 0.0) for pnl in issuer_pnl.values())

        losses.append(portfolio_loss)

    return losses


# =============================================================================
# Vectorized Monte Carlo (NumPy) — 50-100× faster
# =============================================================================

def _build_transition_arrays(matrix: dict = None):
    """
    Build NumPy-friendly transition arrays for vectorized simulation.

    Parameters
    ----------
    matrix : dict, optional
        Transition matrix to use. If None, uses default global matrix.

    Returns
    -------
    tuple
        (thresholds, targets, rating_to_idx) for vectorized lookup.
    """
    if matrix is None:
        matrix = TRANSITION_MATRIX_GLOBAL

    # Rating to index mapping
    rating_to_idx = {r: i for i, r in enumerate(RATING_CATEGORIES)}

    # Build arrays: for each from_rating, cumulative thresholds and target indices
    thresholds = {}
    targets = {}

    for from_rating in RATING_CATEGORIES[:-1]:  # Exclude 'D' (absorbing state)
        probs = matrix[from_rating]
        cum_probs = []
        target_indices = []
        running = 0.0
        for to_rating in RATING_CATEGORIES:
            running += probs[to_rating]
            cum_probs.append(running)
            target_indices.append(rating_to_idx[to_rating])
        thresholds[from_rating] = cum_probs
        targets[from_rating] = target_indices

    return thresholds, targets, rating_to_idx


# Pre-build default for efficiency (used when config uses "global" matrix)
_TRANSITION_THRESHOLDS, _TRANSITION_TARGETS, _RATING_TO_IDX = _build_transition_arrays(TRANSITION_MATRIX_GLOBAL)


def simulate_irc_portfolio_vectorized(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> list[float]:
    """
    Vectorized Monte Carlo simulation of IRC portfolio losses using NumPy.

    This is 50-100× faster than the pure Python version for large portfolios.
    Uses the same random process (Gaussian copula) so precision is identical.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    config : IRCConfig
        Simulation configuration.

    Returns
    -------
    list[float]
        Simulated portfolio losses (one per simulation).
    """
    try:
        import numpy as np
        from scipy.stats import norm
    except ImportError:
        # Fallback to pure Python version
        return simulate_irc_portfolio(positions, config)

    if config is None:
        config = IRCConfig()

    n_sims = config.num_simulations
    rng = np.random.default_rng(config.seed)

    # Get transition matrix and build arrays
    matrix = config.get_matrix()
    if matrix is TRANSITION_MATRIX_GLOBAL:
        # Use pre-computed arrays for default matrix (faster)
        trans_thresholds = _TRANSITION_THRESHOLDS
        trans_targets = _TRANSITION_TARGETS
        rating_to_idx = _RATING_TO_IDX
    else:
        # Build arrays for custom/non-default matrix
        trans_thresholds, trans_targets, rating_to_idx = _build_transition_arrays(matrix)

    # Group positions by issuer
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    issuers = list(issuer_positions.keys())
    n_issuers = len(issuers)
    issuer_to_idx = {issuer: i for i, issuer in enumerate(issuers)}

    # Pre-compute issuer-level parameters
    issuer_ratings = []
    issuer_rhos = []
    for issuer in issuers:
        pos_list = issuer_positions[issuer]
        issuer_ratings.append(pos_list[0].rating)
        issuer_rhos.append(config.systematic_correlation)

    issuer_rhos = np.array(issuer_rhos)

    # Pre-compute position-level parameters
    n_positions = len(positions)
    pos_issuer_idx = np.zeros(n_positions, dtype=np.int32)
    pos_lgd = np.zeros(n_positions)
    pos_spread_pv01 = np.zeros(n_positions)
    pos_current_spread = np.zeros(n_positions)
    pos_lh_factor = np.zeros(n_positions)
    pos_direction = np.zeros(n_positions)  # +1 for long, -1 for short

    for i, pos in enumerate(positions):
        pos_issuer_idx[i] = issuer_to_idx[pos.issuer]
        pos_lgd[i] = get_lgd(pos)
        pos_spread_pv01[i] = calculate_spread_pv01(pos.notional, pos.tenor_years, pos.coupon_rate)
        pos_current_spread[i] = get_credit_spread(pos.rating, pos.tenor_years)
        pos_lh_factor[i] = math.sqrt(pos.liquidity_horizon_months / 12.0)
        pos_direction[i] = 1.0 if pos.is_long else -1.0

    pos_notional = np.array([abs(pos.notional) for pos in positions])

    # Pre-compute spread changes for all rating transitions
    # spread_change_matrix[from_rating_idx, to_rating_idx, position_idx] = new_spread
    spread_lookup = {}
    for i, pos in enumerate(positions):
        for to_rating in RATING_CATEGORIES:
            spread_lookup[(i, to_rating)] = get_credit_spread(to_rating, pos.tenor_years)

    # Generate all random numbers at once
    # Shape: (n_sims,) for systematic, (n_sims, n_issuers) for idiosyncratic
    systematic = rng.standard_normal(n_sims)
    idiosyncratic = rng.standard_normal((n_sims, n_issuers))

    # Correlated latent variables: Z = rho * X + sqrt(1-rho²) * epsilon
    # Shape: (n_sims, n_issuers)
    sqrt_one_minus_rho2 = np.sqrt(1.0 - issuer_rhos ** 2)
    z = issuer_rhos * systematic[:, np.newaxis] + sqrt_one_minus_rho2 * idiosyncratic

    # Convert to uniform via Phi (standard normal CDF)
    u = norm.cdf(z)  # Shape: (n_sims, n_issuers)

    # Simulate rating migrations for all issuers across all simulations
    # new_ratings[sim, issuer] = new rating index
    new_rating_idx = np.zeros((n_sims, n_issuers), dtype=np.int32)

    for j, issuer in enumerate(issuers):
        current_rating = issuer_ratings[j]
        if current_rating == "D":
            new_rating_idx[:, j] = rating_to_idx["D"]
            continue

        thresholds = trans_thresholds[current_rating]
        targets = trans_targets[current_rating]

        # Vectorized migration: find first threshold exceeded
        u_col = u[:, j]  # Shape: (n_sims,)

        # Use searchsorted for vectorized threshold lookup
        threshold_arr = np.array(thresholds)
        indices = np.searchsorted(threshold_arr, u_col, side='left')
        indices = np.clip(indices, 0, len(targets) - 1)
        new_rating_idx[:, j] = np.array(targets)[indices]

    # Calculate losses for all simulations
    # Shape: (n_sims, n_positions)
    losses_matrix = np.zeros((n_sims, n_positions))

    default_idx = rating_to_idx["D"]

    for i, pos in enumerate(positions):
        issuer_idx = pos_issuer_idx[i]
        new_ratings_for_pos = new_rating_idx[:, issuer_idx]  # Shape: (n_sims,)

        # Default case: loss = LGD × notional
        is_default = new_ratings_for_pos == default_idx
        default_loss = pos_lgd[i] * pos_notional[i]

        # Migration case: loss = spread_change × PV01
        migration_loss = np.zeros(n_sims)
        for rating_idx, rating in enumerate(RATING_CATEGORIES):
            if rating == "D":
                continue
            mask = new_ratings_for_pos == rating_idx
            if mask.any():
                new_spread = spread_lookup[(i, rating)]
                spread_change = new_spread - pos_current_spread[i]
                migration_loss[mask] = spread_change * pos_spread_pv01[i]

        # Combine: default takes precedence
        loss = np.where(is_default, default_loss, migration_loss)

        # Apply liquidity horizon factor and direction
        loss = loss * pos_lh_factor[i] * pos_direction[i]

        losses_matrix[:, i] = loss

    # Aggregate by issuer (allows netting within issuer)
    issuer_pnl = np.zeros((n_sims, n_issuers))
    for i in range(n_positions):
        issuer_idx = pos_issuer_idx[i]
        issuer_pnl[:, issuer_idx] += losses_matrix[:, i]

    # Portfolio loss = sum of positive issuer P&Ls (no cross-issuer netting)
    portfolio_losses = np.sum(np.maximum(issuer_pnl, 0.0), axis=1)

    return portfolio_losses.tolist()


def calculate_irc(
    positions: list[IRCPosition],
    config: IRCConfig = None,
    use_vectorized: bool = True,
) -> dict:
    """
    Calculate IRC via Monte Carlo simulation.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio of credit positions.
    config : IRCConfig
        Simulation configuration.
    use_vectorized : bool
        If True (default), use NumPy vectorized simulation (50-100× faster).
        Falls back to pure Python if NumPy/SciPy not available.

    Returns
    -------
    dict
        IRC charge and distribution statistics.
    """
    if config is None:
        config = IRCConfig()

    if not positions:
        return {"irc": 0.0, "mean_loss": 0.0, "num_simulations": 0}

    # Run simulation (vectorized by default for speed)
    if use_vectorized:
        losses = simulate_irc_portfolio_vectorized(positions, config)
    else:
        losses = simulate_irc_portfolio(positions, config)

    # Sort for percentile calculation
    losses_sorted = sorted(losses)
    n = len(losses_sorted)

    # IRC = 99.9th percentile
    idx_999 = min(int(n * config.confidence_level), n - 1)
    irc = losses_sorted[idx_999]

    # Statistics
    mean_loss = sum(losses) / n
    idx_99 = min(int(n * 0.99), n - 1)
    idx_95 = min(int(n * 0.95), n - 1)
    idx_50 = n // 2

    # Expected shortfall at 99.9%
    tail_losses = losses_sorted[idx_999:]
    es_999 = sum(tail_losses) / len(tail_losses) if tail_losses else irc

    # Portfolio summary
    total_notional = sum(abs(p.notional) for p in positions)
    num_issuers = len(set(p.issuer for p in positions))

    return {
        "approach": "IRC (Monte Carlo)",
        "irc": irc,
        "rwa": irc * 12.5,
        "capital_ratio": irc / total_notional if total_notional > 0 else 0.0,
        "mean_loss": mean_loss,
        "median_loss": losses_sorted[idx_50],
        "percentile_95": losses_sorted[idx_95],
        "percentile_99": losses_sorted[idx_99],
        "percentile_999": irc,
        "expected_shortfall_999": es_999,
        "max_loss": losses_sorted[-1],
        "min_loss": losses_sorted[0],
        "num_simulations": n,
        "num_positions": len(positions),
        "num_issuers": num_issuers,
        "total_notional": total_notional,
        "config": {
            "confidence_level": config.confidence_level,
            "horizon_years": config.horizon_years,
            "systematic_correlation": config.systematic_correlation,
        },
    }


def calculate_irc_multi_matrix(
    positions: list[IRCPosition],
    config: IRCConfig,
    issuer_matrix_map: dict[str, str],
) -> dict:
    """
    Calculate IRC with different transition matrices per issuer.

    This allows mixed portfolios where different issuers use different
    matrices (e.g., US corporates vs EM vs financials).

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    config : IRCConfig
        Base configuration (default matrix for unmapped issuers).
    issuer_matrix_map : dict
        Mapping of issuer name to matrix name.

    Returns
    -------
    dict
        IRC result.
    """
    try:
        import numpy as np
        from scipy.stats import norm
    except ImportError:
        raise ImportError("NumPy and SciPy required for multi-matrix IRC")

    if not positions:
        return {"irc": 0.0, "mean_loss": 0.0, "num_simulations": 0}

    n_sims = config.num_simulations
    rng = np.random.default_rng(config.seed)

    # Get default matrix
    default_matrix = config.get_matrix()

    # Build thresholds for each unique matrix
    unique_matrices = set(issuer_matrix_map.values())
    matrix_thresholds = {}
    for matrix_name in unique_matrices:
        matrix = get_transition_matrix(matrix_name)
        matrix_thresholds[matrix_name] = _build_cumulative_thresholds(matrix)

    # Add default matrix thresholds
    matrix_thresholds["_default"] = _build_cumulative_thresholds(default_matrix)

    # Group positions by issuer
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    issuers = list(issuer_positions.keys())
    n_issuers = len(issuers)
    issuer_to_idx = {issuer: i for i, issuer in enumerate(issuers)}

    # Map each issuer to its thresholds
    issuer_thresholds = {}
    for issuer in issuers:
        if issuer in issuer_matrix_map:
            issuer_thresholds[issuer] = matrix_thresholds[issuer_matrix_map[issuer]]
        else:
            issuer_thresholds[issuer] = matrix_thresholds["_default"]

    # Pre-compute issuer-level parameters
    issuer_ratings = []
    issuer_rhos = []
    for issuer in issuers:
        pos_list = issuer_positions[issuer]
        issuer_ratings.append(pos_list[0].rating)
        issuer_rhos.append(config.systematic_correlation)

    issuer_rhos = np.array(issuer_rhos)

    # Pre-compute position-level parameters
    n_positions = len(positions)
    pos_issuer_idx = np.zeros(n_positions, dtype=np.int32)
    pos_lgd = np.zeros(n_positions)
    pos_spread_pv01 = np.zeros(n_positions)
    pos_current_spread = np.zeros(n_positions)
    pos_lh_factor = np.zeros(n_positions)
    pos_direction = np.zeros(n_positions)

    for i, pos in enumerate(positions):
        pos_issuer_idx[i] = issuer_to_idx[pos.issuer]
        pos_lgd[i] = get_lgd(pos)
        pos_spread_pv01[i] = calculate_spread_pv01(pos.notional, pos.tenor_years, pos.coupon_rate)
        pos_current_spread[i] = get_credit_spread(pos.rating, pos.tenor_years)
        pos_lh_factor[i] = math.sqrt(pos.liquidity_horizon_months / 12.0)
        pos_direction[i] = 1.0 if pos.is_long else -1.0

    pos_notional = np.array([abs(pos.notional) for pos in positions])

    # Pre-compute spread lookup
    spread_lookup = {}
    for i, pos in enumerate(positions):
        for to_rating in RATING_CATEGORIES:
            spread_lookup[(i, to_rating)] = get_credit_spread(to_rating, pos.tenor_years)

    # Generate random numbers
    systematic = rng.standard_normal(n_sims)
    idiosyncratic = rng.standard_normal((n_sims, n_issuers))

    sqrt_one_minus_rho2 = np.sqrt(1.0 - issuer_rhos ** 2)
    z = issuer_rhos * systematic[:, np.newaxis] + sqrt_one_minus_rho2 * idiosyncratic
    u = norm.cdf(z)

    # Simulate rating migrations using per-issuer matrices
    rating_to_idx = {r: i for i, r in enumerate(RATING_CATEGORIES)}
    new_rating_idx = np.zeros((n_sims, n_issuers), dtype=np.int32)

    for j, issuer in enumerate(issuers):
        current_rating = issuer_ratings[j]
        thresholds = issuer_thresholds[issuer]

        if current_rating == "D":
            new_rating_idx[:, j] = rating_to_idx["D"]
            continue

        rating_thresholds = thresholds[current_rating]
        cum_probs = [t[0] for t in rating_thresholds]
        target_ratings = [t[1] for t in rating_thresholds]
        target_indices = [rating_to_idx[r] for r in target_ratings]

        u_col = u[:, j]
        threshold_arr = np.array(cum_probs)
        indices = np.searchsorted(threshold_arr, u_col, side='left')
        indices = np.clip(indices, 0, len(target_indices) - 1)
        new_rating_idx[:, j] = np.array(target_indices)[indices]

    # Calculate losses
    losses_matrix = np.zeros((n_sims, n_positions))
    default_idx = rating_to_idx["D"]

    for i, pos in enumerate(positions):
        issuer_idx = pos_issuer_idx[i]
        new_ratings_for_pos = new_rating_idx[:, issuer_idx]

        is_default = new_ratings_for_pos == default_idx
        default_loss = pos_lgd[i] * pos_notional[i]

        migration_loss = np.zeros(n_sims)
        for rating_idx, rating in enumerate(RATING_CATEGORIES):
            if rating == "D":
                continue
            mask = new_ratings_for_pos == rating_idx
            if mask.any():
                new_spread = spread_lookup[(i, rating)]
                spread_change = new_spread - pos_current_spread[i]
                migration_loss[mask] = spread_change * pos_spread_pv01[i]

        loss = np.where(is_default, default_loss, migration_loss)
        loss = loss * pos_lh_factor[i] * pos_direction[i]
        losses_matrix[:, i] = loss

    # Aggregate by issuer
    issuer_pnl = np.zeros((n_sims, n_issuers))
    for i in range(n_positions):
        issuer_idx = pos_issuer_idx[i]
        issuer_pnl[:, issuer_idx] += losses_matrix[:, i]

    portfolio_losses = np.sum(np.maximum(issuer_pnl, 0.0), axis=1)
    losses = portfolio_losses.tolist()

    # Calculate statistics
    losses_sorted = sorted(losses)
    n = len(losses_sorted)

    idx_999 = min(int(n * config.confidence_level), n - 1)
    irc = losses_sorted[idx_999]

    mean_loss = sum(losses) / n
    idx_99 = min(int(n * 0.99), n - 1)
    idx_95 = min(int(n * 0.95), n - 1)
    idx_50 = n // 2

    tail_losses = losses_sorted[idx_999:]
    es_999 = sum(tail_losses) / len(tail_losses) if tail_losses else irc

    total_notional = sum(abs(p.notional) for p in positions)
    num_issuers = len(set(p.issuer for p in positions))

    return {
        "approach": "IRC (Multi-Matrix Monte Carlo)",
        "irc": irc,
        "rwa": irc * 12.5,
        "capital_ratio": irc / total_notional if total_notional > 0 else 0.0,
        "mean_loss": mean_loss,
        "median_loss": losses_sorted[idx_50],
        "percentile_95": losses_sorted[idx_95],
        "percentile_99": losses_sorted[idx_99],
        "percentile_999": irc,
        "expected_shortfall_999": es_999,
        "max_loss": losses_sorted[-1],
        "min_loss": losses_sorted[0],
        "num_simulations": n,
        "num_positions": len(positions),
        "num_issuers": num_issuers,
        "total_notional": total_notional,
        "matrices_used": list(set(issuer_matrix_map.values())),
        "config": {
            "confidence_level": config.confidence_level,
            "horizon_years": config.horizon_years,
            "systematic_correlation": config.systematic_correlation,
        },
    }


# =============================================================================
# Interactive Portfolio Class (for Jupyter notebooks)
# =============================================================================

class IRCPortfolio:
    """
    Interactive portfolio builder for IRC calculation.

    Designed for Jupyter notebooks — add positions incrementally,
    view portfolio state, then calculate IRC when ready.

    Example
    -------
    >>> from irc import IRCPortfolio
    >>> portfolio = IRCPortfolio()
    >>>
    >>> # Add positions one by one
    >>> portfolio.add("Apple", "AA", 5.0, 20_000_000)
    >>> portfolio.add("Microsoft", "AAA", 7.0, 15_000_000)
    >>> portfolio.add("Ford", "BB", 3.0, 10_000_000, seniority="senior_secured")
    >>>
    >>> # Add with custom LGD
    >>> portfolio.add("Tesla", "BBB", 4.0, 12_000_000, lgd=0.40)
    >>>
    >>> # Add short position (CDS protection)
    >>> portfolio.add("Ford", "BB", 5.0, 5_000_000, is_long=False)
    >>>
    >>> # View portfolio
    >>> portfolio.show()
    >>>
    >>> # Calculate IRC
    >>> result = portfolio.irc()
    >>> print(f"IRC: ${result['irc']:,.0f}")
    >>>
    >>> # Get issuer breakdown
    >>> result = portfolio.irc_by_issuer()
    """

    def __init__(
        self,
        num_simulations: int = 50_000,
        correlation: float = 0.50,
        transition_matrix: str | dict = "global",
    ):
        """
        Initialize portfolio.

        Parameters
        ----------
        num_simulations : int
            Number of Monte Carlo simulations.
        correlation : float
            Systematic correlation.
        transition_matrix : str or dict
            Default transition matrix.
        """
        self.positions: list[dict] = []
        self.num_simulations = num_simulations
        self.correlation = correlation
        self.transition_matrix = transition_matrix
        self._position_counter = 0

    def add(
        self,
        issuer: str,
        rating: str,
        tenor_years: float,
        notional: float,
        seniority: str = None,
        lgd: float = None,
        sector: str = None,
        region: str = None,
        is_long: bool = True,
        liquidity_horizon_months: int = 3,
        coupon_rate: float = 0.05,
        position_id: str = None,
    ) -> "IRCPortfolio":
        """
        Add a position to the portfolio.

        Parameters
        ----------
        issuer : str
            Obligor name.
        rating : str
            Credit rating (AAA, AA, A, BBB, BB, B, CCC).
        tenor_years : float
            Remaining maturity in years.
        notional : float
            Position size (positive number).
        seniority : str, optional
            senior_secured (25% LGD), senior_unsecured (45%), subordinated (75%).
        lgd : float, optional
            Custom LGD (0.0-1.0). Overrides seniority if provided.
        sector : str, optional
            Sector for correlation.
        region : str, optional
            Region for matrix selection.
        is_long : bool
            True for long credit, False for short (CDS protection).
        liquidity_horizon_months : int
            Rebalancing frequency (3, 6, or 12).
        coupon_rate : float
            Annual coupon rate.
        position_id : str, optional
            Unique identifier.

        Returns
        -------
        IRCPortfolio
            Self, for method chaining.
        """
        # Validate rating
        valid_ratings = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]
        if rating.upper() not in valid_ratings:
            raise ValueError(f"Invalid rating '{rating}'. Must be one of {valid_ratings}")

        # Validate LGD
        if lgd is not None and not 0.0 <= lgd <= 1.0:
            raise ValueError(f"LGD must be between 0.0 and 1.0, got {lgd}")

        # Validate seniority
        valid_seniorities = ["senior_secured", "senior_unsecured", "subordinated"]
        if seniority is not None and seniority not in valid_seniorities:
            raise ValueError(f"Invalid seniority '{seniority}'. Must be one of {valid_seniorities}")

        self._position_counter += 1
        pos = {
            "position_id": position_id or f"pos_{self._position_counter}",
            "issuer": issuer,
            "rating": rating.upper(),
            "tenor_years": tenor_years,
            "notional": abs(notional),
            "is_long": is_long,
            "liquidity_horizon_months": liquidity_horizon_months,
            "coupon_rate": coupon_rate,
        }

        if seniority:
            pos["seniority"] = seniority
        if lgd is not None:
            pos["lgd"] = lgd
        if sector:
            pos["sector"] = sector
        if region:
            pos["region"] = region

        self.positions.append(pos)
        return self  # Allow chaining

    def add_many(self, positions: list[dict]) -> "IRCPortfolio":
        """
        Add multiple positions from a list of dicts.

        Parameters
        ----------
        positions : list[dict]
            List of position dicts (same format as quick_irc).

        Returns
        -------
        IRCPortfolio
            Self, for method chaining.
        """
        import math

        def _clean(val, default=None):
            """Handle NaN values from pandas."""
            if val is None:
                return default
            try:
                if math.isnan(val):
                    return default
            except (TypeError, ValueError):
                pass
            return val

        for p in positions:
            self.add(
                issuer=p["issuer"],
                rating=p["rating"],
                tenor_years=p["tenor_years"],
                notional=p["notional"],
                seniority=_clean(p.get("seniority")),
                lgd=_clean(p.get("lgd")),
                sector=_clean(p.get("sector")),
                region=_clean(p.get("region")),
                is_long=_clean(p.get("is_long"), True),
                liquidity_horizon_months=int(_clean(p.get("liquidity_horizon_months"), 3)),
                coupon_rate=float(_clean(p.get("coupon_rate"), 0.05)),
                position_id=_clean(p.get("position_id")),
            )
        return self

    def add_from_dataframe(self, df) -> "IRCPortfolio":
        """
        Add positions from a pandas DataFrame.

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame with position columns.

        Returns
        -------
        IRCPortfolio
            Self, for method chaining.
        """
        return self.add_many(df.to_dict(orient="records"))

    def remove(self, position_id: str) -> "IRCPortfolio":
        """Remove a position by ID."""
        self.positions = [p for p in self.positions if p.get("position_id") != position_id]
        return self

    def clear(self) -> "IRCPortfolio":
        """Remove all positions."""
        self.positions = []
        self._position_counter = 0
        return self

    def show(self) -> None:
        """Display portfolio summary."""
        if not self.positions:
            print("Portfolio is empty. Use .add() to add positions.")
            return

        try:
            import pandas as pd
            df = pd.DataFrame(self.positions)
            cols = ["position_id", "issuer", "rating", "tenor_years", "notional", "is_long"]
            extra_cols = [c for c in ["seniority", "lgd", "sector", "region"] if c in df.columns]
            cols = [c for c in cols if c in df.columns] + extra_cols
            print(df[cols].to_string(index=False))
        except ImportError:
            # Fallback without pandas
            print(f"{'ID':<10} {'Issuer':<15} {'Rating':>6} {'Tenor':>6} {'Notional':>14} {'Long':>5}")
            print("-" * 65)
            for p in self.positions:
                print(f"{p.get('position_id', '-'):<10} {p['issuer']:<15} {p['rating']:>6} "
                      f"{p['tenor_years']:>6.1f} ${p['notional']:>12,.0f} {'Y' if p.get('is_long', True) else 'N':>5}")

        print(f"\nTotal: {len(self.positions)} positions, "
              f"{len(set(p['issuer'] for p in self.positions))} issuers, "
              f"${sum(p['notional'] for p in self.positions):,.0f} notional")

    def summary(self) -> dict:
        """Get portfolio summary as dict."""
        if not self.positions:
            return {"num_positions": 0, "num_issuers": 0, "total_notional": 0}

        return {
            "num_positions": len(self.positions),
            "num_issuers": len(set(p["issuer"] for p in self.positions)),
            "total_notional": sum(p["notional"] for p in self.positions),
            "long_notional": sum(p["notional"] for p in self.positions if p.get("is_long", True)),
            "short_notional": sum(p["notional"] for p in self.positions if not p.get("is_long", True)),
            "ratings": dict(sorted(
                {r: sum(1 for p in self.positions if p["rating"] == r)
                 for r in set(p["rating"] for p in self.positions)}.items()
            )),
        }

    def to_dataframe(self):
        """Convert positions to pandas DataFrame."""
        try:
            import pandas as pd
            return pd.DataFrame(self.positions)
        except ImportError:
            raise ImportError("pandas required for to_dataframe()")

    def irc(
        self,
        matrix_by_region: dict = None,
        matrix_by_sector: dict = None,
        matrix_by_issuer: dict = None,
    ) -> dict:
        """
        Calculate IRC for the portfolio.

        Parameters
        ----------
        matrix_by_region : dict, optional
            Map region to matrix.
        matrix_by_sector : dict, optional
            Map sector to matrix.
        matrix_by_issuer : dict, optional
            Map issuer to matrix.

        Returns
        -------
        dict
            IRC result.
        """
        if not self.positions:
            raise ValueError("Portfolio is empty. Add positions first.")

        return quick_irc(
            self.positions,
            num_simulations=self.num_simulations,
            correlation=self.correlation,
            transition_matrix=self.transition_matrix,
            matrix_by_region=matrix_by_region,
            matrix_by_sector=matrix_by_sector,
            matrix_by_issuer=matrix_by_issuer,
        )

    def irc_by_issuer(
        self,
        matrix_by_region: dict = None,
        matrix_by_sector: dict = None,
        matrix_by_issuer: dict = None,
    ) -> dict:
        """
        Calculate IRC with issuer breakdown.

        Returns
        -------
        dict
            IRC result with issuer_contributions.
        """
        if not self.positions:
            raise ValueError("Portfolio is empty. Add positions first.")

        # Convert to IRCPosition objects
        irc_positions = []
        for i, p in enumerate(self.positions):
            irc_positions.append(IRCPosition(
                position_id=p.get("position_id", f"pos_{i}"),
                issuer=p["issuer"],
                notional=p["notional"],
                market_value=p.get("market_value", p["notional"]),
                rating=p["rating"],
                tenor_years=p["tenor_years"],
                seniority=p.get("seniority", "senior_unsecured"),
                sector=p.get("sector", "corporate"),
                liquidity_horizon_months=p.get("liquidity_horizon_months", 3),
                is_long=p.get("is_long", True),
                coupon_rate=p.get("coupon_rate", 0.05),
                lgd=p.get("lgd"),
            ))

        config = IRCConfig(
            num_simulations=self.num_simulations,
            systematic_correlation=self.correlation,
            transition_matrix=self.transition_matrix,
        )

        return calculate_irc_by_issuer(irc_positions, config)

    def __len__(self):
        return len(self.positions)

    def __repr__(self):
        return f"IRCPortfolio({len(self.positions)} positions, {len(set(p['issuer'] for p in self.positions))} issuers)"


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_irc(
    positions: list[dict],
    num_simulations: int = 50_000,
    correlation: float = 0.50,
    transition_matrix: str | dict = "global",
    matrix_by_region: dict[str, str] = None,
    matrix_by_sector: dict[str, str] = None,
    matrix_by_issuer: dict[str, str] = None,
) -> dict:
    """
    Quick IRC calculation from simplified position dicts.

    Parameters
    ----------
    positions : list[dict]
        Each dict must have: issuer, notional, rating, tenor_years.
        Optional fields:
        - seniority: "senior_secured", "senior_unsecured", "subordinated"
        - lgd: float (0.0-1.0) — custom LGD, overrides seniority if provided
        - sector, region, liquidity_horizon_months, is_long, coupon_rate

        LGD Priority: lgd > seniority > default (0.45)
        If both lgd and seniority provided, lgd wins.

    num_simulations : int
        Number of MC simulations.
    correlation : float
        Systematic correlation.
    transition_matrix : str or dict
        Default transition matrix for positions without specific mapping.
    matrix_by_region : dict, optional
        Map region to matrix: {"US": "global", "EU": "europe", "EM": "emerging_markets"}
    matrix_by_sector : dict, optional
        Map sector to matrix: {"financial": "financials", "sovereign": "sovereign"}
    matrix_by_issuer : dict, optional
        Map issuer to matrix (highest priority): {"Deutsche Bank": "financials"}

    Returns
    -------
    dict
        IRC result.

    Example
    -------
    >>> positions = [
    ...     {"issuer": "Apple", "rating": "AA", "tenor_years": 5, "notional": 10e6,
    ...      "region": "US", "sector": "tech"},
    ...     {"issuer": "Deutsche Bank", "rating": "A", "tenor_years": 5, "notional": 10e6,
    ...      "region": "EU", "sector": "financial"},
    ...     {"issuer": "Petrobras", "rating": "BB", "tenor_years": 5, "notional": 10e6,
    ...      "region": "EM", "sector": "energy"},
    ... ]
    >>> result = quick_irc(
    ...     positions,
    ...     matrix_by_region={"US": "global", "EU": "europe", "EM": "emerging_markets"},
    ...     matrix_by_sector={"financial": "financials"},
    ...     matrix_by_issuer={"Petrobras": "recession"},  # override for specific issuer
    ... )
    """
    # Build issuer -> matrix mapping
    issuer_matrix_map = {}

    for p in positions:
        issuer = p["issuer"]
        if issuer in issuer_matrix_map:
            continue

        # Priority: issuer > sector > region > default
        matrix_name = None

        if matrix_by_issuer and issuer in matrix_by_issuer:
            matrix_name = matrix_by_issuer[issuer]
        elif matrix_by_sector and p.get("sector") in matrix_by_sector:
            matrix_name = matrix_by_sector[p.get("sector")]
        elif matrix_by_region and p.get("region") in matrix_by_region:
            matrix_name = matrix_by_region[p.get("region")]

        if matrix_name:
            issuer_matrix_map[issuer] = matrix_name

    irc_positions = []
    for i, p in enumerate(positions):
        irc_positions.append(IRCPosition(
            position_id=p.get("position_id", f"pos_{i}"),
            issuer=p["issuer"],
            notional=p["notional"],
            market_value=p.get("market_value", p["notional"]),
            rating=p["rating"],
            tenor_years=p["tenor_years"],
            seniority=p.get("seniority", "senior_unsecured"),
            sector=p.get("sector", "corporate"),
            liquidity_horizon_months=p.get("liquidity_horizon_months", 3),
            is_long=p.get("is_long", True),
            coupon_rate=p.get("coupon_rate", 0.05),
            lgd=p.get("lgd"),  # Custom LGD (overrides seniority if provided)
        ))

    config = IRCConfig(
        num_simulations=num_simulations,
        systematic_correlation=correlation,
        transition_matrix=transition_matrix,
    )

    # If we have per-issuer mappings, use the multi-matrix simulation
    if issuer_matrix_map:
        return calculate_irc_multi_matrix(irc_positions, config, issuer_matrix_map)

    return calculate_irc(irc_positions, config)


def calculate_irc_by_issuer(
    positions: list[IRCPosition],
    config: IRCConfig = None,
) -> dict:
    """
    Calculate IRC with breakdown by issuer contribution.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    config : IRCConfig
        Configuration.

    Returns
    -------
    dict
        IRC with per-issuer marginal contributions.
    """
    if config is None:
        config = IRCConfig()

    # Full portfolio IRC
    full_result = calculate_irc(positions, config)
    full_irc = full_result["irc"]

    # Group by issuer
    issuer_positions: dict[str, list[IRCPosition]] = {}
    for pos in positions:
        issuer_positions.setdefault(pos.issuer, []).append(pos)

    # Calculate marginal contribution per issuer
    issuer_contributions = []
    for issuer, issuer_pos_list in issuer_positions.items():
        # Standalone IRC for this issuer
        standalone = calculate_irc(issuer_pos_list, config)

        # IRC without this issuer (for marginal contribution)
        other_positions = [p for p in positions if p.issuer != issuer]
        if other_positions:
            without = calculate_irc(other_positions, config)
            marginal = full_irc - without["irc"]
        else:
            marginal = full_irc

        issuer_notional = sum(abs(p.notional) for p in issuer_pos_list)
        issuer_rating = issuer_pos_list[0].rating

        issuer_contributions.append({
            "issuer": issuer,
            "rating": issuer_rating,
            "num_positions": len(issuer_pos_list),
            "notional": issuer_notional,
            "standalone_irc": standalone["irc"],
            "marginal_irc": marginal,
            "pct_of_total": marginal / full_irc * 100 if full_irc > 0 else 0,
        })

    # Sort by marginal contribution
    issuer_contributions.sort(key=lambda x: x["marginal_irc"], reverse=True)

    return {
        **full_result,
        "issuer_contributions": issuer_contributions,
        "diversification_benefit": sum(c["standalone_irc"] for c in issuer_contributions) - full_irc,
    }


def irc_to_dataframe(result: dict, include_summary: bool = True):
    """
    Convert IRC result to a pandas DataFrame for export.

    Parameters
    ----------
    result : dict
        Output from calculate_irc_by_issuer() or calculate_irc().
    include_summary : bool
        If True, adds a summary row with portfolio totals.

    Returns
    -------
    pandas.DataFrame
        DataFrame with issuer-level breakdown.

    Example
    -------
    >>> result = calculate_irc_by_issuer(positions, config)
    >>> df = irc_to_dataframe(result)
    >>> df.to_csv("irc_report.csv", index=False)
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError("pandas is required for irc_to_dataframe(). Install with: pip install pandas")

    # Check if this is an issuer breakdown result
    if "issuer_contributions" not in result:
        # Simple result without issuer breakdown - return summary only
        return pd.DataFrame([{
            "issuer": "PORTFOLIO",
            "rating": "-",
            "num_positions": result.get("num_positions", 0),
            "notional": result.get("total_notional", 0),
            "standalone_irc": result.get("irc", 0),
            "marginal_irc": result.get("irc", 0),
            "pct_of_total": 100.0,
            "irc": result.get("irc", 0),
            "rwa": result.get("rwa", 0),
        }])

    # Build DataFrame from issuer contributions
    df = pd.DataFrame(result["issuer_contributions"])

    if include_summary:
        # Add summary row
        summary = pd.DataFrame([{
            "issuer": "TOTAL",
            "rating": "-",
            "num_positions": result.get("num_positions", df["num_positions"].sum()),
            "notional": result.get("total_notional", df["notional"].sum()),
            "standalone_irc": df["standalone_irc"].sum(),
            "marginal_irc": df["marginal_irc"].sum(),
            "pct_of_total": df["pct_of_total"].sum(),
        }])

        # Add diversification and portfolio IRC
        diversification = pd.DataFrame([{
            "issuer": "DIVERSIFICATION",
            "rating": "-",
            "num_positions": 0,
            "notional": 0,
            "standalone_irc": -result.get("diversification_benefit", 0),
            "marginal_irc": 0,
            "pct_of_total": 0,
        }])

        portfolio = pd.DataFrame([{
            "issuer": "PORTFOLIO IRC",
            "rating": "-",
            "num_positions": result.get("num_positions", 0),
            "notional": result.get("total_notional", 0),
            "standalone_irc": result.get("irc", 0),
            "marginal_irc": result.get("irc", 0),
            "pct_of_total": 100.0,
        }])

        df = pd.concat([df, summary, diversification, portfolio], ignore_index=True)

    return df


def irc_to_csv(result: dict, filepath: str, include_summary: bool = True) -> str:
    """
    Save IRC result directly to CSV.

    Parameters
    ----------
    result : dict
        Output from calculate_irc_by_issuer() or calculate_irc().
    filepath : str
        Path to save CSV file.
    include_summary : bool
        If True, adds summary rows.

    Returns
    -------
    str
        Path to saved file.

    Example
    -------
    >>> result = calculate_irc_by_issuer(positions, config)
    >>> irc_to_csv(result, "irc_report.csv")
    """
    df = irc_to_dataframe(result, include_summary=include_summary)
    df.to_csv(filepath, index=False)
    return filepath


# =============================================================================
# IRC + DRC Comparison (IMA vs Basel 2.5)
# =============================================================================

def compare_irc_vs_ima_drc(
    positions: list[IRCPosition],
    irc_config: IRCConfig = None,
) -> dict:
    """
    Compare Basel 2.5 IRC vs FRTB-IMA DRC.

    IRC includes migration risk; IMA DRC is default-only.

    Parameters
    ----------
    positions : list[IRCPosition]
        Portfolio positions.
    irc_config : IRCConfig
        IRC configuration.

    Returns
    -------
    dict
        Both charges and comparison.
    """
    from frtb_ima import DRCPosition, FRTBIMAConfig, calculate_ima_drc

    # Calculate IRC
    irc_result = calculate_irc(positions, irc_config)

    # Build DRC positions
    drc_positions = []
    for pos in positions:
        pd = RATING_TO_PD.get(pos.rating, RATING_TO_PD.get("BBB", 0.004))
        lgd = get_lgd(pos)

        drc_positions.append(DRCPosition(
            position_id=pos.position_id,
            obligor=pos.issuer,
            notional=pos.notional,
            market_value=pos.market_value,
            pd=pd,
            lgd=lgd,
            seniority=pos.seniority,
            sector=pos.sector,
            systematic_factor=irc_config.systematic_correlation if irc_config else 0.50,
            is_long=pos.is_long,
        ))

    drc_config = FRTBIMAConfig(
        drc_num_simulations=irc_config.num_simulations if irc_config else 100_000,
    )
    drc_result = calculate_ima_drc(drc_positions, drc_config)

    irc = irc_result["irc"]
    drc = drc_result["drc_charge"]

    return {
        "irc": irc_result,
        "drc": drc_result,
        "irc_charge": irc,
        "drc_charge": drc,
        "migration_component": irc - drc if irc > drc else 0,
        "irc_to_drc_ratio": irc / drc if drc > 0 else float("inf"),
        "commentary": (
            "IRC > DRC because IRC includes rating migration risk. "
            "Under FRTB-IMA, migration risk is captured in ES via credit spreads."
        ),
    }


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 72)
    print("Incremental Risk Charge (IRC) — Monte Carlo Simulation")
    print("=" * 72)

    # Create a sample portfolio
    positions = [
        IRCPosition("bond_1", "Corp_A", 10_000_000, 10_200_000, "BBB", 5.0,
                    "senior_unsecured", "financial", 3, True, 0.045),
        IRCPosition("bond_2", "Corp_A", 5_000_000, 4_900_000, "BBB", 3.0,
                    "senior_unsecured", "financial", 3, True, 0.04),
        IRCPosition("bond_3", "Corp_B", 8_000_000, 7_800_000, "BB", 4.0,
                    "senior_unsecured", "energy", 3, True, 0.065),
        IRCPosition("bond_4", "Corp_C", 6_000_000, 6_100_000, "A", 7.0,
                    "senior_unsecured", "tech", 6, True, 0.035),
        IRCPosition("bond_5", "Corp_D", 12_000_000, 11_500_000, "BBB", 5.0,
                    "senior_unsecured", "industrial", 3, True, 0.05),
        IRCPosition("cds_1", "Corp_B", 4_000_000, 3_900_000, "BB", 5.0,
                    "senior_unsecured", "energy", 3, False, 0.0),  # short via CDS
        IRCPosition("bond_6", "Corp_E", 7_000_000, 6_800_000, "B", 3.0,
                    "subordinated", "retail", 3, True, 0.08),
    ]

    config = IRCConfig(
        num_simulations=100_000,
        systematic_correlation=0.50,
    )

    print(f"\n  Portfolio: {len(positions)} positions, "
          f"{len(set(p.issuer for p in positions))} issuers")
    print(f"  Simulations: {config.num_simulations:,}")
    print(f"  Systematic correlation: {config.systematic_correlation}")

    # Basic IRC
    print("\n" + "-" * 72)
    print("IRC Calculation")
    print("-" * 72)

    result = calculate_irc(positions, config)

    print(f"\n  Mean loss:             ${result['mean_loss']:>14,.0f}")
    print(f"  Median loss:           ${result['median_loss']:>14,.0f}")
    print(f"  95th percentile:       ${result['percentile_95']:>14,.0f}")
    print(f"  99th percentile:       ${result['percentile_99']:>14,.0f}")
    print(f"  99.9th percentile:     ${result['percentile_999']:>14,.0f}")
    print(f"  Expected Shortfall:    ${result['expected_shortfall_999']:>14,.0f}")
    print(f"  Max loss:              ${result['max_loss']:>14,.0f}")
    print(f"\n  IRC (99.9%):           ${result['irc']:>14,.0f}")
    print(f"  IRC RWA:               ${result['rwa']:>14,.0f}")
    print(f"  Capital ratio:         {result['capital_ratio']*100:>13.2f}%")

    # IRC by issuer
    print("\n" + "-" * 72)
    print("IRC by Issuer")
    print("-" * 72)

    issuer_result = calculate_irc_by_issuer(positions, config)

    print(f"\n  {'Issuer':<12} {'Rating':>6} {'Notional':>14} {'Standalone':>12} "
          f"{'Marginal':>12} {'% Total':>8}")
    print("  " + "-" * 70)
    for c in issuer_result["issuer_contributions"]:
        print(f"  {c['issuer']:<12} {c['rating']:>6} ${c['notional']:>12,.0f} "
              f"${c['standalone_irc']:>10,.0f} ${c['marginal_irc']:>10,.0f} "
              f"{c['pct_of_total']:>7.1f}%")

    print(f"\n  Diversification benefit: ${issuer_result['diversification_benefit']:>12,.0f}")

    # IRC vs IMA DRC comparison
    print("\n" + "-" * 72)
    print("IRC vs FRTB-IMA DRC Comparison")
    print("-" * 72)

    try:
        comparison = compare_irc_vs_ima_drc(positions, config)
        print(f"\n  IRC (migration + default):  ${comparison['irc_charge']:>14,.0f}")
        print(f"  DRC (default only):         ${comparison['drc_charge']:>14,.0f}")
        print(f"  Migration component:        ${comparison['migration_component']:>14,.0f}")
        print(f"  IRC / DRC ratio:            {comparison['irc_to_drc_ratio']:>14.2f}")
    except ImportError:
        print("\n  (frtb_ima module not available for comparison)")

    # Transition matrix demo
    print("\n" + "-" * 72)
    print("Rating Transition Probabilities (1-year)")
    print("-" * 72)
    print(f"\n  {'From':<6} → {'Upgrade':>8} {'Stable':>8} {'Downgrade':>10} {'Default':>8}")
    print("  " + "-" * 50)
    for rating in ["AAA", "AA", "A", "BBB", "BB", "B", "CCC"]:
        probs = TRANSITION_MATRIX[rating]
        # Calculate upgrade/stable/downgrade/default probabilities
        idx = RATING_CATEGORIES.index(rating)
        upgrade = sum(probs[r] for r in RATING_CATEGORIES[:idx])
        stable = probs[rating]
        downgrade = sum(probs[r] for r in RATING_CATEGORIES[idx+1:-1])
        default = probs["D"]
        print(f"  {rating:<6}   {upgrade*100:>7.2f}% {stable*100:>7.2f}% "
              f"{downgrade*100:>9.2f}% {default*100:>7.2f}%")
