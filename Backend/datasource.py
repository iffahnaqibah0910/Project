"""
Single point of truth for 'where does the raw data come from'.

Reads from SQL Server. Set connection details in a .env file
(see .env.example) — nothing else in the app needs to change.
"""

import os
from functools import lru_cache
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

TABLE = "dbo.RPT_MRR_Daily_Summary_ByFac_Result"
COLUMNS = (
    "MACHCODE, WKDATE, MACHNAME, RUNTIME_SEC, RUNTIME_HOUR, "
    "DAILY_MC_RATIO, FACTORY"
)

# Recent sample for rolling time series charts for EDA (kept small for the Next proxy).
DEFAULT_QUERY = (
    f"SELECT TOP 2000 {COLUMNS} "
    f"FROM {TABLE} "
    "ORDER BY WKDATE DESC, MACHCODE"
)

COUNT_QUERY = f"SELECT COUNT(*) AS n FROM {TABLE}"

# Full-table rows that should always feed detection (alerts / missingness),
# even when they fall outside the recent TOP-N EDA window.
ANOMALY_PREDICATE = (
    "DAILY_MC_RATIO > 100 "
    "   OR RUNTIME_SEC IS NULL "
    "   OR DAILY_MC_RATIO IS NULL "
    "   OR WKDATE IS NULL "
    "   OR MACHCODE IS NULL OR LTRIM(RTRIM(MACHCODE)) = '' "
    "   OR MACHNAME IS NULL OR LTRIM(RTRIM(MACHNAME)) = '' "
    "   OR FACTORY IS NULL OR LTRIM(RTRIM(FACTORY)) = '' "
    "   OR RUNTIME_HOUR IS NULL "
    "   OR LTRIM(RTRIM(CONVERT(varchar(50), RUNTIME_HOUR))) = ''"
)

ANOMALY_QUERY = (
    f"SELECT {COLUMNS} "
    f"FROM {TABLE} "
    f"WHERE {ANOMALY_PREDICATE} "
    "ORDER BY WKDATE DESC, MACHCODE"
)

# Exact missingness over the whole table (not just the recent sample).
MISSINGNESS_SELECT = f"""
SELECT
  COUNT_BIG(*) AS n,
  SUM(CASE WHEN MACHCODE IS NULL OR LTRIM(RTRIM(MACHCODE)) = '' THEN 1 ELSE 0 END) AS MACHCODE,
  SUM(CASE WHEN WKDATE IS NULL THEN 1 ELSE 0 END) AS WKDATE,
  SUM(CASE WHEN MACHNAME IS NULL OR LTRIM(RTRIM(MACHNAME)) = '' THEN 1 ELSE 0 END) AS MACHNAME,
  SUM(CASE WHEN RUNTIME_SEC IS NULL THEN 1 ELSE 0 END) AS RUNTIME_SEC,
  SUM(CASE WHEN RUNTIME_HOUR IS NULL
            OR LTRIM(RTRIM(CONVERT(varchar(50), RUNTIME_HOUR))) = '' THEN 1 ELSE 0 END) AS RUNTIME_HOUR,
  SUM(CASE WHEN DAILY_MC_RATIO IS NULL THEN 1 ELSE 0 END) AS DAILY_MC_RATIO,
  SUM(CASE WHEN FACTORY IS NULL OR LTRIM(RTRIM(FACTORY)) = '' THEN 1 ELSE 0 END) AS FACTORY
FROM {TABLE}
"""
MISSINGNESS_QUERY = MISSINGNESS_SELECT


def normalize_factory(factory: str | None) -> str | None:
    """Empty / 'all' means no factory filter."""
    if factory is None:
        return None
    value = str(factory).strip()
    if not value or value.lower() in {"all", "*"}:
        return None
    return value


def _factory_clause(factory: str | None, *, has_where: bool = False) -> tuple[str, dict]:
    factory = normalize_factory(factory)
    if not factory:
        return "", {}
    joiner = " AND " if has_where else " WHERE "
    return f"{joiner}LTRIM(RTRIM(FACTORY)) = :factory", {"factory": factory}


def _filter_df_factory(df: pd.DataFrame, factory: str | None) -> pd.DataFrame:
    factory = normalize_factory(factory)
    if not factory or df is None or df.empty or "FACTORY" not in df.columns:
        return df
    mask = df["FACTORY"].map(
        lambda v: str(v).strip() == factory if pd.notna(v) else False
    )
    return df.loc[mask].reset_index(drop=True)


def get_factory_names() -> list[str]:
    """Distinct factory codes for the dashboard dropdown."""
    query = (
        f"SELECT DISTINCT LTRIM(RTRIM(FACTORY)) AS FACTORY "
        f"FROM {TABLE} "
        "WHERE FACTORY IS NOT NULL AND LTRIM(RTRIM(FACTORY)) <> '' "
        "ORDER BY FACTORY"
    )
    df = pd.read_sql(text(query), _get_engine())
    names = []
    seen = set()
    for value in df["FACTORY"].tolist():
        name = str(value).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


