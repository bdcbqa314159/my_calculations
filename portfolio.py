"""
Unified Portfolio Module

A single portfolio object that can be used across different risk calculations:
- VaR and ES (market risk)
- IRC (credit migration risk)
- Credit RWA (regulatory capital)

Usage:
    from portfolio import Portfolio

    # Create portfolio
    port = Portfolio(name="Trading Book", reference_ccy="USD")

    # Add positions
    port.add("Apple", notional=10_000_000, rating="AA", tenor_years=5.0)
    port.add("Ford", notional=5_000_000, rating="BB", tenor_years=3.0, sector="auto")

    # Calculate different risk measures
    var_result = port.var(confidence=0.99)
    irc_result = port.irc()
    summary = port.risk_summary()
"""

import math
from dataclasses import dataclass, field
from typing import Union, Optional, List
from datetime import date, datetime

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# =============================================================================
# Position Dataclass
# =============================================================================

@dataclass
class Position:
    """A single portfolio position."""
    position_id: str
    issuer: str
    notional: float
    market_value: float = None
    rating: str = None
    pd: float = None
    tenor_years: float = None
    maturity_date: date = None
    seniority: str = "senior_unsecured"
    lgd: float = None
    sector: str = "corporate"
    region: str = "US"
    ccy: str = "USD"
    is_long: bool = True
    asset_class: str = "credit"  # credit, equity, fx, rates, commodity
    volatility: float = None     # for VaR
    returns: list = None         # historical returns for VaR
    coupon_rate: float = 0.05
    liquidity_horizon_months: int = 3

    def __post_init__(self):
        if self.market_value is None:
            self.market_value = self.notional


# =============================================================================
# Portfolio Class
# =============================================================================

