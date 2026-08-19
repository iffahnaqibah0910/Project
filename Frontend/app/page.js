"use client";

import { useEffect, useState } from "react";
import { fetchJSON } from "../lib/api";
import MissingnessPanel from "../components/MissingnessPanel";
import RollingChart from "../components/RollingChart";
import AlertFeed from "../components/AlertFeed";
import DataTable from "../components/DataTable";

const SENSORS = ["RUNTIME_SEC", "DAILY_MC_RATIO"];

export default function Dashboard() {
  const [missingness, setMissingness] = useState(null);
  const [eda, setEda] = useState(null);
  const [sensor, setSensor] = useState("RUNTIME_SEC");
  const [error, setError] = useState(null);

  useEffect(() => {
    const ac = new AbortController();

    // Load independently — Promise.all previously hid missingness whenever
    // the heavier /api/eda call failed or timed out through the Next proxy.
    async function loadMissingness() {
      try {
        const mp = await fetchJSON("/api/missingness", { signal: ac.signal });
        if (!ac.signal.aborted) setMissingness(mp);
      } catch (e) {
        if (ac.signal.aborted || e.name === "AbortError") return;
        setError((prev) => prev || e.message || "Failed to fetch missingness");
      }
    }

    async function loadEda() {
      try {
        const edaData = await fetchJSON("/api/eda", { signal: ac.signal });
        if (!ac.signal.aborted) {
          setEda(edaData);
          setError(null);
        }
      } catch (e) {
        if (ac.signal.aborted || e.name === "AbortError") return;
        setError(e.message || "Failed to fetch EDA");
      }
    }

    loadMissingness();
    loadEda();
    return () => ac.abort();
  }, []);

  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <span className="eyebrow">Missing Values</span>
          <h1>Automated Error Of Missing Values Detection Dashboard For Machine Running Data Monitoring</h1>
        </div>
        <div className="sensor-picker">
          {SENSORS.map((s) => (
            <button
              key={s}
              className={s === sensor ? "active" : ""}
              onClick={() => setSensor(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </header>

      {error && (
        <p className="error">
          Backend request failed — check that the API on :8000 is healthy. ({error})
        </p>
      )}

      <div className="top-row">
        <aside className="sidebar">
          <AlertFeed />
        </aside>
        <div className="missingness-slot">
          <MissingnessPanel missingness={missingness} />
        </div>
      </div>

      <div className="grid">
        <div className="table-slot">
          <DataTable />
        </div>

        <section className="chart-panel">
          <div className="panel-head">
            <h3>Time Series Chart of Exploratory Data Analysis — {sensor}</h3>
          </div>
          <RollingChart eda={eda} sensor={sensor} />
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
        .eyebrow {
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--amber);
        }
        h1 { margin: 4px 0 0; font-size: 26px; font-weight: 700; letter-spacing: -0.01em; }
        .sensor-picker { display: flex; gap: 6px; }
        .sensor-picker button {
          background: var(--panel);
          border: 1px solid var(--line);
          color: var(--text-dim);
          padding: 8px 14px;
          border-radius: 4px;
          font-size: 12px;
          text-transform: capitalize;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        .sensor-picker button.active {
          border-color: var(--amber);
          color: var(--amber);
          background: rgba(224,166,64,0.08);
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
        .panel-head { margin-bottom: 14px; }
        .panel-head h3 { margin: 4px 0 0; font-size: 16px; font-weight: 600; }
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
        }
      `}</style>
    </main>
  );
}
