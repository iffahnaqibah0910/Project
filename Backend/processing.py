"""
Phase 1 (ingestion & preprocessing) + Phase 2 (rolling-window EDA) logic.
Pure pandas on DataFrames loaded from SQL Server.
"""
import re

import numpy as np
import pandas as pd

ALL_COLUMNS = [
    "MACHCODE",
    "WKDATE",
    "MACHNAME",
    "RUNTIME_SEC",
    "RUNTIME_HOUR",
    "DAILY_MC_RATIO",
    "FACTORY",
]
NUMERIC_SENSORS = ["RUNTIME_SEC", "DAILY_MC_RATIO"]
TIME_COL = "WKDATE"
_HHMMSS = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")


def _is_blank(value) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return True
    if pd.isna(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def detect_schema_violations(df: pd.DataFrame) -> list[dict]:
    """Flag rows/columns that don't match the expected schema."""
    violations = []

    for col in NUMERIC_SENSORS:
        if col not in df.columns:
            continue
        bad = df[~df[col].apply(
            lambda v: isinstance(v, (int, float, np.integer, np.floating)) or pd.isna(v)
        )]
        for idx in bad.index:
            violations.append({
                "row": int(idx),
                "column": col,
                "issue": "non-numeric value",
                "value": str(df.loc[idx, col]),
            })

    if "RUNTIME_HOUR" in df.columns:
        bad_hour = df[
            df["RUNTIME_HOUR"].notna()
            & ~df["RUNTIME_HOUR"].astype(str).str.match(_HHMMSS)
            & (df["RUNTIME_HOUR"].astype(str).str.strip() != "")
        ]
        for idx in bad_hour.index:
            violations.append({
                "row": int(idx),
                "column": "RUNTIME_HOUR",
                "issue": "invalid HH:MM:SS duration",
                "value": str(df.loc[idx, "RUNTIME_HOUR"]),
            })

    # Explicit null/blank detections so missing values surface as violations
    # even when overall Mp% is tiny on a large table.
    for col in ALL_COLUMNS:
        if col not in df.columns:
            continue
        blank = df[df[col].map(_is_blank)]
        for idx in blank.index:
            violations.append({
                "row": int(idx),
                "column": col,
                "issue": "missing value",
                "value": "null",
            })

    return violations


def calculate_missingness(df: pd.DataFrame) -> dict:
    """Exact Missingness Percentage (Mp) per column.

    Treats pandas NA and blank/whitespace strings as missing — SQL Server
    often stores '' instead of NULL for text fields.
    """
    total = len(df)
    mp = {}
    for col in ALL_COLUMNS:
        if col not in df.columns:
            mp[col] = 0.0
            continue
        missing = int(df[col].map(_is_blank).sum())
        mp[col] = round(float(missing / total) * 100, 4) if total else 0.0
    return mp


def prepare_for_eda(df: pd.DataFrame) -> pd.DataFrame:
    """Sort and coerce types for rolling stats only. Does not impute or
    repair values — missing/invalid numeric fields stay as NaN so errors
    remain visible to the detection dashboard.
    """
    out = df.copy()
    if TIME_COL not in out.columns:
        raise KeyError(f"Expected time column '{TIME_COL}' in dataframe")

    # WKDATE is stored as YYYYMMDD (e.g. "20260810").
    out[TIME_COL] = pd.to_datetime(out[TIME_COL], format="%Y%m%d", errors="coerce")
    out = out.dropna(subset=[TIME_COL]).sort_values(TIME_COL)

    for col in NUMERIC_SENSORS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    return out


def rolling_window_eda(df: pd.DataFrame, window: int = 7) -> pd.DataFrame:
    """Daily rolling-window EDA for the chart.

    Rows are first averaged by WKDATE (many machines share one work date),
    then a short rolling mean/std/z-score is computed. That keeps the
    /api/eda payload small and chart-friendly instead of shipping ~2000
    near-duplicate machine rows (~600KB+) that routinely timed out the
    Next.js proxy under concurrent dashboard load.
    """
    work = prepare_for_eda(df)
    present = [c for c in NUMERIC_SENSORS if c in work.columns]
    if not present:
        return pd.DataFrame(columns=["timestamp"])

    daily = (
        work.groupby(TIME_COL, as_index=False)[present]
        .mean(numeric_only=True)
        .sort_values(TIME_COL)
    )

    out = pd.DataFrame({"timestamp": daily[TIME_COL]})
    for col in present:
        roll = daily[col].rolling(window=window, min_periods=2)
        out[f"{col}_roll_mean"] = roll.mean()
        out[f"{col}_roll_std"] = roll.std()
        out[f"{col}_zscore"] = (
            (daily[col] - out[f"{col}_roll_mean"])
            / out[f"{col}_roll_std"].replace(0, np.nan)
        )

    if {"RUNTIME_SEC", "DAILY_MC_RATIO"}.issubset(daily.columns):
        out["runtime_ratio_roll_corr"] = (
            daily["RUNTIME_SEC"]
            .rolling(window=window, min_periods=2)
            .corr(daily["DAILY_MC_RATIO"])
        )
    return out
