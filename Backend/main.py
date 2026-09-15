import asyncio
import json
import threading
import time
import traceback

import pandas as pd
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from datasource import (
    get_anomaly_rows,
    get_data_page,
    get_factory_names,
    get_full_missingness,
    get_raw_data,
    normalize_factory,
)
from processing import (
    detect_schema_violations,
    rolling_window_eda,
)
from rules import (
    apply_rule_engine,
    missing_value_alerts,
)

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


# Longer TTL: SQL TOP 2000 can take several seconds over the network.
# Sharing one snapshot across /api/* + ws ticks avoids stampeding the DB
# and blocking uvicorn's single worker. Cached per factory filter.
_PIPELINE_TTL_SEC = 30.0
_pipeline_cache: dict = {}
_pipeline_lock = threading.Lock()


def _pipeline(factory: str | None = None):
    """Runs Phase 1 + Phase 2 + Phase 4.

    - EDA uses the recent TOP-N sample (fast chart payload).
    - Missingness Mp is computed on the **full SQL table** (or one factory).
    - Alerts scan recent rows **plus** full-table anomaly rows so older
      DAILY_MC_RATIO > 100 / NULL fields still appear in the stream.
    """
    factory = normalize_factory(factory)
    key = factory or "__all__"
    now = time.time()
    cached = _pipeline_cache.get(key)
    if cached is not None and (now - cached["ts"]) < _PIPELINE_TTL_SEC:
        return cached["result"]

    with _pipeline_lock:
        now = time.time()
        cached = _pipeline_cache.get(key)
        if cached is not None and (now - cached["ts"]) < _PIPELINE_TTL_SEC:
            return cached["result"]

        recent = get_raw_data(factory)
        anomalies = get_anomaly_rows(factory)
        detection = (
            pd.concat([recent, anomalies], ignore_index=True)
            .drop_duplicates(subset=["MACHCODE", "WKDATE", "FACTORY"], keep="last")
            .reset_index(drop=True)
            if not anomalies.empty
            else recent
        )

        mp, missing_counts, total_rows = get_full_missingness(factory)
        schema_violations = detect_schema_violations(
            anomalies if not anomalies.empty else recent.head(0)
        )
        eda = rolling_window_eda(recent)

        alerts = (
            apply_rule_engine(detection)
            + missing_value_alerts(anomalies if not anomalies.empty else recent.head(0))
        )
        result = (recent, eda, schema_violations, mp, alerts, missing_counts, total_rows)
        _pipeline_cache[key] = {"ts": now, "result": result}
        return result


def _get_data_payload(page: int, page_size: int, factory: str | None) -> dict:
    raw, total = get_data_page(page=page, page_size=page_size, factory=factory)
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "rows": _records(raw),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "factory": normalize_factory(factory),
    }


def _get_missingness_payload(factory: str | None) -> dict:
    # result: recent, eda, schema_violations, mp, alerts, missing_counts, total_rows
    _recent, _eda, schema_violations, mp, _alerts, missing_counts, total_rows = _pipeline(factory)
    return {
        "missingness_pct": mp,
        "missing_counts": missing_counts,
        "total_rows": total_rows,
        "schema_violations": schema_violations,
        "factory": normalize_factory(factory),
    }


def _get_eda_payload(factory: str | None) -> list:
    _recent, eda, *_ = _pipeline(factory)
    return _records(eda)


def _get_alerts_payload(factory: str | None) -> list:
    # result: recent, eda, schema_violations, mp, alerts, missing_counts, total_rows
    return _pipeline(factory)[4]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/factories")
async def get_factories():
    """Distinct FACTORY values for the dashboard dropdown."""
    names = await asyncio.to_thread(get_factory_names)
    return {"factories": names}


@app.get("/api/data")
async def get_data(
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(15, ge=1, le=200, description="Rows per page"),
    factory: str | None = Query(None, description="Optional factory filter"),
):
    """Full-table page (errors/missing intact). Newest WKDATE first.

    Returns { rows, total, page, page_size, total_pages } so the UI can
    page through the entire SQL table without downloading it all at once.
    """
    return await asyncio.to_thread(_get_data_payload, page, page_size, factory)


@app.get("/api/missingness")
async def get_missingness(
    factory: str | None = Query(None, description="Optional factory filter"),
):
    """Phase 1, Objective 1: exact Mp per sensor + schema violations found."""
    return await asyncio.to_thread(_get_missingness_payload, factory)


@app.get("/api/eda")
async def get_eda(
    factory: str | None = Query(None, description="Optional factory filter"),
):
    """Phase 2: rolling window statistical EDA on raw (unimputed) data."""
    return await asyncio.to_thread(_get_eda_payload, factory)


@app.get("/api/alerts")
async def get_alerts(
    factory: str | None = Query(None, description="Optional factory filter"),
):
    """Phase 4: current alerts + corrective actions (snapshot, non-streaming)."""
    return await asyncio.to_thread(_get_alerts_payload, factory)


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
    factory = websocket.query_params.get("factory")
    try:
        while True:
            t0 = time.perf_counter()
            result = await asyncio.to_thread(_pipeline, factory)
            # result: recent, eda, schema_violations, mp, alerts, missing_counts, total_rows
            # Stream only row-level issues: missing_value + abnormal_daily_mc_ratio
            alerts = [
                a for a in result[4]
                if a.get("type") in ("missing_value", "abnormal_daily_mc_ratio")
            ]
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            await websocket.send_json({
                "server_time": time.time(),
                "diagnostic_latency_ms": latency_ms,
                "alert_count": len(alerts),
                "alerts": alerts[:15],
                "factory": normalize_factory(factory),
            })
            await asyncio.sleep(5)  # simulate a new stream tick every 5s
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        # Client gone mid-send ("socket.send() raised exception") — exit cleanly.
        traceback.print_exc()
