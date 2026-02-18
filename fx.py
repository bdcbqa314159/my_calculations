"""
FX Module — Currency Conversion with Standard Market Conventions

Handles FX rate quoting conventions and conversions.

Standard market conventions:
    EURUSD = 1.08  →  1 EUR = 1.08 USD  (EUR is base)
    GBPUSD = 1.27  →  1 GBP = 1.27 USD  (GBP is base)
    USDJPY = 150   →  1 USD = 150 JPY   (USD is base)
    USDCHF = 0.88  →  1 USD = 0.88 CHF  (USD is base)

Usage:
    from fx import FXRates

    fx = FXRates()
    fx.set_spot("EURUSD", 1.08)
    fx.set_spot("USDJPY", 150.0)

    # Convert 1M EUR to USD
    usd_amount = fx.convert(1_000_000, "EUR", "USD")  # 1,080,000

    # Convert 100M JPY to EUR
    eur_amount = fx.convert(100_000_000, "JPY", "EUR")  # ~617,284
"""

from dataclasses import dataclass, field
from typing import Optional


# Standard market convention: which currency is BASE in each pair
# BASE/QUOTE means 1 BASE = X QUOTE
MARKET_CONVENTION = {
    # EUR is always base
    "EURUSD": ("EUR", "USD"),
    "EURGBP": ("EUR", "GBP"),
    "EURJPY": ("EUR", "JPY"),
    "EURCHF": ("EUR", "CHF"),
    "EURCAD": ("EUR", "CAD"),
    "EURAUD": ("EUR", "AUD"),
    "EURNZD": ("EUR", "NZD"),
    "EURCNY": ("EUR", "CNY"),
    "EURHKD": ("EUR", "HKD"),
    "EURSGD": ("EUR", "SGD"),
    "EURKRW": ("EUR", "KRW"),
    "EURINR": ("EUR", "INR"),
    "EURBRL": ("EUR", "BRL"),
    "EURMXN": ("EUR", "MXN"),
    "EURZAR": ("EUR", "ZAR"),
    # GBP is base against USD
    "GBPUSD": ("GBP", "USD"),
    "GBPJPY": ("GBP", "JPY"),
    "GBPCHF": ("GBP", "CHF"),
    # AUD, NZD are base against USD
    "AUDUSD": ("AUD", "USD"),
    "NZDUSD": ("NZD", "USD"),
    # USD is base against others
    "USDJPY": ("USD", "JPY"),
    "USDCHF": ("USD", "CHF"),
    "USDCAD": ("USD", "CAD"),
    "USDCNY": ("USD", "CNY"),
    "USDHKD": ("USD", "HKD"),
    "USDSGD": ("USD", "SGD"),
    "USDKRW": ("USD", "KRW"),
    "USDINR": ("USD", "INR"),
    "USDBRL": ("USD", "BRL"),
    "USDMXN": ("USD", "MXN"),
    "USDZAR": ("USD", "ZAR"),
}


