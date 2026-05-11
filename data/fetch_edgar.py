# Required packages: requests, pandas
"""
Fetches quarterly revenue for Goodyear Tire & Rubber from SEC EDGAR
company facts API and stores results in SQLite.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent.parent / "db" / "tiresignal.db"
TABLE = "edgar_revenue"
CACHE_TTL_DAYS = 7

GOODYEAR_CIK = "0000042582"
EDGAR_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{GOODYEAR_CIK}.json"
HEADERS = {"User-Agent": "TireSignal/1.0 contact@example.com"}

# Prefer the more specific concept; fall back to the broader one
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
]
QUARTERLY_FORMS = {"10-Q", "10-K"}


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
    df = pd.read_sql(f"SELECT date, revenue, form_type FROM {TABLE}", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fetch_from_edgar() -> pd.DataFrame:
    resp = requests.get(EDGAR_URL, headers=HEADERS, timeout=(10, 30))
    resp.raise_for_status()
    facts = resp.json().get("facts", {}).get("us-gaap", {})

    units = None
    chosen_concept = None
    for concept in REVENUE_CONCEPTS:
        if concept in facts:
            units = facts[concept].get("units", {}).get("USD")
            chosen_concept = concept
            break

    if not units:
        raise ValueError(
            f"Neither of {REVENUE_CONCEPTS} found in EDGAR facts for CIK {GOODYEAR_CIK}"
        )

    print(f"[edgar] Using concept: {chosen_concept}")
    rows = []
    for entry in units:
        form = entry.get("form", "")
        if form not in QUARTERLY_FORMS:
            continue
        # 'end' is the period end date; skip instant/point-in-time entries
        end = entry.get("end")
        val = entry.get("val")
        if end and val is not None:
            rows.append({
                "date": pd.to_datetime(end),
                "revenue": float(val),
                "form_type": form,
            })

    if not rows:
        raise ValueError("No quarterly revenue entries found in EDGAR response")

    df = pd.DataFrame(rows).drop_duplicates(subset=["date", "form_type"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _save_to_db(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    fetched_at = datetime.utcnow().isoformat()
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
    conn.execute(
        f"""CREATE TABLE {TABLE} (
            date       TEXT NOT NULL,
            revenue    REAL NOT NULL,
            form_type  TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        )"""
    )
    rows = [
        (row.date.isoformat(), row.revenue, row.form_type, fetched_at)
        for row in df.itertuples(index=False)
    ]
    conn.executemany(f"INSERT INTO {TABLE} VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    print(f"[edgar] Stored {len(rows)} rows to cache.")


def get_edgar_revenue() -> pd.DataFrame:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        if _is_cache_fresh(conn):
            print("[edgar] Loaded from cache (data is less than 7 days old).")
            return _load_from_cache(conn)

        print(f"[edgar] Fetching Goodyear revenue from SEC EDGAR (CIK {GOODYEAR_CIK})...")
        df = _fetch_from_edgar()
        print(f"[edgar] Fetched {len(df)} quarterly revenue entries.")
        _save_to_db(conn, df)
        return df[["date", "revenue", "form_type"]]
    finally:
        conn.close()
