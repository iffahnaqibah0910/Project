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


def detect_schema_violations(df: pd.DataFrame) -> list[dict]:
    """Flag rows/columns that don't match the expected schema."""
    violations = []

    for col in NUMERIC_SENSORS:
        if col not in df.columns:
            continue
        bad = df[~df[col].apply(lambda v: isinstance(v, (int, float, np.integer, np.floating)) or pd.isna(v))]
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
        ]
        for idx in bad_hour.index:
            violations.append({
                "row": int(idx),
                "column": "RUNTIME_HOUR",
                "issue": "invalid HH:MM:SS duration",
                "value": str(df.loc[idx, "RUNTIME_HOUR"]),
            })

    return violations


def calculate_missingness(df: pd.DataFrame) -> dict:
    """Exact Missingness Percentage (Mp) per column."""
    total = len(df)
    mp = {}
    for col in ALL_COLUMNS:
        if col not in df.columns:
            mp[col] = 0.0
            continue
        missing = df[col].isna().sum()
        mp[col] = round(float(missing / total) * 100, 2) if total else 0.0
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


def rolling_window_eda(df: pd.DataFrame, window: int = 15) -> pd.DataFrame:
    """Multi-variable rolling window statistical EDA on raw (unimputed) data:
    rolling mean, std, z-score per numeric sensor, plus rolling
    cross-correlation between runtime and daily machine ratio.
    NaNs from missing/invalid values are preserved in the calculations.
    """
    work = prepare_for_eda(df)
    out = pd.DataFrame({
        "timestamp": work[TIME_COL],
    })
    for col in NUMERIC_SENSORS:
        if col not in work.columns:
            continue
        roll = work[col].rolling(window=window, min_periods=3)
        out[f"{col}_roll_mean"] = roll.mean()
        out[f"{col}_roll_std"] = roll.std()
        out[f"{col}_zscore"] = (work[col] - out[f"{col}_roll_mean"]) / out[f"{col}_roll_std"].replace(0, np.nan)

    if all(c in work.columns for c in ("RUNTIME_SEC", "DAILY_MC_RATIO")):
        out["runtime_ratio_roll_corr"] = (
            work["RUNTIME_SEC"]
            .rolling(window=window, min_periods=3)
            .corr(work["DAILY_MC_RATIO"])
        )
    return out