@dataclass
class FXRates:
    """
    FX rate store with automatic convention handling.

    Stores rates in standard market convention and handles
    conversions automatically (multiply vs divide).
    """

    # Internal storage: pair -> rate (in market convention)
    _rates: dict = field(default_factory=dict)

    def set_spot(self, pair: str, rate: float) -> None:
        """
        Set an FX spot rate.

        Parameters
        ----------
        pair : str
            Currency pair (e.g., "EURUSD", "USDJPY").
            Can also use "/" format: "EUR/USD".
        rate : float
            The spot rate in market convention.

        Examples
        --------
        >>> fx.set_spot("EURUSD", 1.08)   # 1 EUR = 1.08 USD
        >>> fx.set_spot("USDJPY", 150.0)  # 1 USD = 150 JPY
        """
        pair = self._normalize_pair(pair)
        self._rates[pair] = rate

    def get_spot(self, pair: str) -> Optional[float]:
        """Get the spot rate for a pair."""
        pair = self._normalize_pair(pair)
        return self._rates.get(pair)

    def set_rates(self, rates: dict) -> None:
        """
        Set multiple rates at once.

        Parameters
        ----------
        rates : dict
            Dictionary of pair -> rate.

        Examples
        --------
        >>> fx.set_rates({
        ...     "EURUSD": 1.08,
        ...     "USDJPY": 150.0,
        ...     "GBPUSD": 1.27,
        ... })
        """
        for pair, rate in rates.items():
            self.set_spot(pair, rate)

    def convert(
        self,
        amount: float,
        from_ccy: str,
        to_ccy: str,
    ) -> float:
        """
        Convert an amount from one currency to another.

        Parameters
        ----------
        amount : float
            The amount to convert.
        from_ccy : str
            Source currency (e.g., "EUR", "USD").
        to_ccy : str
            Target currency.

        Returns
        -------
        float
            Converted amount.

        Raises
        ------
        ValueError
            If no rate is available for the conversion.

        Examples
        --------
        >>> fx.convert(1_000_000, "EUR", "USD")  # 1M EUR -> USD
        1080000.0
        >>> fx.convert(150_000_000, "JPY", "USD")  # 150M JPY -> USD
        1000000.0
        """
        from_ccy = from_ccy.upper()
        to_ccy = to_ccy.upper()

        if from_ccy == to_ccy:
            return amount

        # Try direct pair
        rate = self._get_rate(from_ccy, to_ccy)
        if rate is not None:
            return amount * rate

        # Try triangulation through USD
        if from_ccy != "USD" and to_ccy != "USD":
            rate_from_usd = self._get_rate(from_ccy, "USD")
            rate_to_usd = self._get_rate("USD", to_ccy)
            if rate_from_usd is not None and rate_to_usd is not None:
                return amount * rate_from_usd * rate_to_usd

        # Try triangulation through EUR
        if from_ccy != "EUR" and to_ccy != "EUR":
            rate_from_eur = self._get_rate(from_ccy, "EUR")
            rate_to_eur = self._get_rate("EUR", to_ccy)
            if rate_from_eur is not None and rate_to_eur is not None:
                return amount * rate_from_eur * rate_to_eur

        raise ValueError(
            f"No FX rate available for {from_ccy} -> {to_ccy}. "
            f"Available pairs: {list(self._rates.keys())}"
        )

    def convert_to_reference(
        self,
        amount: float,
        from_ccy: str,
        reference_ccy: str,
    ) -> float:
        """Alias for convert() — converts to a reference currency."""
        return self.convert(amount, from_ccy, reference_ccy)

    def _get_rate(self, from_ccy: str, to_ccy: str) -> Optional[float]:
        """
        Get the conversion rate from one currency to another.

        Handles the multiply/divide logic based on market convention.
        """
        # Try the standard pair order
        pair1 = from_ccy + to_ccy
        pair2 = to_ccy + from_ccy

        if pair1 in self._rates:
            # pair1 is BASE/QUOTE, we have from_ccy as base
            # 1 from_ccy = rate to_ccy, so multiply
            base, quote = self._get_convention(pair1)
            if base == from_ccy:
                return self._rates[pair1]
            else:
                return 1.0 / self._rates[pair1]

        if pair2 in self._rates:
            # pair2 is stored, figure out the direction
            base, quote = self._get_convention(pair2)
            if base == from_ccy:
                # from_ccy is base, rate gives us quote per base
                return self._rates[pair2]
            else:
                # to_ccy is base, rate gives us from_ccy per to_ccy
                # we need to_ccy per from_ccy, so invert
                return 1.0 / self._rates[pair2]

        return None

    def _get_convention(self, pair: str) -> tuple:
        """Get (base, quote) for a pair based on market convention."""
        if pair in MARKET_CONVENTION:
            return MARKET_CONVENTION[pair]
        # Default: first 3 chars are base, last 3 are quote
        return (pair[:3], pair[3:])

    def _normalize_pair(self, pair: str) -> str:
        """Normalize pair format (remove /, uppercase)."""
        return pair.replace("/", "").replace("-", "").upper()

    def __repr__(self) -> str:
        rates_str = ", ".join(f"{k}={v}" for k, v in self._rates.items())
        return f"FXRates({rates_str})"


# =============================================================================
# Convenience: Default rates (approximate, for demo purposes)
# =============================================================================

def get_default_fx_rates(reference_ccy: str = "USD") -> FXRates:
    """
    Get default FX rates for common currencies.

    These are approximate rates for demo/testing purposes.
    In production, use live market data.

    Parameters
    ----------
    reference_ccy : str
        Reference currency (USD or EUR supported).

    Returns
    -------
    FXRates
        Initialized FX rate store.
    """
    fx = FXRates()

    # Set standard market convention rates
    fx.set_rates({
        "EURUSD": 1.08,
        "GBPUSD": 1.27,
        "USDJPY": 150.0,
        "USDCHF": 0.88,
        "USDCAD": 1.35,
        "AUDUSD": 0.65,
        "USDCNY": 7.25,
        "USDHKD": 7.82,
        "USDSGD": 1.35,
        "USDKRW": 1330.0,
        "USDINR": 83.0,
        "USDBRL": 5.00,
        "USDMXN": 17.2,
        "USDZAR": 18.5,
    })

    return fx


