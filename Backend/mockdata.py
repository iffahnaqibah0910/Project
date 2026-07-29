"""
Generates fake 'raw machine stream' data so the whole pipeline can be built
and tested before a real SQL Server connection exists.

Swap this module out for real DB calls later (see data_source.py) without
touching any FastAPI routes or frontend code.
"""
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SENSORS = ["temperature", "pressure", "vibration", "rpm"]


def generate_raw_stream(n_points: int = 500, seed: int = 42) -> pd.DataFrame:
    """Simulate a raw machine data stream with realistic problems baked in:
    - missing values (NaN) scattered per sensor
    - a few out-of-range / wrong-type values (schema violations)
    - a handful of injected anomalies (spikes / drift) for the rule engine to catch
    """
    rng = np.random.default_rng(seed)
    start = datetime.utcnow() - timedelta(minutes=n_points)
    timestamps = [start + timedelta(minutes=i) for i in range(n_points)]

    data = {
        "timestamp": timestamps,
        "temperature": 70 + rng.normal(0, 2, n_points).cumsum() * 0.05 + rng.normal(0, 1, n_points),
        "pressure": 30 + rng.normal(0, 0.5, n_points),
        "vibration": 0.5 + np.abs(rng.normal(0, 0.1, n_points)),
        "rpm": 1500 + rng.normal(0, 20, n_points),
    }
    df = pd.DataFrame(data)

    # Inject anomalies (spikes) so Phase 4's rule engine has something to detect
    anomaly_idx = rng.choice(n_points, size=6, replace=False)
    for idx in anomaly_idx[:3]:
        df.loc[idx, "temperature"] += rng.choice([25, -25])
    for idx in anomaly_idx[3:]:
        df.loc[idx, "vibration"] += rng.uniform(2, 4)

    # Inject missing values (~8% per sensor, scattered)
    for col in SENSORS:
        missing_idx = rng.choice(n_points, size=int(n_points * 0.08), replace=False)
        df.loc[missing_idx, col] = np.nan

    # Inject a schema/type violation column: machine_state should be a
    # fixed set of strings, but a few rows get a stray numeric/garbage value.
    # Use dtype=object explicitly so pandas doesn't upcast this to a strict
    # StringDtype column, which would reject the intentionally-bad values below.
    states = rng.choice(["running", "idle", "stopped"], size=n_points)
    df["machine_state"] = pd.array(states, dtype=object)

    bad_state_idx = rng.choice(n_points, size=3, replace=False)
    for idx in bad_state_idx:
       df.loc[idx, "machine_state"] = random.choice(["9999", "N/A", None])

    df["machine_id"] = "M-01"
    return df