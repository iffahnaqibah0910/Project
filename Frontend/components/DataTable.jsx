"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchJSON, withQuery } from "../lib/api";

const PAGE_SIZE = 15;
const MC_RATIO_THRESHOLD = 100;

const COLUMNS = [
  { key: "WKDATE", label: "Work Date" },
  { key: "MACHCODE", label: "Machine Code" },
  { key: "MACHNAME", label: "Machine Name" },
  { key: "RUNTIME_SEC", label: "Runtime (sec)" },
  { key: "RUNTIME_HOUR", label: "Runtime (hours)" },
  { key: "DAILY_MC_RATIO", label: "Daily MC Ratio" },
  { key: "FACTORY", label: "Factory" },
];

function isBlank(value) {
  return value == null || (typeof value === "string" && value.trim() === "");
}

function isCellIssue(key, value) {
  if (isBlank(value)) return "missing";
  if (key === "DAILY_MC_RATIO") {
    const n = typeof value === "number" ? value : Number(value);
    if (Number.isFinite(n) && n > MC_RATIO_THRESHOLD) return "abnormal_ratio";
  }
  return null;
}

function rowIssues(row) {
  const issues = {};
  for (const col of COLUMNS) {
    const kind = isCellIssue(col.key, row[col.key]);
    if (kind) issues[col.key] = kind;
  }
  return issues;
}

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
  if (value == null || (typeof value === "string" && value.trim() === "")) return "—";
  if (key === "WKDATE") return formatWorkDate(value);
  if (key === "timestamp") return formatWorkDate(value);
  if (typeof value === "number") return value.toFixed(2);
  return String(value);
}

export default function DataTable({ factory = "" }) {
  const [page, setPage] = useState(1); // 1-based, matches API
  const [jumpInput, setJumpInput] = useState("");
  const [rows, setRows] = useState(null);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setPage(1);
    setRows(null);
    setError(null);
  }, [factory]);

  useEffect(() => {
    const ac = new AbortController();

    async function loadPage() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchJSON(
          withQuery("/api/data", { page, page_size: PAGE_SIZE, factory }),
          { signal: ac.signal },
        );
        if (ac.signal.aborted) return;
        setRows(data.rows);
        setTotal(data.total);
        setTotalPages(Math.max(1, data.total_pages));
        // Clamp if the server reports fewer pages than requested
        if (page > data.total_pages && data.total_pages >= 1) {
          setPage(data.total_pages);
        }
      } catch (e) {
        if (ac.signal.aborted || e.name === "AbortError") return;
        setError(e.message || "Failed to load table");
        setRows([]);
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    }

    loadPage();
    return () => ac.abort();
  }, [page, factory]);

  const annotated = useMemo(
    () => (rows || []).map((row) => ({ row, issues: rowIssues(row) })),
    [rows],
  );

  const issueCount = annotated.filter(({ issues }) => Object.keys(issues).length > 0).length;

  function goToPage(raw) {
    const n = Number.parseInt(String(raw).trim(), 10);
    if (!Number.isFinite(n)) {
      setJumpInput("");
      return;
    }
    const clamped = Math.min(totalPages, Math.max(1, n));
    setPage(clamped);
    setJumpInput("");
  }

  if (rows == null && loading) {
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

  return (
    <div className="panel">
      <div className="panel-head">
        <h3> Data Table </h3>
        <span className="count">
          {factory ? factory : "All factories"} · {total} rows total
          {issueCount > 0 ? ` · ${issueCount} flagged on this page` : ""}
        </span>
      </div>

      {error && <p className="table-error">{error}</p>}

      <div className={`table-wrap${loading ? " is-loading" : ""}`}>
        <table>
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {annotated.map(({ row, issues }, i) => {
              const rowBad = Object.keys(issues).length > 0;
              return (
                <tr key={`${page}-${i}`} className={rowBad ? "row-flagged" : undefined}>
                  {COLUMNS.map((col) => {
                    const kind = issues[col.key];
                    return (
                      <td
                        key={col.key}
                        className={kind ? `cell-flagged cell-${kind}` : undefined}
                        title={
                          kind === "missing"
                            ? "Missing value"
                            : kind === "abnormal_ratio"
                              ? `DAILY_MC_RATIO > ${MC_RATIO_THRESHOLD}`
                              : undefined
                        }
                      >
                        {formatValue(col.key, row[col.key])}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="pager">
        <button disabled={page <= 1 || loading} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          ← Prev
        </button>
        <span className="page-label">
          Page {page} of {totalPages}
        </span>
        <button
          disabled={page >= totalPages || loading}
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
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
            placeholder={String(page)}
            value={jumpInput}
            onChange={(e) => setJumpInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") goToPage(jumpInput);
            }}
            aria-label="Jump to page"
          />
          <button type="button" onClick={() => goToPage(jumpInput)} disabled={!jumpInput.trim() || loading}>
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
        h3 { margin: 4px 0 0; font-size: 16px; font-weight: 600; }
        .count {
          position: absolute;
          top: 2px;
          right: 0;
          font-family: var(--mono);
          font-size: 11px;
          color: var(--text-dim);
        }
        .table-error {
          color: var(--alert-red);
          font-size: 13px;
          margin: 0 0 10px;
        }
        .table-wrap {
          overflow-x: auto;
          border: 1px solid var(--line);
          border-radius: 4px;
        }
        .table-wrap.is-loading { opacity: 0.55; }
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
        tbody tr.row-flagged {
          background: rgba(217, 96, 79, 0.08);
        }
        tbody tr.row-flagged:hover {
          background: rgba(217, 96, 79, 0.14);
        }
        tbody td.cell-flagged {
          color: var(--alert-red);
          font-weight: 600;
          background: rgba(217, 96, 79, 0.16);
        }
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
        .empty { font-size: 13px; color: var(--text-dim); margin: 0; }
      `}</style>
    </div>
  );
}