@lru_cache(maxsize=1)
def _get_engine():
    server = os.getenv("DB_SERVER", "").strip()
    database = os.getenv("DB_NAME", "").strip()
    username = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASSWORD", "").strip()
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    # TrustServerCertificate=yes is common for local/dev; turn off in prod if you use a real cert
    trust = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes").strip()

    missing = [name for name, val in [
        ("DB_SERVER", server),
        ("DB_NAME", database),
        ("DB_USER", username),
        ("DB_PASSWORD", password),
    ] if not val]
    if missing:
        raise RuntimeError(
            f"Missing SQL Server settings in .env: {', '.join(missing)}"
        )

    odbc = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate={trust};"
    )
    url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"
    # Keep a small pool; long SQL over VPN previously exhausted hang-prone
    # connections and froze uvicorn when sync handlers blocked the loop.
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=30,
    )


def get_raw_data(factory: str | None = None) -> pd.DataFrame:
    """Recent sample used by rolling EDA charts."""
    factory = normalize_factory(factory)
    custom = (os.getenv("DB_QUERY") or "").strip()
    if custom:
        return _filter_df_factory(pd.read_sql(custom, _get_engine()), factory)

    clause, params = _factory_clause(factory)
    query = (
        f"SELECT TOP 2000 {COLUMNS} "
        f"FROM {TABLE}{clause} "
        "ORDER BY WKDATE DESC, MACHCODE"
    )
    if params:
        return pd.read_sql(text(query), _get_engine(), params=params)
    return pd.read_sql(query, _get_engine())


def get_anomaly_rows(factory: str | None = None) -> pd.DataFrame:
    """Full-table rows with null/blank fields or DAILY_MC_RATIO > 100."""
    clause, params = _factory_clause(factory, has_where=True)
    query = (
        f"SELECT {COLUMNS} "
        f"FROM {TABLE} "
        f"WHERE ({ANOMALY_PREDICATE}){clause} "
        "ORDER BY WKDATE DESC, MACHCODE"
    )
    if params:
        return pd.read_sql(text(query), _get_engine(), params=params)
    return pd.read_sql(text(query), _get_engine())


def get_detection_data(factory: str | None = None) -> pd.DataFrame:
    """Recent sample plus full-table anomaly rows (deduped) for rule checks."""
    recent = get_raw_data(factory)
    anomalies = get_anomaly_rows(factory)
    if anomalies.empty:
        return recent
    combined = pd.concat([recent, anomalies], ignore_index=True)
    return combined.drop_duplicates(
        subset=["MACHCODE", "WKDATE", "FACTORY"],
        keep="last",
    ).reset_index(drop=True)


def get_full_missingness(factory: str | None = None) -> tuple[dict, dict, int]:
    """Exact Mp + absolute missing counts over the entire SQL table.

    Returns (missingness_pct, missing_counts, total_rows).
    """
    clause, params = _factory_clause(factory)
    query = f"{MISSINGNESS_SELECT.rstrip()}{clause}"
    with _get_engine().connect() as conn:
        row = dict(conn.execute(text(query), params).mappings().one())

    total = int(row.pop("n") or 0)
    counts = {col: int(row.get(col) or 0) for col in (
        "MACHCODE", "WKDATE", "MACHNAME", "RUNTIME_SEC",
        "RUNTIME_HOUR", "DAILY_MC_RATIO", "FACTORY",
    )}
    mp = {
        col: round((cnt / total) * 100, 4) if total else 0.0
        for col, cnt in counts.items()
    }
    return mp, counts, total


def get_data_count(factory: str | None = None) -> int:
    """Total rows in the source table (full table, not the analytics sample)."""
    clause, params = _factory_clause(factory)
    query = f"SELECT COUNT(*) AS n FROM {TABLE}{clause}"
    with _get_engine().connect() as conn:
        n = conn.execute(text(query), params).scalar()
    return int(n or 0)


def get_data_page(
    page: int = 1,
    page_size: int = 15,
    factory: str | None = None,
) -> tuple[pd.DataFrame, int]:
    """One page of the full table, newest WKDATE first. page is 1-based.

    Page 1 prepends full-table anomaly rows (missing values /
    DAILY_MC_RATIO > 100) so they are visible and can be highlighted
    without a slow table-wide ORDER BY CASE scan.
    """
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))
    factory = normalize_factory(factory)
    total = get_data_count(factory)

    anomalies = get_anomaly_rows(factory) if page == 1 else pd.DataFrame()
    anomaly_n = 0 if anomalies.empty else len(anomalies)
    # Reserve slots on page 1 for anomalies, then fill with normal rows.
    normal_limit = page_size if page > 1 else max(0, page_size - anomaly_n)
    normal_offset = 0 if page == 1 else max(0, (page - 1) * page_size - anomaly_n)

    clause, factory_params = _factory_clause(factory)
    page_query = (
        f"SELECT {COLUMNS} "
        f"FROM {TABLE}{clause} "
        "ORDER BY WKDATE DESC, MACHCODE "
        "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
    )

    if normal_limit > 0:
        normal = pd.read_sql(
            text(page_query),
            _get_engine(),
            params={
                "offset": int(normal_offset),
                "limit": int(normal_limit),
                **factory_params,
            },
        )
    else:
        normal = pd.DataFrame()

    if page == 1 and not anomalies.empty:
        if not normal.empty:
            keys = ["MACHCODE", "WKDATE", "FACTORY"]
            merged = normal.merge(
                anomalies[keys].drop_duplicates(),
                on=keys,
                how="left",
                indicator=True,
            )
            normal = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
        df = pd.concat([anomalies, normal], ignore_index=True).head(page_size)
    else:
        df = normal

    return df, total
