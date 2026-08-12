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
from sqlalchemy import create_engine

load_dotenv()

# Expected columns from dbo.RPT_MRR_Daily_Summary_ByFac_Result.
# TOP keeps dashboard payloads browser-friendly (~33k full table is too large).
DEFAULT_QUERY = (
    "SELECT TOP 2000 MACHCODE, WKDATE, MACHNAME, RUNTIME_SEC, RUNTIME_HOUR, "
    "DAILY_MC_RATIO, FACTORY "
    "FROM dbo.RPT_MRR_Daily_Summary_ByFac_Result "
    "ORDER BY WKDATE DESC, MACHCODE"
)


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
    return create_engine(url, pool_pre_ping=True)


def get_raw_data() -> pd.DataFrame:
    query = os.getenv("DB_QUERY", DEFAULT_QUERY).strip() or DEFAULT_QUERY
    return pd.read_sql(query, _get_engine())
