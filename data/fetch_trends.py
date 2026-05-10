# Required packages: requests, pandas
"""
Fetches tire-related search interest from Google Trends via direct CSV export
and stores results in SQLite. Falls back to SYNTHETIC data if the live fetch fails.
"""

import csv
import random
import sqlite3
import time
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import requests

DB_PATH = Path(__file__).parent.parent / "db" / "tiresignal.db"
KEYWORDS = ["tire", "winter tires", "tire deals"]
TABLE = "trends"
CACHE_TTL_DAYS = 7

_TRENDS_URL = "https://trends.google.com/trends/explore/csvHeader"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://trends.google.com/",
}

# Seasonal index by month (Jan–Dec) reflecting tire search patterns
_SEASONAL = [75, 72, 82, 88, 85, 78, 70, 68, 78, 90, 88, 80]


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
    df = pd.read_sql(f"SELECT date, keyword, interest FROM {TABLE}", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _parse_trends_csv(text: str, keyword: str) -> pd.DataFrame:
    lines = text.splitlines()
    data_start = next(
        (i for i, line in enumerate(lines) if line.startswith("Week,")), None
    )
    if data_start is None:
        return pd.DataFrame(columns=["date", "keyword", "interest"])

    reader = csv.reader(lines[data_start:])
    next(reader)  # skip "Week, <keyword>" header row
    rows = []
    for row in reader:
        if len(row) >= 2 and row[0] and row[1].strip().isdigit():
            rows.append({
                "date": pd.to_datetime(row[0]),
                "keyword": keyword,
                "interest": int(row[1]),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["date", "keyword", "interest"])


def _fetch_live() -> tuple[pd.DataFrame, str]:
    session = requests.Session()
    session.headers.update(_HEADERS)
    frames = []
    for i, keyword in enumerate(KEYWORDS):
        if i > 0:
            delay = random.uniform(5, 15)
            print(f"[trends] Waiting {delay:.1f}s before next keyword request...")
            time.sleep(delay)
        resp = session.get(
            _TRENDS_URL,
            params={"q": keyword, "geo": "US", "date": "today 5-y"},
            timeout=(10, 25),
        )
        resp.raise_for_status()
        chunk = _parse_trends_csv(resp.text, keyword)
        if not chunk.empty:
            frames.append(chunk)

    if not frames:
        raise ValueError("Google Trends returned no parseable data for any keyword")
    return pd.concat(frames, ignore_index=True), "live"


def _generate_synthetic() -> tuple[pd.DataFrame, str]:
    today = datetime.utcnow().date()
    start = today - timedelta(weeks=260)
    weeks: list[date] = []
    d = start
    while d <= today:
        weeks.append(d)
        d += timedelta(weeks=1)

    base = {"tire": 65, "winter tires": 28, "tire deals": 38}
    rng = random.Random(0xBEEF)
    rows = []
    for keyword in KEYWORDS:
        b = base.get(keyword, 50)
        for d in weeks:
            seasonal_scale = _SEASONAL[d.month - 1] / 80
            noise = rng.uniform(-8, 8)
            interest = max(1, min(100, int(b * seasonal_scale + noise)))
            rows.append({"date": pd.to_datetime(d), "keyword": keyword, "interest": interest})
    return pd.DataFrame(rows), "SYNTHETIC"


def _save_to_db(conn: sqlite3.Connection, df: pd.DataFrame, source: str) -> None:
    fetched_at = datetime.utcnow().isoformat()
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}")
    conn.execute(
        f"""CREATE TABLE {TABLE} (
            date     TEXT NOT NULL,
            keyword  TEXT NOT NULL,
            interest INTEGER NOT NULL,
            fetched_at TEXT NOT NULL,
            source   TEXT NOT NULL
        )"""
    )
    rows = [
        (row.date.isoformat(), row.keyword, int(row.interest), fetched_at, source)
        for row in df.itertuples(index=False)
    ]
    conn.executemany(f"INSERT INTO {TABLE} VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    print(f"[trends] Stored {len(rows)} rows to cache (source={source}).")


def get_trends_data() -> pd.DataFrame:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        if _is_cache_fresh(conn):
            print("[trends] Loaded from cache (data is less than 7 days old).")
            return _load_from_cache(conn)

        print("[trends] Fetching fresh data from Google Trends...")
        try:
            df, source = _fetch_live()
            print(f"[trends] Live fetch succeeded ({len(df)} rows).")
        except Exception as exc:
            print(f"[trends] Live fetch failed: {exc}")
            print("[trends] Falling back to SYNTHETIC data.")
            df, source = _generate_synthetic()

        _save_to_db(conn, df, source)
        return df[["date", "keyword", "interest"]]
    finally:
        conn.close()
