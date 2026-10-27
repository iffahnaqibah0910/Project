"use client";

import { useEffect, useState } from "react";

const FIELD_LABELS = {
  RUNTIME_SEC: "Runtime (sec)",
  RUNTIME_HOUR: "Runtime (hours)",
  DAILY_MC_RATIO: "Daily MC ratio",
  MACHCODE: "Machine code",
  MACHNAME: "Machine name",
  WKDATE: "Work date",
  FACTORY: "Factory",
};

function fieldLabel(key) {
  if (!key) return null;
  return FIELD_LABELS[key] || key.replaceAll("_", " ");
}

function formatAgo(ts, now) {
  if (ts == null) return "—";
  const totalSec = Math.max(0, Math.round((now - ts) / 1000));
  if (totalSec < 5) return "Just now";

  const hours = Math.floor(totalSec / 3600);
  const min = Math.floor((totalSec % 3600) / 60);
  const sec = totalSec % 60;
  const parts = [];
  if (hours > 0) parts.push(`${hours}hr`);
  if (min > 0) parts.push(`${min}min`);
  parts.push(`${sec}sec`);
  return parts.join(" ");
}

function toneFor(kind, value) {
  if (value == null) return "";
  if (kind === "alerts") return value > 0 ? "is-bad" : "is-ok";
  if (kind === "missing") return value > 0 ? "is-bad" : "is-ok";
  if (kind === "flagged") return value > 0 ? "is-warn" : "is-ok";
  if (kind === "refresh") return value > 6 * 60 ? "is-warn" : "";
  return "";
}

export default function StatusStrip({
  alertCount,
  connected,
  worstPct,
  worstField,
  missingReady,
  flagged,
  pageRows,
  tableReady,
  lastRefreshAt,
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const refreshAgeSec =
    lastRefreshAt == null ? null : Math.max(0, Math.round((now - lastRefreshAt) / 1000));

  const cards = [
    {
      key: "alerts",
      label: "Active alerts",
      value: alertCount == null ? "—" : String(alertCount),
      hint: connected ? "Live" : "Offline",
      tone: toneFor("alerts", alertCount),
    },
    {
      key: "missing",
      label: "Worst missing",
      value: !missingReady || worstPct == null ? "—" : `${worstPct}%`,
      hint: !missingReady
        ? "Loading"
        : worstPct > 0
          ? fieldLabel(worstField)
          : "No missing values",
      tone: toneFor("missing", missingReady ? worstPct : null),
    },
    {
      key: "flagged",
      label: "Flagged rows",
      value: !tableReady || flagged == null ? "—" : String(flagged),
      hint: !tableReady
        ? "Loading"
        : pageRows != null
          ? `of ${pageRows} on this page`
          : "On this page",
      tone: toneFor("flagged", tableReady ? flagged : null),
    },
    {
      key: "refresh",
      label: "Last refresh",
      value: formatAgo(lastRefreshAt, now),
      hint: "Every 5 minutes",
      tone: toneFor("refresh", refreshAgeSec),
    },
  ];

  return (
    <section className="kpi-strip" aria-label="Dashboard status">
      {cards.map((card) => (
        <article key={card.key} className="kpi-card">
          <span className="kpi-label">{card.label}</span>
          <strong className={`kpi-value ${card.tone}`}>{card.value}</strong>
          <span className="kpi-hint">{card.hint}</span>
        </article>
      ))}

      <style jsx>{`
        .kpi-strip {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 20px;
        }
        .kpi-card {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 6px;
          padding: 14px 16px;
          min-width: 0;
        }
        .kpi-label {
          display: block;
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.06em;
          text-transform: uppercase;
          color: var(--text-dim);
        }
        .kpi-value {
          display: block;
          margin-top: 6px;
          font-size: 22px;
          font-weight: 700;
          letter-spacing: -0.02em;
          line-height: 1.15;
          color: var(--text-primary);
        }
        .kpi-value.is-ok { color: var(--ok-green); }
        .kpi-value.is-bad { color: var(--alert-red); }
        .kpi-value.is-warn { color: var(--amber); }
        .kpi-hint {
          display: block;
          margin-top: 6px;
          font-size: 12px;
          color: var(--text-dim);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        @media (max-width: 960px) {
          .kpi-strip {
            grid-template-columns: 1fr 1fr;
          }
        }
      `}</style>
    </section>
  );
}