class Portfolio:
    """
    Unified portfolio for multiple risk calculations.

    Supports:
    - VaR and ES (parametric, historical, Monte Carlo)
    - IRC (Incremental Risk Charge)
    - Credit RWA
    - Risk summary across measures

    Example
    -------
    >>> from portfolio import Portfolio
    >>>
    >>> # Create portfolio
    >>> port = Portfolio("Trading Book", reference_ccy="USD")
    >>>
    >>> # Add positions
    >>> port.add("Apple", notional=10_000_000, rating="AA", tenor_years=5.0)
    >>> port.add("Microsoft", notional=15_000_000, rating="AAA", tenor_years=7.0)
    >>> port.add("Ford", notional=5_000_000, rating="BB", tenor_years=3.0, sector="auto")
    >>>
    >>> # View portfolio
    >>> port.show()
    >>>
    >>> # Calculate risks
    >>> print(port.var(confidence=0.99))
    >>> print(port.irc())
    >>> print(port.risk_summary())
    """

    def __init__(
        self,
        name: str = "Portfolio",
        reference_ccy: str = "USD",
        as_of_date: Union[str, date] = None,
    ):
        """
        Initialize portfolio.

        Parameters
        ----------
        name : str
            Portfolio name.
        reference_ccy : str
            Reference currency for reporting.
        as_of_date : str or date
            As-of date for calculations.
        """
        self.name = name
        self.reference_ccy = reference_ccy
        self.as_of_date = self._parse_date(as_of_date) or date.today()
        self.positions: List[Position] = []
        self._position_counter = 0

        # Cache for returns matrix (for VaR)
        self._returns_matrix = None
        self._weights = None

    def _parse_date(self, d) -> Optional[date]:
        """Parse date from various formats."""
        if d is None:
            return None
        if isinstance(d, date):
            return d
        if isinstance(d, datetime):
            return d.date()
        if isinstance(d, str):
            return datetime.strptime(d, "%Y-%m-%d").date()
        return None

    # =========================================================================
    # Add Positions
    # =========================================================================

    def add(
        self,
        issuer: str,
        notional: float,
        rating: str = None,
        pd: float = None,
        tenor_years: float = None,
        maturity_date: Union[str, date] = None,
        market_value: float = None,
        seniority: str = "senior_unsecured",
        lgd: float = None,
        sector: str = "corporate",
        region: str = "US",
        ccy: str = None,
        is_long: bool = True,
        asset_class: str = "credit",
        volatility: float = None,
        returns: list = None,
        position_id: str = None,
        **kwargs,
    ) -> "Portfolio":
        """
        Add a position to the portfolio.

        Parameters
        ----------
        issuer : str
            Issuer/obligor name.
        notional : float
            Notional amount.
        rating : str, optional
            Credit rating (AAA, AA, A, BBB, BB, B, CCC).
        pd : float, optional
            Probability of default (alternative to rating).
        tenor_years : float, optional
            Time to maturity in years.
        maturity_date : str or date, optional
            Maturity date (alternative to tenor_years).
        market_value : float, optional
            Current market value (defaults to notional).
        seniority : str
            senior_secured, senior_unsecured, subordinated.
        lgd : float, optional
            Loss given default (0-1).
        sector : str
            Sector (corporate, financial, sovereign, etc.).
        region : str
            Region (US, EU, EM, ASIA, etc.).
        ccy : str, optional
            Currency (defaults to reference_ccy).
        is_long : bool
            True for long, False for short.
        asset_class : str
            credit, equity, fx, rates, commodity.
        volatility : float, optional
            Annual volatility for VaR.
        returns : list, optional
            Historical returns for VaR.
        position_id : str, optional
            Position identifier.

        Returns
        -------
        Portfolio
            Self for method chaining.
        """
        self._position_counter += 1
        pos_id = position_id or f"pos_{self._position_counter}"

        # Calculate tenor from maturity date if needed
        if tenor_years is None and maturity_date is not None:
            mat_date = self._parse_date(maturity_date)
            if mat_date:
                days = (mat_date - self.as_of_date).days
                tenor_years = max(days / 365.25, 0.01)

        pos = Position(
            position_id=pos_id,
            issuer=issuer,
            notional=abs(notional),
            market_value=market_value,
            rating=rating,
            pd=pd,
            tenor_years=tenor_years,
            maturity_date=self._parse_date(maturity_date),
            seniority=seniority,
            lgd=lgd,
            sector=sector,
            region=region,
            ccy=ccy or self.reference_ccy,
            is_long=is_long,
            asset_class=asset_class,
            volatility=volatility,
            returns=returns,
        )

        self.positions.append(pos)
        self._returns_matrix = None  # Invalidate cache

        return self

    def add_from_df(self, df: "pd.DataFrame", **kwargs) -> "Portfolio":
        """
        Add positions from a DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame with position data.
        **kwargs
            Additional arguments passed to prepare_irc_data.

        Returns
        -------
        Portfolio
            Self for method chaining.
        """
        if not HAS_PANDAS:
            raise ImportError("pandas required for add_from_df")

        from irc_data_prep import prepare_irc_data

        clean_df = prepare_irc_data(
            df,
            as_of_date=self.as_of_date,
            reference_ccy=self.reference_ccy,
            **kwargs
        )

        for _, row in clean_df.iterrows():
            self.add(
                issuer=row.get("issuer"),
                notional=row.get("notional"),
                rating=row.get("rating"),
                pd=row.get("pd"),
                tenor_years=row.get("tenor_years"),
                market_value=row.get("market_value"),
                seniority=row.get("seniority", "senior_unsecured"),
                lgd=row.get("lgd"),
                sector=row.get("sector", "corporate"),
                region=row.get("region", "US"),
                ccy=row.get("ccy", self.reference_ccy),
                is_long=row.get("is_long", True),
            )

        return self

    def add_from_csv(self, filepath: str, **kwargs) -> "Portfolio":
        """
        Add positions from a CSV file.

        Parameters
        ----------
        filepath : str
            Path to CSV file.
        **kwargs
            Additional arguments passed to prepare_irc_data.

        Returns
        -------
        Portfolio
            Self for method chaining.
        """
        if not HAS_PANDAS:
            raise ImportError("pandas required for add_from_csv")

        df = pd.read_csv(filepath)
        return self.add_from_df(df, **kwargs)

    def clear(self) -> "Portfolio":
        """Clear all positions."""
        self.positions = []
        self._position_counter = 0
        self._returns_matrix = None
        return self

    # =========================================================================
    # Portfolio Info
    # =========================================================================

    def __len__(self) -> int:
        return len(self.positions)

    def __repr__(self) -> str:
        return f"Portfolio('{self.name}', {len(self)} positions, {self.reference_ccy})"

    @property
    def total_notional(self) -> float:
        """Total notional across all positions."""
        return sum(p.notional for p in self.positions)

    @property
    def total_market_value(self) -> float:
        """Total market value across all positions."""
        return sum(p.market_value for p in self.positions)

    @property
    def num_issuers(self) -> int:
        """Number of unique issuers."""
        return len(set(p.issuer for p in self.positions))

    def show(self) -> None:
        """Display portfolio summary."""
        print(f"\n{'='*70}")
        print(f"PORTFOLIO: {self.name}")
        print(f"{'='*70}")
        print(f"  As-of date:      {self.as_of_date}")
        print(f"  Reference CCY:   {self.reference_ccy}")
        print(f"  Positions:       {len(self)}")
        print(f"  Issuers:         {self.num_issuers}")
        print(f"  Total notional:  {self.total_notional:,.0f}")
        print(f"  Total MV:        {self.total_market_value:,.0f}")

        if self.positions:
            print(f"\n  {'Issuer':<20} {'Rating':>6} {'Tenor':>6} {'Notional':>14} {'Sector':>12}")
            print(f"  {'-'*62}")
            for p in self.positions[:15]:
                rating = p.rating or "N/A"
                tenor = f"{p.tenor_years:.1f}y" if p.tenor_years else "N/A"
                print(f"  {p.issuer[:20]:<20} {rating:>6} {tenor:>6} {p.notional:>14,.0f} {p.sector:>12}")
            if len(self.positions) > 15:
                print(f"  ... and {len(self.positions) - 15} more positions")

        print(f"{'='*70}\n")

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert portfolio to DataFrame."""
        if not HAS_PANDAS:
            raise ImportError("pandas required for to_dataframe")

        data = []
        for p in self.positions:
            data.append({
                "position_id": p.position_id,
                "issuer": p.issuer,
                "notional": p.notional,
                "market_value": p.market_value,
                "rating": p.rating,
                "pd": p.pd,
                "tenor_years": p.tenor_years,
                "seniority": p.seniority,
                "lgd": p.lgd,
                "sector": p.sector,
                "region": p.region,
                "ccy": p.ccy,
                "is_long": p.is_long,
                "asset_class": p.asset_class,
            })
        return pd.DataFrame(data)

    # =========================================================================
    # IRC Calculation
    # =========================================================================

    def irc(
        self,
        num_simulations: int = 100_000,
        correlation: float = 0.50,
        matrix_by_region: dict = None,
        matrix_by_sector: dict = None,
    ) -> dict:
        """
        Calculate Incremental Risk Charge.

        Parameters
        ----------
        num_simulations : int
            Number of Monte Carlo simulations.
        correlation : float
            Systematic correlation.
        matrix_by_region : dict, optional
            Region to transition matrix mapping.
        matrix_by_sector : dict, optional
            Sector to transition matrix mapping.

        Returns
        -------
        dict
            IRC results.
        """
        from irc import quick_irc

        # Default mappings
        if matrix_by_region is None:
            matrix_by_region = {
                "US": "global",
                "EU": "europe",
                "EM": "emerging_markets",
                "ASIA": "global",
            }

        if matrix_by_sector is None:
            matrix_by_sector = {
                "financial": "financials",
                "financials": "financials",
                "sovereign": "sovereign",
            }

        # Build positions list
        positions = []
        for p in self.positions:
            positions.append({
                "position_id": p.position_id,
                "issuer": p.issuer,
                "notional": p.notional,
                "market_value": p.market_value,
                "rating": p.rating,
                "pd": p.pd,
                "tenor_years": p.tenor_years or 1.0,
                "seniority": p.seniority,
                "lgd": p.lgd,
                "sector": p.sector,
                "region": p.region,
                "is_long": p.is_long,
                "liquidity_horizon_months": p.liquidity_horizon_months,
                "coupon_rate": p.coupon_rate,
            })

        return quick_irc(
            positions,
            num_simulations=num_simulations,
            correlation=correlation,
            matrix_by_region=matrix_by_region,
            matrix_by_sector=matrix_by_sector,
        )

    def irc_by_issuer(self, num_simulations: int = 100_000) -> dict:
        """Calculate IRC with issuer breakdown."""
        from irc import calculate_irc_by_issuer, IRCPosition, IRCConfig

        irc_positions = []
        for p in self.positions:
            irc_positions.append(IRCPosition(
                position_id=p.position_id,
                issuer=p.issuer,
                notional=p.notional,
                market_value=p.market_value,
                rating=p.rating or "B",
                tenor_years=p.tenor_years or 1.0,
                seniority=p.seniority,
                sector=p.sector,
                liquidity_horizon_months=p.liquidity_horizon_months,
                is_long=p.is_long,
                coupon_rate=p.coupon_rate,
                lgd=p.lgd,
            ))

        config = IRCConfig(num_simulations=num_simulations)
        return calculate_irc_by_issuer(irc_positions, config)

    # =========================================================================
    # VaR Calculation
    # =========================================================================

    def var(
        self,
        confidence: float = 0.99,
        horizon_days: int = 1,
        method: str = "parametric",
    ) -> dict:
        """
        Calculate portfolio VaR.

        Parameters
        ----------
        confidence : float
            Confidence level (0.95, 0.99, 0.999).
        horizon_days : int
            Holding period in days.
        method : str
            "parametric", "historical", or "monte_carlo".

        Returns
        -------
        dict
            VaR results.
        """
        from var import quick_var, portfolio_var

        # Check if we have returns data
        positions_with_returns = [p for p in self.positions if p.returns is not None]

        if positions_with_returns:
            # Use returns-based VaR
            if len(positions_with_returns) == len(self.positions):
                # All positions have returns - do portfolio VaR
                returns_matrix = np.array([p.returns for p in self.positions]).T
                weights = np.array([p.market_value for p in self.positions])
                weights = weights / weights.sum()

                return portfolio_var(
                    weights,
                    returns_matrix,
                    confidence=confidence,
                    horizon_days=horizon_days,
                    method=method,
                    position_value=self.total_market_value,
                )
            else:
                # Some positions have returns
                all_returns = []
                for p in positions_with_returns:
                    all_returns.extend(p.returns)
                returns = np.array(all_returns)
                return quick_var(
                    returns,
                    confidence=confidence,
                    horizon_days=horizon_days,
                    method=method,
                    position_value=self.total_market_value,
                )

        # Estimate from volatilities
        positions_with_vol = [p for p in self.positions if p.volatility is not None]

        if positions_with_vol:
            # Use volatility-based parametric VaR
            total_mv = sum(p.market_value for p in positions_with_vol)
            weighted_var_sq = 0

            for p in positions_with_vol:
                weight = p.market_value / total_mv
                daily_vol = p.volatility / math.sqrt(252)
                weighted_var_sq += (weight * daily_vol) ** 2

            portfolio_vol = math.sqrt(weighted_var_sq)

            from var import monte_carlo_var
            return monte_carlo_var(
                mean_return=0,
                volatility=portfolio_vol,
                confidence=confidence,
                horizon_days=horizon_days,
                position_value=total_mv,
            )

        # Default: estimate volatility from rating
        # Higher rated = lower vol, lower rated = higher vol
        RATING_VOL = {
            "AAA": 0.05, "AA": 0.08, "A": 0.12,
            "BBB": 0.18, "BB": 0.25, "B": 0.35, "CCC": 0.50,
        }

        total_mv = self.total_market_value
        weighted_vol_sq = 0

        for p in self.positions:
            weight = p.market_value / total_mv
            vol = RATING_VOL.get(p.rating, 0.20)
            weighted_vol_sq += (weight * vol) ** 2

        portfolio_vol = math.sqrt(weighted_vol_sq) / math.sqrt(252)

        from var import monte_carlo_var
        return monte_carlo_var(
            mean_return=0,
            volatility=portfolio_vol,
            confidence=confidence,
            horizon_days=horizon_days,
            position_value=total_mv,
        )

    def es(self, confidence: float = 0.99, horizon_days: int = 1) -> dict:
        """
        Calculate Expected Shortfall (CVaR).

        Parameters
        ----------
        confidence : float
            Confidence level.
        horizon_days : int
            Holding period.

        Returns
        -------
        dict
            ES results (uses VaR calculation which includes ES).
        """
        result = self.var(confidence=confidence, horizon_days=horizon_days)
        return {
            "es_pct": result.get("es_pct"),
            "es_abs": result.get("es_abs"),
            "confidence": confidence,
            "horizon_days": horizon_days,
        }

    # =========================================================================
    # Risk Summary
    # =========================================================================

    def risk_summary(
        self,
        var_confidence: float = 0.99,
        var_horizon: int = 10,
        irc_simulations: int = 50_000,
    ) -> dict:
        """
        Calculate comprehensive risk summary.

        Parameters
        ----------
        var_confidence : float
            VaR confidence level.
        var_horizon : int
            VaR holding period.
        irc_simulations : int
            IRC Monte Carlo simulations.

        Returns
        -------
        dict
            Comprehensive risk summary.
        """
        summary = {
            "portfolio_name": self.name,
            "as_of_date": str(self.as_of_date),
            "reference_ccy": self.reference_ccy,
            "num_positions": len(self.positions),
            "num_issuers": self.num_issuers,
            "total_notional": self.total_notional,
            "total_market_value": self.total_market_value,
        }

        # VaR
        try:
            var_result = self.var(
                confidence=var_confidence,
                horizon_days=var_horizon,
            )
            summary["var"] = {
                "confidence": var_confidence,
                "horizon_days": var_horizon,
                "var_pct": var_result.get("var_pct"),
                "var_abs": var_result.get("var_abs"),
                "es_pct": var_result.get("es_pct"),
                "es_abs": var_result.get("es_abs"),
            }
        except Exception as e:
            summary["var"] = {"error": str(e)}

        # IRC
        try:
            irc_result = self.irc(num_simulations=irc_simulations)
            summary["irc"] = {
                "irc": irc_result.get("irc"),
                "rwa": irc_result.get("rwa"),
                "capital_ratio": irc_result.get("capital_ratio"),
                "mean_loss": irc_result.get("mean_loss"),
                "percentile_999": irc_result.get("percentile_999"),
                "expected_shortfall_999": irc_result.get("expected_shortfall_999"),
            }
        except Exception as e:
            summary["irc"] = {"error": str(e)}

        return summary

    def print_risk_summary(self, **kwargs) -> None:
        """Print formatted risk summary."""
        summary = self.risk_summary(**kwargs)

        print(f"\n{'='*70}")
        print(f"RISK SUMMARY: {summary['portfolio_name']}")
        print(f"{'='*70}")
        print(f"  As-of date:      {summary['as_of_date']}")
        print(f"  Reference CCY:   {summary['reference_ccy']}")
        print(f"  Positions:       {summary['num_positions']}")
        print(f"  Issuers:         {summary['num_issuers']}")
        print(f"  Total notional:  {summary['total_notional']:,.0f}")
        print(f"  Total MV:        {summary['total_market_value']:,.0f}")

        if "var" in summary and "error" not in summary["var"]:
            var = summary["var"]
            print(f"\n  VaR ({var['confidence']:.0%}, {var['horizon_days']}-day):")
            if var.get("var_abs"):
                print(f"    VaR:           {var['var_abs']:,.0f}")
            if var.get("es_abs"):
                print(f"    ES:            {var['es_abs']:,.0f}")

        if "irc" in summary and "error" not in summary["irc"]:
            irc = summary["irc"]
            print(f"\n  IRC (99.9%, 1-year):")
            print(f"    IRC:           {irc['irc']:,.0f}")
            print(f"    RWA:           {irc['rwa']:,.0f}")
            print(f"    Capital ratio: {irc['capital_ratio']*100:.2f}%")

        print(f"{'='*70}\n")


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("UNIFIED PORTFOLIO DEMO")
    print("=" * 70)

    # Create portfolio
    port = Portfolio("Sample Trading Book", reference_ccy="USD")

    # Add positions
    port.add("Apple Inc", notional=20_000_000, rating="AA", tenor_years=5.0, sector="tech", region="US")
    port.add("Microsoft", notional=15_000_000, rating="AAA", tenor_years=7.0, sector="tech", region="US")
    port.add("Ford Motor", notional=10_000_000, rating="BB", tenor_years=3.0, sector="auto", region="US")
    port.add("BMW AG", notional=12_000_000, rating="A", tenor_years=4.0, sector="auto", region="EU")
    port.add("Deutsche Bank", notional=18_000_000, rating="BBB", tenor_years=5.0, sector="financial", region="EU")
    port.add("Petrobras", notional=8_000_000, rating="BB", tenor_years=3.5, sector="energy", region="EM")
    port.add("Toyota", notional=15_000_000, rating="A", tenor_years=6.0, sector="auto", region="ASIA")

    # Show portfolio
    port.show()

    # Calculate IRC
    print("-" * 70)
    print("IRC CALCULATION")
    print("-" * 70)
    irc_result = port.irc(num_simulations=50_000)
    print(f"  IRC (99.9%):         ${irc_result['irc']:>14,.0f}")
    print(f"  IRC RWA:             ${irc_result['rwa']:>14,.0f}")
    print(f"  Capital ratio:       {irc_result['capital_ratio']*100:>13.2f}%")
    print(f"  Mean loss:           ${irc_result['mean_loss']:>14,.0f}")

    # Calculate VaR
    print("\n" + "-" * 70)
    print("VaR CALCULATION")
    print("-" * 70)
    var_result = port.var(confidence=0.99, horizon_days=10)
    print(f"  VaR (99%, 10-day):   ${var_result.get('var_abs', 0):>14,.0f}")
    print(f"  ES (99%, 10-day):    ${var_result.get('es_abs', 0):>14,.0f}")

    # Full risk summary
    print("\n" + "-" * 70)
    print("FULL RISK SUMMARY")
    print("-" * 70)
    port.print_risk_summary()

    # Show issuer breakdown
    print("-" * 70)
    print("IRC ISSUER BREAKDOWN")
    print("-" * 70)
    issuer_result = port.irc_by_issuer(num_simulations=50_000)
    print(f"\n  {'Issuer':<20} {'Rating':>6} {'Notional':>12} {'Marginal IRC':>14}")
    print(f"  {'-'*55}")
    for c in issuer_result["issuer_contributions"]:
        print(f"  {c['issuer'][:20]:<20} {c['rating']:>6} ${c['notional']:>10,.0f} ${c['marginal_irc']:>12,.0f}")

    print(f"\n  Diversification benefit: ${issuer_result['diversification_benefit']:,.0f}")
    print(f"  Portfolio IRC:           ${issuer_result['irc']:,.0f}")

    print("\n" + "=" * 70)
    print("END OF DEMO")
    print("=" * 70)
