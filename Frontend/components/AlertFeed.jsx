"use client";

import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "../lib/api";

export default function AlertFeed() {
  const [alerts, setAlerts] = useState([]);
  const [latency, setLatency] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/alerts`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      setLatency(payload.diagnostic_latency_ms);
      setAlerts(payload.alerts.slice().reverse());
    };

    return () => ws.close();
  }, []);

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="eyebrow">Phase 4 · Live</span>
        <h3>
          Alert Stream
          <span className={`dot ${connected ? "on" : "off"}`} />
        </h3>
        {latency != null && (
          <span className="latency">diagnostic latency: {latency}ms</span>
        )}
      </div>

      {alerts.length === 0 ? (
        <p className="empty">No active alerts — waiting for next stream tick.</p>
      ) : (
        <ul className="alert-list">
          {alerts.map((a, i) => (
            <li key={i} className="alert-item">
              <div className="alert-top">
                <span className="alert-type">{a.type.replaceAll("_", " ")}</span>
                {a.sensor && <span className="alert-sensor">{a.sensor}</span>}
              </div>
              <p className="alert-action">{a.corrective_action}</p>
            </li>
          ))}
        </ul>
      )}

      <style jsx>{`
        .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 20px; }
        .panel-head { margin-bottom: 14px; position: relative; }
        .eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--amber); }
        h3 { margin: 4px 0 0; font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .dot.on { background: var(--ok-green); box-shadow: 0 0 6px var(--ok-green); }
        .dot.off { background: var(--alert-red); }
        .latency { display: block; margin-top: 4px; font-family: var(--mono); font-size: 11px; color: var(--text-dim); }
        .empty { font-size: 13px; color: var(--text-dim); }
        .alert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; max-height: 320px; overflow-y: auto; }
        .alert-item { border-left: 2px solid var(--alert-red); background: var(--panel-raised); padding: 10px 12px; border-radius: 4px; }
        .alert-top { display: flex; justify-content: space-between; align-items: center; }
        .alert-type { font-family: var(--mono); font-size: 12px; color: var(--alert-red); text-transform: capitalize; }
        .alert-sensor { font-size: 11px; color: var(--text-dim); text-transform: uppercase; }
        .alert-action { margin: 6px 0 0; font-size: 12px; color: var(--text-dim); line-height: 1.4; }
      `}</style>
    </div>
  );
}
