# Required packages: yfinance, pandas
"""
Fetches stock prices and revenue for tire-sector companies via yfinance
and stores results in SQLite.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent.parent / "db" / "tiresignal.db"
TABLE_PRICES = "stock_prices"
TABLE_REVENUE = "stock_revenue"
CACHE_TTL_DAYS = 7
TICKERS = [
    "GT",    # Goodyear Tire & Rubber
    "CE",    # Cooper-Standard Holdings
    "DKILY", # Nokian Tyres (ADR)
]


def _is_cache_fresh(conn: sqlite3.Connection, table: str) -> bool:
    try:
        row = conn.execute(f"SELECT MAX(fetched_at) FROM {table}").fetchone()
        if row and row[0]:
            fetched_at = datetime.fromisoformat(row[0])
            return datetime.utcnow() - fetched_at < timedelta(days=CACHE_TTL_DAYS)
    except sqlite3.OperationalError:
        pass
    return False


def _load_prices_from_cache(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT date, ticker, close_price FROM {TABLE_PRICES}", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _load_revenue_from_cache(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT date, ticker, revenue FROM {TABLE_REVENUE}", conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fetch_prices() -> pd.DataFrame:
    frames = []
    for ticker in TICKERS:
        raw = yf.download(
            ticker,
            period="5y",
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            print(f"[stocks] Warning: no price data for {ticker}, skipping.")
            continue
        close = raw[["Close"]].copy()
        close.columns = ["close_price"]
        close.index.name = "date"
        close = close.reset_index()
        close["ticker"] = ticker
        frames.append(close[["date", "ticker", "close_price"]])

    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "close_price"])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _fetch_revenue() -> pd.DataFrame:
    frames = []
    for ticker in TICKERS:
        try:
            info = yf.Ticker(ticker)
            income = info.quarterly_income_stmt
            if income is None or income.empty or "Total Revenue" not in income.index:
                print(f"[stocks] Warning: no revenue data for {ticker}, skipping.")
                continue
            series = income.loc["Total Revenue"].dropna()
            chunk = series.reset_index()
            chunk.columns = ["date", "revenue"]
            chunk["ticker"] = ticker
            frames.append(chunk[["date", "ticker", "revenue"]])
        except Exception as exc:
            print(f"[stocks] Warning: could not fetch revenue for {ticker}: {exc}")
            continue

    if not frames:
        return pd.DataFrame(columns=["date", "ticker", "revenue"])
    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _save_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    fetched_at = datetime.utcnow().isoformat()
    conn.execute(f"DROP TABLE IF EXISTS {TABLE_PRICES}")
    conn.execute(
        f"""CREATE TABLE {TABLE_PRICES} (
            date        TEXT NOT NULL,
            ticker      TEXT NOT NULL,
            close_price REAL NOT NULL,
            fetched_at  TEXT NOT NULL
        )"""
    )
    rows = [
        (row.date.isoformat(), row.ticker, float(row.close_price), fetched_at)
        for row in df.itertuples(index=False)
    ]
    conn.executemany(f"INSERT INTO {TABLE_PRICES} VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    print(f"[stocks] Stored {len(rows)} price rows to cache.")


def _save_revenue(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    fetched_at = datetime.utcnow().isoformat()
    conn.execute(f"DROP TABLE IF EXISTS {TABLE_REVENUE}")
    conn.execute(
        f"""CREATE TABLE {TABLE_REVENUE} (
            date       TEXT NOT NULL,
            ticker     TEXT NOT NULL,
            revenue    REAL NOT NULL,
            fetched_at TEXT NOT NULL
        )"""
    )
    rows = [
        (row.date.isoformat(), row.ticker, float(row.revenue), fetched_at)
        for row in df.itertuples(index=False)
    ]
    conn.executemany(f"INSERT INTO {TABLE_REVENUE} VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    print(f"[stocks] Stored {len(rows)} revenue rows to cache.")


def get_stock_data() -> dict[str, pd.DataFrame]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        prices_cached = _is_cache_fresh(conn, TABLE_PRICES)
        revenue_cached = _is_cache_fresh(conn, TABLE_REVENUE)

        if prices_cached and revenue_cached:
            print("[stocks] Loaded from cache (data is less than 7 days old).")
            return {
                "prices": _load_prices_from_cache(conn),
                "revenue": _load_revenue_from_cache(conn),
            }

        if prices_cached:
            print("[stocks] Prices loaded from cache.")
            prices = _load_prices_from_cache(conn)
        else:
            print(f"[stocks] Fetching monthly prices for {TICKERS}...")
            prices = _fetch_prices()
            print(f"[stocks] Fetched {len(prices)} price rows across {prices['ticker'].nunique()} tickers.")
            _save_prices(conn, prices)

        if revenue_cached:
            print("[stocks] Revenue loaded from cache.")
            revenue = _load_revenue_from_cache(conn)
        else:
            print(f"[stocks] Fetching quarterly revenue for {TICKERS}...")
            revenue = _fetch_revenue()
            print(f"[stocks] Fetched {len(revenue)} revenue rows across {revenue['ticker'].nunique()} tickers.")
            _save_revenue(conn, revenue)

        return {"prices": prices, "revenue": revenue}
    finally:
        conn.close()
