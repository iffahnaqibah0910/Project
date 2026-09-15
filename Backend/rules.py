"""
Phase 4: algorithmic rule engine + plausibility checks that turn
raw (unimputed) sensor values into concrete alerts, plus the
corrective-action lookup dictionary from Phase 3.
"""
import pandas as pd

MC_RATIO_THRESHOLD = 100.0

CORRECTIVE_ACTIONS = {
    "abnormal_daily_mc_ratio": "DAILY_MC_RATIO exceeds 100.",
    "runtime_ratio_mismatch": "RUNTIME_SEC and DAILY_MC_RATIO disagree — verify daily summary calculation and machine clock.",
    "missing_value": "Required field is null/blank.",
}


def _row_factory(row) -> str | None:
    if "FACTORY" not in row or pd.isna(row["FACTORY"]):
        return None
    value = str(row["FACTORY"]).strip()
    return value or None


def apply_rule_engine(df: pd.DataFrame) -> list[dict]:
    """Flag abnormal DAILY_MC_RATIO values above the hard threshold."""
    alerts = []
    if "DAILY_MC_RATIO" not in df.columns:
        return alerts

    work = df.copy()
    work["DAILY_MC_RATIO"] = pd.to_numeric(work["DAILY_MC_RATIO"], errors="coerce")
    spikes = work[work["DAILY_MC_RATIO"] > MC_RATIO_THRESHOLD]

    for _, row in spikes.iterrows():
        ts = row["WKDATE"] if "WKDATE" in row else row.get("timestamp")
        machine = row["MACHCODE"] if "MACHCODE" in row and pd.notna(row["MACHCODE"]) else None
        alerts.append({
            "timestamp": str(ts),
            "machine": None if machine is None else str(machine),
            "factory": _row_factory(row),
            "type": "abnormal_daily_mc_ratio",
            "sensor": "DAILY_MC_RATIO",
            "value": round(float(row["DAILY_MC_RATIO"]), 2),
            "corrective_action": CORRECTIVE_ACTIONS["abnormal_daily_mc_ratio"],
        })
    return alerts


def check_state_contradictions(raw_df: pd.DataFrame) -> list[dict]:
    """Flag rows where runtime seconds and daily ratio are logically inconsistent
    (near-zero runtime but a non-trivial ratio, or vice versa).
    """
    alerts = []
    if not {"RUNTIME_SEC", "DAILY_MC_RATIO", "WKDATE"}.issubset(raw_df.columns):
        return alerts

    df = raw_df.copy()
    df["RUNTIME_SEC"] = pd.to_numeric(df["RUNTIME_SEC"], errors="coerce")
    df["DAILY_MC_RATIO"] = pd.to_numeric(df["DAILY_MC_RATIO"], errors="coerce")

    mismatches = df[
        ((df["RUNTIME_SEC"].fillna(0) < 60) & (df["DAILY_MC_RATIO"].fillna(0) > 5))
        | ((df["RUNTIME_SEC"].fillna(0) > 3600) & (df["DAILY_MC_RATIO"].fillna(0) < 0.5))
    ]
    for _, row in mismatches.iterrows():
        machine = row["MACHCODE"] if "MACHCODE" in row and pd.notna(row["MACHCODE"]) else None
        alerts.append({
            "timestamp": str(row["WKDATE"]),
            "machine": None if machine is None else str(machine),
            "factory": _row_factory(row),
            "type": "runtime_ratio_mismatch",
            "sensor": "DAILY_MC_RATIO",
            "value": float(row["DAILY_MC_RATIO"]) if pd.notna(row["DAILY_MC_RATIO"]) else None,
            "corrective_action": CORRECTIVE_ACTIONS["runtime_ratio_mismatch"],
        })
    return alerts


def missing_value_alerts(df: pd.DataFrame) -> list[dict]:
    """One alert per null/blank cell so missing rows always appear in the stream."""
    alerts = []
    cols = [c for c in (
        "MACHCODE", "WKDATE", "MACHNAME", "RUNTIME_SEC",
        "RUNTIME_HOUR", "DAILY_MC_RATIO", "FACTORY",
    ) if c in df.columns]
    for _, row in df.iterrows():
        machine = row["MACHCODE"] if "MACHCODE" in row and pd.notna(row["MACHCODE"]) else None
        ts = row["WKDATE"] if "WKDATE" in row else None
        for col in cols:
            val = row[col]
            is_missing = pd.isna(val) or (isinstance(val, str) and val.strip() == "")
            if is_missing:
                alerts.append({
                    "timestamp": str(ts),
                    "machine": None if machine is None else str(machine),
                    "factory": _row_factory(row),
                    "type": "missing_value",
                    "sensor": col,
                    "value": None,
                    "corrective_action": CORRECTIVE_ACTIONS["missing_value"],
                })
    return alerts


def missingness_alerts(mp: dict, threshold: float = 10.0, missing_counts: dict | None = None) -> list[dict]:
    """Column-level missingness summary alerts (kept for Mp panel use; not streamed)."""
    alerts = []
    for sensor, pct in mp.items():
        count = None if missing_counts is None else int(missing_counts.get(sensor, 0))
        if (count is not None and count > 0) or pct > threshold:
            alerts.append({
                "type": "high_missingness",
                "sensor": sensor,
                "missingness_pct": pct,
                "missing_count": count,
                "corrective_action": CORRECTIVE_ACTIONS["high_missingness"],
            })
    return alerts
