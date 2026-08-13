import asyncio
import json
import time
import traceback

import pandas as pd
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from datasource import get_raw_data
from processing import (
    calculate_missingness,
    detect_schema_violations,
    rolling_window_eda,
)
from rules import apply_rule_engine, check_state_contradictions, missingness_alerts

app = FastAPI(title="Automated Error Missing Values Detection Dashboard API")

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return JSON errors with CORS so the browser shows the real failure
    instead of a generic 'Failed to fetch'."""
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "http://localhost:3000"},
    )


def _records(df: pd.DataFrame):
    """Convert a DataFrame to plain-Python JSON records, letting pandas'
    own encoder handle numpy dtypes and timestamps instead of FastAPI's.
    WKDATE is emitted as YYYY-MM-DD so the UI shows work date, not insert time.
    """
    out = df.copy()
    if "WKDATE" in out.columns:
        out["WKDATE"] = pd.to_datetime(out["WKDATE"], errors="coerce").dt.strftime("%Y-%m-%d")
    return json.loads(out.to_json(orient="records", date_format="iso"))


# Short TTL so /api/data + /api/eda + /api/missingness + ws ticks share one
# SQL round-trip instead of stampeding the DB and blocking the event loop.
_PIPELINE_TTL_SEC = 3.0
_pipeline_cache: dict = {"ts": 0.0, "result": None}


def _pipeline():
    """Runs Phase 1 + Phase 2 + Phase 4 on raw (unimputed) data so missing
    values and errors stay visible for detection.
    """
    now = time.time()
    cached = _pipeline_cache["result"]
    if cached is not None and (now - _pipeline_cache["ts"]) < _PIPELINE_TTL_SEC:
        return cached

    raw = get_raw_data()
    schema_violations = detect_schema_violations(raw)
    mp = calculate_missingness(raw)
    eda = rolling_window_eda(raw)

    alerts = (
        apply_rule_engine(raw)
        + check_state_contradictions(raw)
        + missingness_alerts(mp)
    )
    result = (raw, eda, schema_violations, mp, alerts)
    _pipeline_cache["ts"] = now
    _pipeline_cache["result"] = result
    return result


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/data")
def get_data():
    """Raw source rows (errors/missing intact). Newest WKDATE first."""
    raw, *_ = _pipeline()
    if "WKDATE" in raw.columns:
        raw = raw.sort_values("WKDATE", ascending=False)
    return _records(raw)


@app.get("/api/missingness")
def get_missingness():
    """Phase 1, Objective 1: exact Mp per sensor + schema violations found."""
    raw = get_raw_data()
    schema_violations = detect_schema_violations(raw)
    mp = calculate_missingness(raw)
    return {"missingness_pct": mp, "schema_violations": schema_violations}


@app.get("/api/eda")
def get_eda():
    """Phase 2: rolling window statistical EDA on raw (unimputed) data."""
    _, eda, *_ = _pipeline()
    return _records(eda)


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

    Pipeline work is sync (SQL + pandas) — run it in a thread so it cannot
    freeze the asyncio loop (which previously caused proxy ECONNRESET /
    'socket hang up' on /api/* while alert sockets were open).
    """
    await websocket.accept()
    try:
        while True:
            t0 = time.perf_counter()
            *_, alerts = await asyncio.to_thread(_pipeline)
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
    except Exception:
        # Client gone mid-send ("socket.send() raised exception") — exit cleanly.
        traceback.print_exc()