def load_fx_rates_from_dict(
    rates: dict,
    input_format: str = "to_reference",
    reference_ccy: str = "USD",
) -> FXRates:
    """
    Load FX rates from a simple dictionary.

    Parameters
    ----------
    rates : dict
        Currency -> rate mapping.
    input_format : str
        How the rates are expressed:
        - "to_reference": 1 foreign = X reference (e.g., {"EUR": 1.08} means 1 EUR = 1.08 USD)
        - "from_reference": 1 reference = X foreign (e.g., {"JPY": 150} means 1 USD = 150 JPY)
        - "market": rates are in standard market convention pairs
    reference_ccy : str
        The reference currency (default USD).

    Returns
    -------
    FXRates
        Initialized FX rate store.

    Examples
    --------
    >>> # Simple format: 1 foreign = X reference
    >>> fx = load_fx_rates_from_dict(
    ...     {"EUR": 1.08, "GBP": 1.27, "JPY": 0.0067},
    ...     input_format="to_reference",
    ...     reference_ccy="USD"
    ... )
    >>> fx.convert(1_000_000, "EUR", "USD")
    1080000.0
    """
    fx = FXRates()

    for ccy, rate in rates.items():
        ccy = ccy.upper()
        ref = reference_ccy.upper()

        if ccy == ref:
            continue

        if input_format == "to_reference":
            # 1 ccy = rate ref
            # Need to figure out the market convention pair
            pair1 = ccy + ref
            pair2 = ref + ccy

            if pair1 in MARKET_CONVENTION:
                base, quote = MARKET_CONVENTION[pair1]
                if base == ccy:
                    # ccy is base, rate is quote per base → store as-is
                    fx.set_spot(pair1, rate)
                else:
                    # ref is base, we have ccy per ref, need to invert
                    fx.set_spot(pair1, 1.0 / rate)
            elif pair2 in MARKET_CONVENTION:
                base, quote = MARKET_CONVENTION[pair2]
                if base == ccy:
                    # ccy is base, rate is ref per ccy → store as-is
                    fx.set_spot(pair2, rate)
                else:
                    # ref is base, store inverted
                    fx.set_spot(pair2, 1.0 / rate)
            else:
                # No convention, store as ccy/ref
                fx.set_spot(pair1, rate)

        elif input_format == "from_reference":
            # 1 ref = rate ccy → 1 ccy = 1/rate ref
            pair1 = ccy + ref
            pair2 = ref + ccy

            if pair2 in MARKET_CONVENTION:
                # ref is base in market convention
                fx.set_spot(pair2, rate)
            elif pair1 in MARKET_CONVENTION:
                fx.set_spot(pair1, 1.0 / rate)
            else:
                fx.set_spot(ref + ccy, rate)

        elif input_format == "market":
            # Already in market convention
            fx.set_spot(ccy, rate)

    return fx


# =============================================================================
# CLI Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("FX Module Demo")
    print("=" * 60)

    # Create FX rate store with market convention rates
    fx = FXRates()
    fx.set_rates({
        "EURUSD": 1.08,
        "GBPUSD": 1.27,
        "USDJPY": 150.0,
        "USDCHF": 0.88,
    })

    print("\nRates (market convention):")
    print(f"  EURUSD = 1.08  (1 EUR = 1.08 USD)")
    print(f"  GBPUSD = 1.27  (1 GBP = 1.27 USD)")
    print(f"  USDJPY = 150   (1 USD = 150 JPY)")
    print(f"  USDCHF = 0.88  (1 USD = 0.88 CHF)")

    print("\nConversions:")
    examples = [
        (1_000_000, "EUR", "USD"),
        (1_000_000, "USD", "EUR"),
        (1_000_000, "GBP", "USD"),
        (150_000_000, "JPY", "USD"),
        (1_000_000, "USD", "JPY"),
        (1_000_000, "EUR", "JPY"),  # triangulation
        (1_000_000, "GBP", "CHF"),  # triangulation
    ]

    for amount, from_ccy, to_ccy in examples:
        result = fx.convert(amount, from_ccy, to_ccy)
        print(f"  {amount:>12,.0f} {from_ccy} -> {result:>15,.2f} {to_ccy}")

    # Demo: loading from simple dict (like current IRC usage)
    print("\n" + "-" * 60)
    print("Loading from simple dict (to_reference format):")
    print("-" * 60)

    simple_rates = {
        "EUR": 1.08,
        "GBP": 1.27,
        "JPY": 0.0067,
        "CHF": 1.12,
    }
    print(f"\nInput: {simple_rates}")
    print("(Meaning: 1 EUR = 1.08 USD, 1 JPY = 0.0067 USD, etc.)")

    fx2 = load_fx_rates_from_dict(simple_rates, "to_reference", "USD")

    print("\nConversions to USD:")
    for ccy, rate in simple_rates.items():
        result = fx2.convert(1_000_000, ccy, "USD")
        print(f"  1,000,000 {ccy} -> {result:>12,.2f} USD")

    print("\n" + "-" * 60)
    print("Loading from simple dict (EUR as reference):")
    print("-" * 60)

    eur_rates = {
        "USD": 0.92,
        "GBP": 1.17,
        "JPY": 0.0062,
    }
    print(f"\nInput: {eur_rates}")
    print("(Meaning: 1 USD = 0.92 EUR, 1 GBP = 1.17 EUR, etc.)")

    fx3 = load_fx_rates_from_dict(eur_rates, "to_reference", "EUR")

    print("\nConversions to EUR:")
    for ccy in eur_rates.keys():
        result = fx3.convert(1_000_000, ccy, "EUR")
        print(f"  1,000,000 {ccy} -> {result:>12,.2f} EUR")

    print("\n" + "=" * 60)
