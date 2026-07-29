"""
Phase 1 (ingestion & preprocessing) + Phase 2 (rolling-window EDA) logic.
Pure pandas — works the same whether the DataFrame came from mock data or
SQL Server.
"""
import numpy as np
import pandas as pd

NUMERIC_SENSORS = ["temperature", "pressure", "vibration", "rpm"]
VALID_STATES = {"running", "idle", "stopped"}


def detect_schema_violations(df: pd.DataFrame) -> list[dict]:
    """Flag rows/columns that don't match the expected schema."""
    violations = []

    for col in NUMERIC_SENSORS:
        bad = df[~df[col].apply(lambda v: isinstance(v, (int, float)) or pd.isna(v))]
        for idx in bad.index:
            violations.append({"row": int(idx), "column": col, "issue": "non-numeric value", "value": str(df.loc[idx, col])})

    bad_state = df[~df["machine_state"].isin(VALID_STATES) & df["machine_state"].notna()]
    for idx in bad_state.index:
        violations.append({"row": int(idx), "column": "machine_state", "issue": "invalid category", "value": str(df.loc[idx, "machine_state"])})

    return violations


def calculate_missingness(df: pd.DataFrame) -> dict:
    """Exact Missingness Percentage (Mp) per column."""
    total = len(df)
    mp = {}
    for col in NUMERIC_SENSORS:
        missing = df[col].isna().sum()
        mp[col] = round(float(missing / total) * 100, 2) if total else 0.0
    return mp


def clean_and_impute(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic imputation: forward-fill then time-based interpolation
    for any leading NaNs ffill can't reach. Coerces bad-type cells to NaN first.
    """
    df = df.copy()
    for col in NUMERIC_SENSORS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["machine_state"] = df["machine_state"].where(df["machine_state"].isin(VALID_STATES))
    df["machine_state"] = df["machine_state"].ffill().fillna("unknown")

    df = df.set_index("timestamp")
    for col in NUMERIC_SENSORS:
        df[col] = df[col].interpolate(method="time").ffill().bfill()
    df = df.reset_index()

    return df


def rolling_window_eda(df: pd.DataFrame, window: int = 15) -> pd.DataFrame:
    """Multi-variable rolling window statistical EDA: rolling mean, std,
    z-score per sensor, plus rolling cross-correlation between two key
    variables as an example of multi-variable analysis.
    """
    out = df[["timestamp"]].copy()
    for col in NUMERIC_SENSORS:
        roll = df[col].rolling(window=window, min_periods=3)
        out[f"{col}_roll_mean"] = roll.mean()
        out[f"{col}_roll_std"] = roll.std()
        out[f"{col}_zscore"] = (df[col] - out[f"{col}_roll_mean"]) / out[f"{col}_roll_std"].replace(0, np.nan)

    out["temp_vibration_roll_corr"] = df["temperature"].rolling(window=window, min_periods=3).corr(df["vibration"])
    return out
