"""
Quick SQL Server connection test.

Usage (from Backend folder):
  .\\.venv\\Scripts\\python.exe test_db_connection.py
  .\\test_db_connection.bat
"""

from __future__ import annotations

import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv


def main() -> int:
    # Always load Backend/.env next to this script (not whatever cwd is)
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path)

    server = os.getenv("DB_SERVER", "").strip()
    database = os.getenv("DB_NAME", "").strip()
    username = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASSWORD", "").strip()
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    trust = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes").strip()

    print(f"Python : {sys.executable}")
    print(f".env   : {env_path} ({'found' if os.path.isfile(env_path) else 'MISSING'})")

    missing = [
        name
        for name, val in [
            ("DB_SERVER", server),
            ("DB_NAME", database),
            ("DB_USER", username),
            ("DB_PASSWORD", password),
        ]
        if not val
    ]
    if missing:
        print(f"FAIL: missing .env values: {', '.join(missing)}")
        return 1

    try:
        import pyodbc
        from sqlalchemy import create_engine, text
    except ImportError as exc:
        print(f"FAIL: missing package — {exc}")
        print("Install with:")
        print(r"  .\.venv\Scripts\python.exe -m pip install sqlalchemy pyodbc python-dotenv")
        return 1

    drivers = pyodbc.drivers()
    if driver not in drivers:
        print(f"FAIL: ODBC driver not installed: {driver}")
        print("Installed drivers:")
        for d in drivers:
            print(f"  - {d}")
        return 1

    print(f"Connecting to {server} / {database} as {username} ...")
    print(f"Driver: {driver}")

    odbc = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate={trust};"
    )
    url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"
    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT @@VERSION AS version, "
                    "DB_NAME() AS db_name, "
                    "SUSER_SNAME() AS login_name"
                )
            ).mappings().one()
    except Exception as exc:
        msg = str(exc)
        print("FAIL: connection error")
        if "18456" in msg:
            print("Login failed (SQL 18456): wrong username/password, or SQL auth disabled.")
            print("Update DB_USER / DB_PASSWORD in Backend/.env and retry.")
        elif "Error Locating Server/Instance" in msg:
            print("Named instance not found. Try host only, or host,port (e.g. 10.21.99.58,1433).")
        elif "Login timeout" in msg or "TCP Provider" in msg:
            print("Network timeout. Check VPN, firewall, and that SQL allows remote TCP.")
        print(msg.split("\n")[0])
        return 1

    version_line = str(row["version"]).splitlines()[0]
    print("OK: connected")
    print(f"  database : {row['db_name']}")
    print(f"  login    : {row['login_name']}")
    print(f"  version  : {version_line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
