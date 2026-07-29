import asyncio
import json
import time

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import Response

from datasource import get_raw_data
from processing import (
    calculate_missingness,
    clean_and_impute,
    detect_schema_violations,
    rolling_window_eda,
)
from rules import apply_rule_engine, check_state_contradictions, missingness_alerts

app = FastAPI(title="Automatic Error Missing Values Detection Dashboard API")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _records(df: pd.DataFrame):
    """Convert a DataFrame to plain-Python JSON records, letting pandas'
    own encoder handle numpy dtypes and timestamps instead of FastAPI's."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _pipeline():
    """Runs Phase 1 + Phase 2 + Phase 4 end to end on the current data."""
    raw = get_raw_data()
    schema_violations = detect_schema_violations(raw)
    mp = calculate_missingness(raw)
    cleaned = clean_and_impute(raw)
    eda = rolling_window_eda(cleaned)

    alerts = (
        apply_rule_engine(eda)
        + check_state_contradictions(cleaned)
        + missingness_alerts(mp)
    )
    return raw, cleaned, eda, schema_violations, mp, alerts


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/data")
def get_data():
    """Cleaned + imputed data, ready to chart."""
    _, cleaned, _, _, _, _ = _pipeline()
    return _records(cleaned)


@app.get("/api/missingness")
def get_missingness():
    """Phase 1, Objective 1: exact Mp per sensor + schema violations found."""
    raw = get_raw_data()
    schema_violations = detect_schema_violations(raw)
    mp = calculate_missingness(raw)
    return {"missingness_pct": mp, "schema_violations": schema_violations}


@app.get("/api/eda")
def get_eda():
    """Phase 2: rolling window statistical EDA."""
    _, cleaned, eda, _, _, _ = _pipeline()
    return _records(eda.fillna(0))


@app.get("/api/alerts")
def get_alerts():
    """Phase 4: current alerts + corrective actions (snapshot, non-streaming)."""
    *_, alerts = _pipeline()
    return alerts


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Phase 4: live alert stream. Each message carries a server timestamp
    and a computed diagnostic_latency_ms so the frontend can display/measure
    detection-to-delivery latency.
    """
    await websocket.accept()
    try:
        while True:
            t0 = time.perf_counter()
            *_ , alerts = _pipeline()
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            await websocket.send_json({
                "server_time": time.time(),
                "diagnostic_latency_ms": latency_ms,
                "alert_count": len(alerts),
                "alerts": alerts[-10:],  # most recent batch
            })
            await asyncio.sleep(5)  # simulate a new stream tick every 5s
    except WebSocketDisconnect:
        pass
    