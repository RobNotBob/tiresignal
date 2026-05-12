# Required packages: fredapi, pandas
"""
Fetches macroeconomic indicators from the FRED API via fredapi
and stores results in SQLite.

Requires env var: FRED_API_KEY
"""

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fredapi import Fred

DB_PATH = Path(__file__).parent.parent / "db" / "tiresignal.db"
TABLE = "fred_indicators"
CACHE_TTL_DAYS = 7
SERIES = [
    "TRFVOLUSM227NFWA",  # vehicle miles traveled (monthly)
    "CUUR0000SAT1",      # CPI for motor vehicle parts (monthly)
    "UMCSENT",           # University of Michigan consumer sentiment (monthly)
]


def _is_cache_fresh(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(f"SELECT MAX(fetched_at) FROM {TABLE}").fetchone()
        if row and row[0]:
            fetched_at = datetime.fromisoformat(row[0])
            return datetime.utcnow() - fetched_at < timedelta(days=CACHE_TTL_DAYS)
    except sqlite3.OperationalError:
        pass
    return False


def _load_from_cache(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT date, series_id, value FROM {TABLE}", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fetch_from_fred(api_key: str) -> pd.DataFrame:
    fred = Fred(api_key=api_key)
    frames = []
    for series_id in SERIES:
        raw = fred.get_series(series_id)
        chunk = raw.dropna().reset_index()
        chunk.columns = ["date", "value"]
        chunk["series_id"] = series_id
        frames.append(chunk[["date", "series_id", "value"]])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _save_to_db(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    fetched_at = datetime.utcnow().isoformat()
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
    conn.execute(
        f"""CREATE TABLE {TABLE} (
            date      TEXT NOT NULL,
            series_id TEXT NOT NULL,
            value     REAL NOT NULL,
            fetched_at TEXT NOT NULL
        )"""
    )
    rows = [
        (row.date.isoformat(), row.series_id, float(row.value), fetched_at)
        for row in df.itertuples(index=False)
    ]
    conn.executemany(f"INSERT INTO {TABLE} VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    print(f"[fred] Stored {len(rows)} rows to cache.")


def get_fred_data(force_refresh: bool = False) -> pd.DataFrame:
    api_key = os.environ["FRED_API_KEY"]
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        if not force_refresh and _is_cache_fresh(conn):
            print("[fred] Loaded from cache (data is less than 7 days old).")
            return _load_from_cache(conn)

        print(f"[fred] Fetching {len(SERIES)} series from FRED...")
        df = _fetch_from_fred(api_key)
        print(f"[fred] Fetched {len(df)} rows across {df['series_id'].nunique()} series.")
        _save_to_db(conn, df)
        return df[["date", "series_id", "value"]]
    finally:
        conn.close()
