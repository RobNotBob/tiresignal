"""
Fetches stock price and volume data for tire-sector companies via yfinance
and stores results in SQLite.
"""

# Tire manufacturers and distributors to track
TICKERS = [
    "GT",   # Goodyear Tire & Rubber
    "CTB",  # Cooper Tire (now part of Goodyear)
    "MGA",  # Magna (auto components proxy)
]


def fetch_stocks():
    # TODO: use yfinance.download() to pull daily OHLCV for TICKERS
    # over a rolling 1-year window, then write to the
    # 'stocks' table in db/tiresignal.db
    pass
