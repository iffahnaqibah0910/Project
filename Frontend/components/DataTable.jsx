"use client";

import { useState } from "react";

const PAGE_SIZE = 15;

const COLUMNS = [
  { key: "WKDATE", label: "Work Date" },
  { key: "MACHCODE", label: "Machine Code" },
  { key: "MACHNAME", label: "Machine Name" },
  { key: "RUNTIME_SEC", label: "Runtime (sec)" },
  { key: "RUNTIME_HOUR", label: "Runtime (hours)" },
  { key: "DAILY_MC_RATIO", label: "Daily MC Ratio" },
  { key: "FACTORY", label: "Factory" },
];

function formatWorkDate(value) {
  if (value == null || value === "") return "—";
  const s = String(value).trim();

  // Raw SQL WKDATE: "20260810"
  if (/^\d{8}$/.test(s)) {
    const y = s.slice(0, 4);
    const m = s.slice(4, 6);
    const d = s.slice(6, 8);
    return formatYmd(y, m, d);
  }

  // ISO date or datetime from API: "2026-08-10" / "2026-08-10T00:00:00"
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return formatYmd(iso[1], iso[2], iso[3]);

  const dt = new Date(s);
  if (!Number.isNaN(dt.getTime())) {
    return dt.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "2-digit",
    });
  }
  return s;
}

function formatYmd(y, m, d) {
  const dt = new Date(Number(y), Number(m) - 1, Number(d));
  return dt.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

function formatValue(key, value) {
  if (value == null) return "—";
  if (key === "WKDATE") return formatWorkDate(value);
  if (key === "timestamp") return formatWorkDate(value);
  if (typeof value === "number") return value.toFixed(2);
  return String(value);
}

export default function DataTable({ data }) {
  const [page, setPage] = useState(0);
  const [jumpInput, setJumpInput] = useState("");

  if (!data) {
    return (
      <div className="panel">
        <p className="empty">Loading data…</p>
        <style jsx>{`
          .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 20px; }
          .empty { font-size: 13px; color: var(--text-dim); margin: 0; }
        `}</style>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const start = safePage * PAGE_SIZE;
  const rows = data.slice(start, start + PAGE_SIZE);

  function goToPage(raw) {
    const n = Number.parseInt(String(raw).trim(), 10);
    if (!Number.isFinite(n)) {
      setJumpInput("");
      return;
    }
    const clamped = Math.min(totalPages, Math.max(1, n));
    setPage(clamped - 1);
    setJumpInput("");
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h3> Data Table </h3>
        <span className="count">{data.length} rows total</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={start + i}>
                {COLUMNS.map((col) => (
                  <td key={col.key} className={col.key === "machine_state" ? `state state-${row[col.key]}` : ""}>
                    {formatValue(col.key, row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button disabled={safePage === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
          ← Prev
        </button>
        <span className="page-label">
          Page {safePage + 1} of {totalPages}
        </span>
        <button
          disabled={safePage >= totalPages - 1}
          onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
        >
          Next →
        </button>
        <label className="jump">
          <span>Jump to</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            inputMode="numeric"
            placeholder={String(safePage + 1)}
            value={jumpInput}
            onChange={(e) => setJumpInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") goToPage(jumpInput);
            }}
            aria-label="Jump to page"
          />
          <button type="button" onClick={() => goToPage(jumpInput)} disabled={!jumpInput.trim()}>
            Go
          </button>
        </label>
      </div>

      <style jsx>{`
        .panel {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 6px;
          padding: 20px;
        }
        .panel-head { margin-bottom: 14px; position: relative; }
        .eyebrow {
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--amber);
        }
        h3 { margin: 4px 0 0; font-size: 16px; font-weight: 600; }
        .count {
          position: absolute;
          top: 2px;
          right: 0;
          font-family: var(--mono);
          font-size: 11px;
          color: var(--text-dim);
        }
        .table-wrap {
          overflow-x: auto;
          border: 1px solid var(--line);
          border-radius: 4px;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12.5px;
        }
        thead th {
          text-align: left;
          padding: 10px 12px;
          background: var(--panel-raised);
          color: var(--text-dim);
          font-family: var(--mono);
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          border-bottom: 1px solid var(--line);
          white-space: nowrap;
        }
        tbody td {
          padding: 8px 12px;
          border-bottom: 1px solid var(--line);
          font-family: var(--mono);
          color: var(--text-primary);
          white-space: nowrap;
        }
        tbody tr:last-child td { border-bottom: none; }
        tbody tr:hover { background: var(--panel-raised); }
        .state-running { color: var(--ok-green); }
        .state-stopped { color: var(--alert-red); }
        .state-idle { color: var(--amber); }
        .pager {
          display: flex;
          align-items: center;
          justify-content: center;
          flex-wrap: wrap;
          gap: 16px;
          margin-top: 14px;
        }
        .pager button {
          background: var(--panel-raised);
          border: 1px solid var(--line);
          color: var(--text-primary);
          padding: 6px 14px;
          border-radius: 4px;
          font-size: 12px;
          cursor: pointer;
        }
        .pager button:disabled {
          opacity: 0.35;
          cursor: not-allowed;
        }
        .pager button:not(:disabled):hover {
          border-color: var(--amber);
          color: var(--amber);
        }
        .page-label {
          font-family: var(--mono);
          font-size: 12px;
          color: var(--text-dim);
        }
        .jump {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-family: var(--mono);
          font-size: 12px;
          color: var(--text-dim);
        }
        .jump input {
          width: 64px;
          background: var(--panel-raised);
          border: 1px solid var(--line);
          color: var(--text-primary);
          border-radius: 4px;
          padding: 6px 8px;
          font-family: var(--mono);
          font-size: 12px;
        }
        .jump input:focus {
          outline: none;
          border-color: var(--amber);
        }
        .jump input::-webkit-outer-spin-button,
        .jump input::-webkit-inner-spin-button {
          -webkit-appearance: none;
          margin: 0;
        }
        .jump input[type="number"] {
          -moz-appearance: textfield;
        }
      `}</style>
    </div>
  );
}