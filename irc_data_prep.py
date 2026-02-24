"""
IRC Data Preparation Module

Normalizes raw portfolio data into the format required by the IRC module.

Handles:
  - Column name mapping (flexible input column names)
  - Rating conversion (granular → base, PD → rating)
  - TTM calculation from as_of_date and maturity_date
  - Currency conversion to reference currency
  - Default values for optional fields
  - Data validation
  - Type conversion (strings, percentages, booleans)

Usage:
    from irc_data_prep import prepare_irc_data

    # Basic usage
    df_clean = prepare_irc_data(df_raw)

    # With TTM calculation
    df_clean = prepare_irc_data(df_raw, as_of_date="2024-01-15")

    # With currency conversion
    fx_rates = {"EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}
    df_clean = prepare_irc_data(df_raw, reference_ccy="USD", fx_rates=fx_rates)

    # Full example
    df_clean = prepare_irc_data(
        df_raw,
        as_of_date="2024-01-15",
        reference_ccy="USD",
        fx_rates={"EUR": 1.08, "GBP": 1.27},
    )
    result = quick_irc(df_clean.to_dict(orient="records"))
"""

import math
import warnings
from datetime import datetime, date
from typing import Union, Optional

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from irc import resolve_rating, normalize_rating, RATING_CATEGORIES
from fx import FXRates, load_fx_rates_from_dict


# =============================================================================
# Column Name Mapping
# =============================================================================
# Maps common variations of column names to the standard IRC field names.
# Case-insensitive matching is applied.

COLUMN_ALIASES = {
    # Issuer
    "issuer": ["issuer", "issuer_name", "obligor", "obligor_name", "counterparty",
               "entity", "company", "name", "borrower"],

    # Rating
    "rating": ["rating", "credit_rating", "external_rating", "sp_rating",
               "moodys_rating", "fitch_rating", "grade"],

    # PD
    "pd": ["pd", "prob_default", "probability_of_default", "default_probability",
           "annual_pd", "1y_pd", "one_year_pd"],

    # Tenor
    "tenor_years": ["tenor_years", "tenor", "maturity", "maturity_years",
                    "remaining_maturity", "term", "years_to_maturity", "ttm"],

    # Notional
    "notional": ["notional", "notional_amount", "principal", "face_value",
                 "exposure", "amount", "size", "position_size", "nominal"],

    # Market Value
    "market_value": ["market_value", "mv", "mtm", "mark_to_market",
                     "fair_value", "current_value"],

    # LGD
    "lgd": ["lgd", "loss_given_default", "severity", "loss_severity"],

    # Seniority
    "seniority": ["seniority", "rank", "ranking", "debt_type", "tranche"],

    # Sector
    "sector": ["sector", "industry", "industry_sector", "segment"],

    # Region
    "region": ["region", "country", "geography", "geo", "location"],

    # Is Long
    "is_long": ["is_long", "long", "direction", "position_type", "side"],

    # Liquidity Horizon
    "liquidity_horizon_months": ["liquidity_horizon_months", "liquidity_horizon",
                                  "lh", "liq_horizon", "rebalancing_period"],

    # Coupon
    "coupon_rate": ["coupon_rate", "coupon", "interest_rate", "yield"],

    # Position ID
    "position_id": ["position_id", "id", "trade_id", "deal_id", "ref", "reference"],

    # Maturity Date (for TTM calculation)
    "maturity_date": ["maturity_date", "maturity_dt", "mat_date", "expiry",
                      "expiry_date", "end_date", "termination_date"],

    # Currency
    "ccy": ["ccy", "currency", "curr", "notional_ccy", "denomination"],
}


# =============================================================================
# Default Values
# =============================================================================

DEFAULTS = {
    "seniority": "senior_unsecured",
    "sector": "corporate",
    "region": "US",
    "is_long": True,
    "liquidity_horizon_months": 3,
    "coupon_rate": 0.05,
}


# =============================================================================
# Known Sectors
# =============================================================================
# Recognized sector values. Unrecognized sectors trigger a warning.
# Sectors with a dedicated transition matrix are marked with a comment.

