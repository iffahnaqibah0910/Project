"""
Phase 4: algorithmic rule engine + plausibility checks that turn the
Phase 2 rolling stats into concrete alerts, plus the corrective-action
lookup dictionary from Phase 3.
"""
import pandas as pd

Z_THRESHOLD = 3.0
NUMERIC_SENSORS = ["RUNTIME_SEC", "DAILY_MC_RATIO"]

CORRECTIVE_ACTIONS = {
    "z_score_spike": "Check sensor wiring/calibration; compare against adjacent machines for drift vs. fault.",
    "runtime_ratio_mismatch": "RUNTIME_SEC and DAILY_MC_RATIO disagree — verify daily summary calculation and machine clock.",
    "high_missingness": "Missingness above threshold — check network link or ETL feed for the affected field.",
}


def apply_rule_engine(eda_df: pd.DataFrame) -> list[dict]:
    """Threshold/z-score based anomaly rules on numeric MRR sensors."""
    alerts = []
    for col in NUMERIC_SENSORS:
        z_col = f"{col}_zscore"
        if z_col not in eda_df:
            continue
        spikes = eda_df[eda_df[z_col].abs() > Z_THRESHOLD]
        for _, row in spikes.iterrows():
            ts = row["timestamp"] if "timestamp" in row else row.get("WKDATE")
            alerts.append({
                "timestamp": str(ts),
                "type": "z_score_spike",
                "sensor": col,
                "z_score": round(float(row[z_col]), 2),
                "corrective_action": CORRECTIVE_ACTIONS["z_score_spike"],
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
        alerts.append({
            "timestamp": str(row["WKDATE"]),
            "type": "runtime_ratio_mismatch",
            "sensor": "DAILY_MC_RATIO",
            "value": float(row["DAILY_MC_RATIO"]) if pd.notna(row["DAILY_MC_RATIO"]) else None,
            "corrective_action": CORRECTIVE_ACTIONS["runtime_ratio_mismatch"],
        })
    return alerts


def missingness_alerts(mp: dict, threshold: float = 10.0) -> list[dict]:
    alerts = []
    for sensor, pct in mp.items():
        if pct > threshold:
            alerts.append({
                "type": "high_missingness",
                "sensor": sensor,
                "missingness_pct": pct,
                "corrective_action": CORRECTIVE_ACTIONS["high_missingness"],
            })
    return alerts
