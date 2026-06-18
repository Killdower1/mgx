"""Upload validation utilities.

Validates uploaded Excel data before processing:
- Required columns existence
- Period format (YYYY-MM)
- Non-empty outlet names
- Non-negative prices
"""

import re
from typing import List, Tuple

import pandas as pd


def validate_period(series: pd.Series) -> Tuple[bool, List[str]]:
    """Check period values match YYYY-MM format."""
    pattern = re.compile(r"^\d{4}-\d{2}$")
    str_vals = series.dropna().astype(str)
    bad = str_vals[~str_vals.str.match(pattern)]
    if len(bad):
        return False, [f"Invalid period format '{v}' (expected YYYY-MM)" for v in bad.unique()[:5]]
    return True, []


def validate_outlet_names(series: pd.Series) -> Tuple[bool, List[str]]:
    """Check outlet names are non-empty strings."""
    empty_mask = series.isna() | (series.astype(str).str.strip() == "")
    if empty_mask.any():
        row_indices = series.index[empty_mask].tolist()
        return False, [f"Empty outlet name at row {i + 2} (Excel header + 1)" for i in row_indices[:10]]
    return True, []


def validate_prices(series: pd.Series) -> Tuple[bool, List[str]]:
    """Check prices are non-negative."""
    numeric = pd.to_numeric(series, errors="coerce")
    bad_mask = numeric < 0
    if bad_mask.any():
        bad_vals = series[bad_mask].unique()
        return False, [f"Negative price found: {v}" for v in bad_vals[:5]]
    return True, []


def validate_upload_df(df: pd.DataFrame, required_cols: List[str]) -> Tuple[bool, List[str]]:
    """Run all validations on the mapped upload DataFrame.

    Returns (is_valid, list_of_error_messages).
    """
    errors: List[str] = []

    # 1. Check required columns exist
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        # Cannot run per-field validators without the columns
        return False, errors

    # 2. Validate outlet names
    ok, errs = validate_outlet_names(df["outlet_name"])
    if not ok:
        errors.extend(errs)

    # 3. Validate prices
    ok, errs = validate_prices(df["harga"])
    if not ok:
        errors.extend(errs)

    # 4. Validate period if column exists
    if "periode" in df.columns:
        ok, errs = validate_period(df["periode"])
        if not ok:
            errors.extend(errs)

    return len(errors) == 0, errors