KNOWN_SECTORS = {
    # Sectors that map to a specific transition matrix
    "financial",
    "financials",
    "bank",
    "insurance",
    "sovereign",
    "government",
    # General corporate sectors (use default/region-based matrix)
    "corporate",
    "tech",
    "energy",
    "auto",
    "retail",
    "industrial",
    "telecom",
    "healthcare",
    "utilities",
    "real_estate",
    "consumer",
    "media",
    "mining",
    "transportation",
}


# =============================================================================
# Seniority Mapping
# =============================================================================

SENIORITY_ALIASES = {
    "senior_secured": ["senior_secured", "secured", "senior secured", "1st lien",
                       "first lien", "senior_sec"],
    "senior_unsecured": ["senior_unsecured", "unsecured", "senior unsecured",
                         "senior", "sen", "snr", "2nd lien", "second lien"],
    "subordinated": ["subordinated", "sub", "junior", "mezzanine", "mezz",
                     "tier2", "tier 2", "lt2"],
}


def _normalize_seniority(value: str) -> str:
    """Convert seniority aliases to standard values."""
    if value is None:
        return DEFAULTS["seniority"]

    value_lower = str(value).strip().lower()

    for standard, aliases in SENIORITY_ALIASES.items():
        if value_lower in [a.lower() for a in aliases]:
            return standard

    return DEFAULTS["seniority"]


# =============================================================================
# Boolean Conversion
# =============================================================================

