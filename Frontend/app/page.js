"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJSON, withQuery } from "../lib/api";
import MissingnessPanel from "../components/MissingnessPanel";
import RollingChart from "../components/RollingChart";
import AlertFeed from "../components/AlertFeed";
import DataTable from "../components/DataTable";
import StatusStrip from "../components/StatusStrip";

const SNAPSHOT_REFRESH_MS = 5 * 60 * 1000;

export default function Dashboard() {
  const [missingness, setMissingness] = useState(null);
  const [eda, setEda] = useState(null);
  const [factories, setFactories] = useState([]);
  const [factory, setFactory] = useState("");
  const [error, setError] = useState(null);
  const [alertStatus, setAlertStatus] = useState({
    count: null,
    connected: false,
    at: null,
  });
  const [tableStatus, setTableStatus] = useState({
    flagged: null,
    pageRows: null,
    at: null,
  });
  const [missingnessAt, setMissingnessAt] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadFactories() {
      try {
        const data = await fetchJSON("/api/factories");
        if (!cancelled) setFactories(data.factories || []);
      } catch (e) {
        if (cancelled) return;
        setError((prev) => prev || e.message || "Failed to fetch factories");
      }
    }

    loadFactories();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    // Load independently — Promise.all previously hid missingness whenever
    // the heavier /api/eda call failed or timed out through the Next proxy.
    // Use a cancelled flag (not AbortController) so React Strict Mode remounts
    // don't abort the in-flight request and leave panels stuck on "Loading…".
    async function loadMissingness() {
      try {
        const mp = await fetchJSON(withQuery("/api/missingness", { factory }));
        if (!cancelled) {
          setMissingness(mp);
          setMissingnessAt(Date.now());
        }
      } catch (e) {
        if (cancelled) return;
        setError((prev) => prev || e.message || "Failed to fetch missingness");
      }
    }

    async function loadEda() {
      try {
        const edaData = await fetchJSON(withQuery("/api/eda", { factory }));
        if (!cancelled) {
          setEda(edaData);
        }
      } catch (e) {
        if (cancelled) return;
        setError((prev) => prev || e.message || "Failed to fetch EDA");
      }
    }

    setMissingness(null);
    setEda(null);
    setMissingnessAt(null);
    setAlertStatus({ count: null, connected: false, at: null });
    setTableStatus({ flagged: null, pageRows: null, at: null });
    loadMissingness();
    loadEda();

    const id = setInterval(() => {
      if (cancelled) return;
      loadMissingness();
      loadEda();
      setRefreshTick((n) => n + 1);
    }, SNAPSHOT_REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [factory]);

  const worstMissing = useMemo(() => {
    const pcts = missingness?.missingness_pct;
    if (!pcts) return null;
    let field = null;
    let pct = -1;
    for (const [key, value] of Object.entries(pcts)) {
      const n = Number(value);
      if (Number.isFinite(n) && n > pct) {
        pct = n;
        field = key;
      }
    }
    return field == null ? { field: null, pct: 0 } : { field, pct };
  }, [missingness]);

  const refreshTimes = [missingnessAt, tableStatus.at].filter((n) => n != null);
  const lastRefreshAt = refreshTimes.length ? Math.max(...refreshTimes) : null;

  function handleAlertStatus(next) {
    if ((next.factory ?? "") !== factory) return;
    setAlertStatus({
      count: next.count,
      connected: Boolean(next.connected),
      at: next.at ?? null,
    });
  }

  function handleTableStatus(next) {
    if ((next.factory ?? "") !== factory) return;
    setTableStatus({
      flagged: next.flagged,
      pageRows: next.pageRows,
      at: next.at ?? null,
    });
  }

  return (
    <main className="dashboard">
      <header className="topbar">
        <div className="title-block">
          <span className="eyebrow">Missing Values</span>
          <h1>Automated Missing Value Error Detection Dashboard For Machine Running Data Monitoring</h1>
        </div>
        <label className="factory-picker">
          <span>Factory</span>
          <select
            value={factory}
            onChange={(e) => setFactory(e.target.value)}
            aria-label="Choose factory"
          >
            <option value="">All factories</option>
            {factories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </header>

      {error && (
        <p className="error">
          Backend request failed — check that the API on :8000 is healthy. ({error})
        </p>
      )}

      <StatusStrip
        alertCount={alertStatus.count}
        connected={alertStatus.connected}
        worstPct={worstMissing?.pct}
        worstField={worstMissing?.field}
        missingReady={Boolean(missingness)}
        flagged={tableStatus.flagged}
        pageRows={tableStatus.pageRows}
        tableReady={tableStatus.flagged != null}
        lastRefreshAt={lastRefreshAt}
      />

      <div className="top-row">
        <aside className="sidebar">
          <AlertFeed factory={factory} onStatusChange={handleAlertStatus} />
        </aside>
        <div className="missingness-slot">
          <MissingnessPanel missingness={missingness} factory={factory} />
        </div>
      </div>

      <div className="grid">
        <div className="table-slot">
          <DataTable
            factory={factory}
            refreshTick={refreshTick}
            onStatsChange={handleTableStatus}
          />
        </div>

        <section className="chart-panel">
          <div className="panel-head">
            <h3>Daily MC Ratio Trend</h3>
          </div>
          <div className="chart-frame">
            <div className="chart-legend" aria-label="Chart legend">
              <span className="legend-item">
                <span className="legend-line solid" />
                Mean
              </span>
              <span className="legend-item">
                <span className="legend-line dashed" />
                +2σ
              </span>
              <span className="legend-item">
                <span className="legend-line dashed" />
                -2σ
              </span>
            </div>
            <RollingChart eda={eda} sensor="DAILY_MC_RATIO" />
          </div>
        </section>
      </div>

      <style jsx>{`
        .dashboard {
          min-height: 100vh;
          padding: 32px 40px 60px;
          max-width: 1400px;
          margin: 0 auto;
        }
        .topbar {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 16px;
          margin-bottom: 28px;
          border-bottom: 5px solid var(--line);
          padding-bottom: 20px;
        }
        .title-block {
          min-width: 0;
        }
        .eyebrow {
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--amber);
        }
        h1 { margin: 4px 0 0; font-size: 26px; font-weight: 700; letter-spacing: -0.01em; }
        .factory-picker {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--text-dim);
        }
        .factory-picker select {
          background: var(--panel);
          border: 1px solid var(--line);
          color: var(--text-primary);
          padding: 8px 12px;
          border-radius: 4px;
          font-size: 12px;
          letter-spacing: 0;
          text-transform: none;
          cursor: pointer;
          min-width: 180px;
        }
        .factory-picker select:focus {
          outline: none;
          border-color: var(--amber);
        }
        .top-row {
          display: grid;
          grid-template-columns: 380px minmax(0, 1fr);
          gap: 20px;
          align-items: stretch;
          margin-bottom: 20px;
        }
        .sidebar {
          min-width: 0;
        }
        .missingness-slot {
          min-width: 0;
        }
        .grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 20px;
          min-width: 0;
        }
        .chart-panel {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 6px;
          padding: 20px;
        }
        .panel-head {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 14px;
        }
        .panel-head h3 { margin: 0; font-size: 16px; font-weight: 600; }
        .chart-frame {
          position: relative;
          background: var(--panel);
        }
        .chart-legend {
          position: absolute;
          top: 18px;
          right: 16px;
          z-index: 2;
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 12px;
          background: var(--panel-raised);
          border: 1px solid var(--line);
          border-radius: 4px;
          padding: 6px 12px;
        }
        .legend-item {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: var(--text-primary);
          white-space: nowrap;
        }
        .legend-line {
          width: 22px;
          height: 0;
          border-top: 2px solid var(--amber);
        }
        .legend-line.dashed {
          border-top-width: 1.5px;
          border-top-style: dashed;
          opacity: 0.7;
        }
        .error {
          background: rgba(217,96,79,0.1);
          border: 1px solid var(--alert-red);
          color: var(--alert-red);
          padding: 12px 16px;
          border-radius: 6px;
          font-size: 13px;
          margin-bottom: 20px;
        }
        @media (max-width: 960px) {
          .top-row {
            grid-template-columns: 1fr;
          }
          .panel-head {
            flex-direction: column;
            align-items: flex-start;
          }
        }
      `}</style>
    </main>
  );
}
