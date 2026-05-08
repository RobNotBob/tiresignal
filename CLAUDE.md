# TireSignal

A tire industry demand forecasting tool. It aggregates signals from multiple public data sources to produce a forward-looking demand estimate for the tire market, rendered as a self-contained HTML report.

## Purpose

TireSignal helps analysts and investors understand near-term tire demand by synthesizing:
- **Google Trends** — search interest in tire-related queries as a leading consumer demand signal
- **FRED** — macroeconomic indicators (vehicle miles traveled, CPI, fuel prices, new vehicle sales)
- **yfinance** — stock price and volume data for publicly traded tire manufacturers and distributors
- **SEC EDGAR** — quarterly earnings and inventory disclosures from major tire companies

## Stack

- **Language**: Python 3.11+
- **Database**: SQLite (stored in `db/tiresignal.db`)
- **Output**: HTML report at `output/report.html`

## Entry Point

```
python run.py
```

`run.py` orchestrates the full pipeline: fetch → store → analyze → report.

## Project Layout

```
tiresignal/
├── run.py                  # Pipeline entry point
├── db/                     # SQLite database files
├── output/                 # Generated HTML report
├── data/
│   ├── fetch_trends.py     # Google Trends fetcher (pytrends)
│   ├── fetch_fred.py       # FRED API fetcher (fredapi)
│   ├── fetch_stocks.py     # Stock data fetcher (yfinance)
│   └── fetch_edgar.py      # SEC EDGAR fetcher (requests + BeautifulSoup)
├── analysis/
│   └── forecast.py         # Demand forecast model
└── report/
    └── build_report.py     # HTML report builder
```

## Data Flow

1. Each `data/fetch_*.py` module pulls raw data from its source and writes to SQLite tables.
2. `analysis/forecast.py` reads from SQLite, combines signals, and produces a forecast.
3. `report/build_report.py` reads forecast output and renders `output/report.html`.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `FRED_API_KEY` | API key for the FRED data service |

Google Trends, yfinance, and SEC EDGAR do not require API keys.