def _to_bool(value, default: bool = True) -> bool:
    """Convert various boolean representations to Python bool."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    value_str = str(value).strip().lower()

    if value_str in ("true", "yes", "y", "1", "long", "buy"):
        return True
    elif value_str in ("false", "no", "n", "0", "short", "sell"):
        return False

    return default


# =============================================================================
# Date Parsing and TTM Calculation
# =============================================================================

DATE_FORMATS = [
    "%Y-%m-%d",      # 2024-01-15
    "%d/%m/%Y",      # 15/01/2024
    "%m/%d/%Y",      # 01/15/2024
    "%Y/%m/%d",      # 2024/01/15
    "%d-%m-%Y",      # 15-01-2024
    "%Y%m%d",        # 20240115
    "%d %b %Y",      # 15 Jan 2024
    "%d %B %Y",      # 15 January 2024
    "%b %d, %Y",     # Jan 15, 2024
    "%B %d, %Y",     # January 15, 2024
]


def _parse_date(value) -> Optional[date]:
    """Parse a date from various formats."""
    if value is None:
        return None

    # Already a date/datetime
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    # Handle pandas Timestamp
    try:
        if hasattr(value, 'date'):
            return value.date()
    except:
        pass

    # Handle NaT or NaN
    try:
        if pd.isna(value):
            return None
    except:
        pass

    # Parse string
    value_str = str(value).strip()
    if not value_str or value_str.lower() in ('nat', 'nan', 'none', ''):
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue

    return None


def _calculate_ttm(as_of_date: date, maturity_date: date) -> float:
    """Calculate time to maturity in years."""
    if as_of_date is None or maturity_date is None:
        return None

    days = (maturity_date - as_of_date).days
    years = days / 365.25

    # Floor at a small positive value (avoid negative/zero TTM)
    return max(years, 0.01)


# =============================================================================
# Currency Conversion
# =============================================================================

# Default FX rates to USD (approximate, for fallback only)
DEFAULT_FX_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0067,
    "CHF": 1.12,
    "CAD": 0.74,
    "AUD": 0.65,
    "CNY": 0.14,
    "HKD": 0.13,
    "SGD": 0.74,
    "KRW": 0.00075,
    "INR": 0.012,
    "BRL": 0.20,
    "MXN": 0.058,
    "ZAR": 0.055,
}


def _get_fx_converter(fx_rates, reference_ccy: str) -> FXRates:
    """
    Get an FXRates converter from various input formats.

    Accepts:
    - FXRates object (used directly)
    - dict with simple format {"EUR": 1.08, ...} (1 foreign = X reference)
    - None (uses defaults)
    """
    if fx_rates is None:
        return load_fx_rates_from_dict(
            DEFAULT_FX_RATES_TO_USD,
            input_format="to_reference",
            reference_ccy=reference_ccy,
        )

    if isinstance(fx_rates, FXRates):
        return fx_rates

    # Assume dict in "to_reference" format
    return load_fx_rates_from_dict(
        fx_rates,
        input_format="to_reference",
        reference_ccy=reference_ccy,
    )


def _convert_to_reference_ccy(
    amount: float,
    from_ccy: str,
    reference_ccy: str,
    fx_converter: FXRates,
) -> float:
    """
    Convert amount from one currency to reference currency.

    Uses the FXRates converter for proper handling of market conventions.
    """
    if amount is None:
        return None

    from_ccy = str(from_ccy).strip().upper() if from_ccy else reference_ccy
    reference_ccy = reference_ccy.upper()

    # Same currency, no conversion needed
    if from_ccy == reference_ccy:
        return amount

    return fx_converter.convert(amount, from_ccy, reference_ccy)


# =============================================================================
# Numeric Conversion
# =============================================================================

def _to_float(value, default: float = None) -> float:
    """Convert value to float, handling percentages and strings."""
    if value is None:
        return default

    try:
        if isinstance(value, float) and math.isnan(value):
            return default
    except (TypeError, ValueError):
        pass

    if isinstance(value, (int, float)):
        return float(value)

    # Handle string
    value_str = str(value).strip()

    # Remove common formatting
    value_str = value_str.replace(",", "").replace(" ", "")

    # Handle percentage
    if value_str.endswith("%"):
        try:
            return float(value_str[:-1]) / 100
        except ValueError:
            return default

    try:
        return float(value_str)
    except ValueError:
        return default


# =============================================================================
# Column Mapping
# =============================================================================

def _normalize_column_name(col: str) -> str:
    """Normalize a column name for comparison."""
    return col.lower().strip().replace(" ", "_").replace("-", "_")


def _find_standard_name(column: str) -> str:
    """Find the standard IRC field name for a given column."""
    col_normalized = _normalize_column_name(column)

    for standard_name, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if _normalize_column_name(alias) == col_normalized:
                return standard_name

    return None


def _build_column_mapping(columns: list) -> dict:
    """Build mapping from original column names to standard names."""
    mapping = {}
    for col in columns:
        standard = _find_standard_name(col)
        if standard:
            mapping[col] = standard
    return mapping


# =============================================================================
# Main Preparation Function
# =============================================================================

def prepare_irc_data(
    data: Union[list, "pd.DataFrame"],
    column_mapping: dict = None,
    validate: bool = True,
    as_of_date: Union[str, date, datetime] = None,
    reference_ccy: str = None,
    fx_rates: dict = None,
) -> Union[list, "pd.DataFrame"]:
    """
    Prepare raw data for IRC calculation.

    Accepts a DataFrame or list of dicts with flexible column names and formats.
    Returns clean data with standardized column names and values.

    Parameters
    ----------
    data : list[dict] or pd.DataFrame
        Raw portfolio data. Flexible column names accepted.

    column_mapping : dict, optional
        Custom column name mapping: {"your_column": "irc_field"}
        Overrides auto-detection.

    validate : bool
        If True, validates required fields and raises errors.

    as_of_date : str or date, optional
        Reference date for TTM calculation. If provided and data has
        maturity_date column, tenor_years will be calculated automatically.
        Formats: "2024-01-15", "15/01/2024", datetime, etc.

    reference_ccy : str, optional
        Reference currency for notional conversion (e.g., "USD", "EUR").
        If provided, all notionals will be converted to this currency.

    fx_rates : dict or FXRates, optional
        FX rates for currency conversion. Accepts:
        - dict: {"EUR": 1.08, "GBP": 1.27} means 1 EUR = 1.08 reference_ccy
        - FXRates object: from fx.py module with market convention handling
        If not provided, uses defaults.

    Returns
    -------
    list[dict] or pd.DataFrame
        Clean data ready for quick_irc().

    Required Fields (at least one of rating/pd, and tenor_years OR maturity_date):
    ------------------------------------------------------------------------------
    - issuer: Obligor name
    - notional: Position size
    - tenor_years OR maturity_date: Remaining maturity (if maturity_date, need as_of_date)
    - rating OR pd: Credit quality

    Optional Fields (defaults applied):
    ----------------------------------
    - ccy: Currency (for conversion if reference_ccy provided)
    - seniority: senior_unsecured
    - lgd: derived from seniority
    - sector: corporate
    - region: US
    - is_long: True
    - liquidity_horizon_months: 3
    - coupon_rate: 0.05

    Examples
    --------
    >>> # With TTM calculation and currency conversion
    >>> raw = pd.DataFrame({
    ...     "Issuer": ["Apple", "BMW", "Sony"],
    ...     "Rating": ["AA+", "A", "A-"],
    ...     "Maturity Date": ["2029-06-15", "2027-03-20", "2028-12-01"],
    ...     "Notional": [10e6, 8e6, 500e6],
    ...     "CCY": ["USD", "EUR", "JPY"],
    ... })
    >>> clean = prepare_irc_data(
    ...     raw,
    ...     as_of_date="2024-01-15",
    ...     reference_ccy="USD",
    ...     fx_rates={"EUR": 1.08, "JPY": 0.0067},
    ... )
    >>> result = quick_irc(clean.to_dict(orient="records"))
    """
    # Convert DataFrame to list of dicts for uniform processing
    is_dataframe = HAS_PANDAS and isinstance(data, pd.DataFrame)

    if is_dataframe:
        records = data.to_dict(orient="records")
        available_columns = list(data.columns)
    else:
        records = list(data)
        available_columns = list(records[0].keys()) if records else []

    # Build column mapping: original_name -> standard_name
    col_to_standard = _build_column_mapping(available_columns)
    if column_mapping:
        col_to_standard.update(column_mapping)

    # Build FX converter if needed
    fx_converter = None
    if reference_ccy:
        fx_converter = _get_fx_converter(fx_rates, reference_ccy)

    # Process each record
    clean_records = []
    errors = []

    for i, record in enumerate(records):
        clean = {}

        # Map column names
        for orig_key, value in record.items():
            std_key = col_to_standard.get(orig_key, orig_key.lower().strip())
            clean[std_key] = value

        # === Required: Issuer ===
        issuer = clean.get("issuer")
        if not issuer and validate:
            errors.append(f"Row {i}: missing issuer")
            continue
        clean["issuer"] = str(issuer).strip() if issuer else f"unknown_{i}"

        # === Required: Notional (with optional currency conversion) ===
        notional = _to_float(clean.get("notional"))
        if notional is None and validate:
            errors.append(f"Row {i}: missing or invalid notional")
            continue
        notional = notional or 0

        # Currency conversion if reference_ccy provided
        original_ccy = clean.get("ccy")
        if reference_ccy and notional and fx_converter:
            try:
                notional = _convert_to_reference_ccy(
                    notional,
                    from_ccy=original_ccy,
                    reference_ccy=reference_ccy,
                    fx_converter=fx_converter,
                )
                clean["original_ccy"] = original_ccy
                clean["ccy"] = reference_ccy
            except ValueError as e:
                if validate:
                    errors.append(f"Row {i}: {e}")
                    continue

        clean["notional"] = notional

        # === Required: Tenor (from tenor_years OR calculated from maturity_date) ===
        tenor = _to_float(clean.get("tenor_years"))

        # If no tenor but we have maturity_date and as_of_date, calculate TTM
        if tenor is None and as_of_date is not None:
            maturity_date_raw = clean.get("maturity_date")
            if maturity_date_raw is not None:
                parsed_as_of = _parse_date(as_of_date)
                parsed_maturity = _parse_date(maturity_date_raw)

                if parsed_as_of and parsed_maturity:
                    tenor = _calculate_ttm(parsed_as_of, parsed_maturity)
                    clean["maturity_date"] = parsed_maturity.isoformat()
                    clean["as_of_date"] = parsed_as_of.isoformat()

        if tenor is None and validate:
            errors.append(f"Row {i}: missing tenor_years (and no maturity_date/as_of_date to calculate)")
            continue

        clean["tenor_years"] = tenor or 1.0

        # === Rating (from rating or pd) ===
        raw_rating = clean.get("rating")
        raw_pd = _to_float(clean.get("pd"))

        # Handle PD as percentage (>1 means it was given as percent, e.g., 5 instead of 0.05)
        if raw_pd is not None and raw_pd > 1:
            raw_pd = raw_pd / 100

        if raw_rating is None and raw_pd is None and validate:
            errors.append(f"Row {i}: missing both rating and pd")
            continue

        # Resolve to base rating
        clean["rating"] = resolve_rating(
            rating=str(raw_rating) if raw_rating else None,
            pd=raw_pd,
        )

        # Store original PD if provided (useful for reporting)
        if raw_pd is not None:
            clean["pd"] = raw_pd

        # === Optional fields with defaults ===
        clean["market_value"] = _to_float(clean.get("market_value"), clean["notional"])
        clean["seniority"] = _normalize_seniority(clean.get("seniority"))
        clean["lgd"] = _to_float(clean.get("lgd"))  # None = derive from seniority
        sector = str(clean.get("sector", DEFAULTS["sector"])).strip().lower()
        if sector not in KNOWN_SECTORS:
            warnings.warn(
                f"Row {i} (issuer={clean['issuer']}): unrecognized sector '{sector}'. "
                f"Known sectors: {sorted(KNOWN_SECTORS)}. "
                f"Position will use default/region-based transition matrix.",
                stacklevel=2,
            )
        clean["sector"] = sector
        clean["region"] = str(clean.get("region", DEFAULTS["region"])).strip().upper()
        clean["is_long"] = _to_bool(clean.get("is_long"), DEFAULTS["is_long"])
        clean["liquidity_horizon_months"] = int(_to_float(
            clean.get("liquidity_horizon_months"), DEFAULTS["liquidity_horizon_months"]
        ))
        clean["coupon_rate"] = _to_float(clean.get("coupon_rate"), DEFAULTS["coupon_rate"])
        clean["position_id"] = str(clean.get("position_id", f"pos_{i}")).strip()

        clean_records.append(clean)

    # Report errors
    if errors and validate:
        raise ValueError(f"Data validation errors:\n" + "\n".join(errors))

    # Return in same format as input
    if is_dataframe:
        return pd.DataFrame(clean_records)
    return clean_records


def validate_irc_data(data: Union[list, "pd.DataFrame"]) -> dict:
    """
    Validate data for IRC without modifying it.

    Returns
    -------
    dict
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
            "summary": dict
        }
    """
    errors = []
    warnings = []

    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        records = data.to_dict(orient="records")
    else:
        records = list(data)

    if not records:
        errors.append("No data provided")
        return {"valid": False, "errors": errors, "warnings": warnings, "summary": {}}

    # Check for required columns using the mapping
    sample = records[0]
    col_mapping = _build_column_mapping(list(sample.keys()))
    mapped_fields = set(col_mapping.values())

    has_issuer = "issuer" in mapped_fields
    has_notional = "notional" in mapped_fields
    has_tenor = "tenor_years" in mapped_fields
    has_rating = "rating" in mapped_fields
    has_pd = "pd" in mapped_fields

    if not has_issuer:
        errors.append("Missing issuer column")
    if not has_notional:
        errors.append("Missing notional column")
    if not has_tenor:
        errors.append("Missing tenor_years column")
    if not has_rating and not has_pd:
        errors.append("Missing both rating and pd columns (need at least one)")

    # Check for unrecognized sectors
    sector_col = None
    for orig, std in col_mapping.items():
        if std == "sector":
            sector_col = orig
            break

    if sector_col:
        unrecognized = set()
        for rec in records:
            val = rec.get(sector_col)
            if val is not None:
                sector_lower = str(val).strip().lower()
                if sector_lower and sector_lower not in KNOWN_SECTORS:
                    unrecognized.add(sector_lower)
        if unrecognized:
            warnings.append(
                f"Unrecognized sectors: {sorted(unrecognized)}. "
                f"Known sectors: {sorted(KNOWN_SECTORS)}"
            )

    # Summary
    summary = {
        "num_records": len(records),
        "columns_found": list(sample.keys()),
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


# =============================================================================
# Convenience Function
# =============================================================================

def load_and_prepare(filepath: str, **kwargs) -> "pd.DataFrame":
    """
    Load CSV and prepare for IRC in one step.

    Parameters
    ----------
    filepath : str
        Path to CSV file.
    **kwargs
        Passed to prepare_irc_data().

    Returns
    -------
    pd.DataFrame
        Clean data ready for IRC.
    """
    if not HAS_PANDAS:
        raise ImportError("pandas required for load_and_prepare()")

    df = pd.read_csv(filepath)
    return prepare_irc_data(df, **kwargs)
