"""
Phase 4: algorithmic rule engine + state-contradiction checks that turn the
Phase 2 rolling stats into concrete alerts, plus the corrective-action
lookup dictionary from Phase 3.
"""
import pandas as pd

Z_THRESHOLD = 3.0

CORRECTIVE_ACTIONS = {
    "z_score_spike": "Check sensor wiring/calibration; compare against adjacent sensors for drift vs. fault.",
    "state_power_contradiction": "Machine reports 'stopped' but rpm > 0 — verify state sensor and confirm true machine status on-site.",
    "high_missingness": "Missingness above threshold — check network link or sensor power to the affected device.",
}


def apply_rule_engine(eda_df: pd.DataFrame) -> list[dict]:
    """Threshold/z-score based anomaly rules."""
    alerts = []
    for col in ["temperature", "pressure", "vibration", "rpm"]:
        z_col = f"{col}_zscore"
        if z_col not in eda_df:
            continue
        spikes = eda_df[eda_df[z_col].abs() > Z_THRESHOLD]
        for idx, row in spikes.iterrows():
            alerts.append({
                "timestamp": str(row["timestamp"]),
                "type": "z_score_spike",
                "sensor": col,
                "z_score": round(float(row[z_col]), 2),
                "corrective_action": CORRECTIVE_ACTIONS["z_score_spike"],
            })
    return alerts


def check_state_contradictions(raw_df: pd.DataFrame) -> list[dict]:
    """Flag rows where machine_state and sensor readings logically contradict
    (e.g. 'stopped' but rpm suggests it's spinning).
    """
    alerts = []
    contradictions = raw_df[(raw_df["machine_state"] == "stopped") & (raw_df["rpm"] > 100)]
    for idx, row in contradictions.iterrows():
        alerts.append({
            "timestamp": str(row["timestamp"]),
            "type": "state_power_contradiction",
            "sensor": "rpm",
            "value": float(row["rpm"]),
            "corrective_action": CORRECTIVE_ACTIONS["state_power_contradiction"],
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