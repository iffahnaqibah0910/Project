"use client";

export default function MissingnessPanel({ missingness }) {
  if (!missingness) return null;
  const { missingness_pct, schema_violations } = missingness;

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="eyebrow">Phase 1</span>
        <h3>Missingness (Mp)</h3>
      </div>
      <div className="mp-grid">
        {Object.entries(missingness_pct).map(([sensor, pct]) => (
          <div className="mp-row" key={sensor}>
            <span className="mp-label">{sensor}</span>
            <div className="mp-bar-track">
              <div
                className="mp-bar-fill"
                style={{ width: `${Math.min(pct, 100)}%`, background: pct > 10 ? "var(--alert-red)" : "var(--ok-green)" }}
              />
            </div>
            <span className="mp-value">{pct}%</span>
          </div>
        ))}
      </div>

      {schema_violations?.length > 0 && (
        <div className="violations">
          <span className="eyebrow">{schema_violations.length} schema violation(s)</span>
          <ul>
            {schema_violations.slice(0, 5).map((v, i) => (
              <li key={i}>
                row {v.row} · <code>{v.column}</code> · {v.issue} (<code>{String(v.value)}</code>)
              </li>
            ))}
          </ul>
        </div>
      )}

      <style jsx>{`
        .panel {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 6px;
          padding: 20px;
        }
        .panel-head { margin-bottom: 14px; }
        .eyebrow {
          font-family: var(--mono);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--amber);
        }
        h3 { margin: 4px 0 0; font-size: 16px; font-weight: 600; }
        .mp-grid { display: flex; flex-direction: column; gap: 10px; }
        .mp-row { display: grid; grid-template-columns: 90px 1fr 48px; align-items: center; gap: 10px; }
        .mp-label { font-size: 13px; color: var(--text-dim); text-transform: capitalize; }
        .mp-bar-track {
          height: 6px;
          background: var(--panel-raised);
          border-radius: 3px;
          overflow: hidden;
        }
        .mp-bar-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
        .mp-value { font-family: var(--mono); font-size: 12px; text-align: right; }
        .violations {
          margin-top: 18px;
          padding-top: 14px;
          border-top: 1px solid var(--line);
        }
        .violations ul { margin: 8px 0 0; padding-left: 16px; }
        .violations li { font-size: 12px; color: var(--text-dim); margin-bottom: 4px; font-family: var(--mono); }
        code { color: var(--text-primary); }
      `}</style>
    </div>
  );
}
