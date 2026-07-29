"""
Single point of truth for 'where does the raw data come from'.

Right now it returns mock data. When SQL Server is ready, replace the body
of get_raw_data() with a pyodbc/SQLAlchemy query that returns a DataFrame
with the same columns (timestamp, temperature, pressure, vibration, rpm,
machine_state, machine_id) — nothing else in the app needs to change.
"""

from functools import lru_cache

import pandas as pd

from mockdata import generate_raw_stream

USE_MOCK = True  # flip to False once SQL Server wiring is in place


def get_raw_data() -> pd.DataFrame:
    if USE_MOCK:
        return generate_raw_stream()

    # --- Real SQL Server version (fill in later) ---
    # import sqlalchemy as sa
    # engine = sa.create_engine(
    #     "mssql+pyodbc://<user>:<password>@<server>/<db>?driver=ODBC+Driver+18+for+SQL+Server"
    # )
    # query = "SELECT * FROM dbo.MachineStream ORDER BY timestamp"
    # return pd.read_sql(query, engine)
    raise NotImplementedError("SQL Server connection not wired up yet")