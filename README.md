# TireSignal

A tire industry demand forecasting tool that aggregates public data signals into a forward-looking market outlook.

## Overview

TireSignal pulls data from four public sources — Google Trends, FRED, Yahoo Finance, and SEC EDGAR — stores them in a local SQLite cache, and fits a linear regression model to produce a 6-month demand forecast. The output is a fully self-contained HTML report with interactive charts that requires no server to view. The tool is designed for analysts and investors who want a repeatable, data-driven read on near-term tire market conditions without manual data wrangling.

## Architecture

```
Google Trends ─┐
               │
FRED           ├──► SQLite cache ──► Linear regression ──► output/report.html
               │    (db/tiresignal.db)   model
yfinance       ┤
               │
SEC EDGAR ─────┘
```

Each data source writes to its own table in `db/tiresignal.db`. The forecast model reads all four tables, aligns them to a monthly time index, and produces historical fit + 6-month forward projections. The report renders everything as a self-contained HTML file with Chart.js charts.

## Data Sources

| Source | Table | Contribution |
|--------|-------|-------------|
| **Google Trends** | `trends` | Weekly US search interest for "tire", "winter tires", and "tire deals" — a leading consumer demand signal |
| **FRED** | `fred_indicators` | Three monthly macro series: vehicle miles traveled (TRFVOLUSM227NFWA), CPI for motor vehicle parts (CUUR0000SAT1), and University of Michigan consumer sentiment (UMCSENT) |
| **yfinance** | `stock_prices`, `stock_revenue` | Monthly closing prices and quarterly revenue for Goodyear (GT), Cooper-Standard (CE), and Nokian (DKILY) — market pricing as a forward-looking demand proxy |
| **SEC EDGAR** | `edgar_revenue` | Quarterly revenue from Goodyear's 10-Q and 10-K filings via the EDGAR company facts API |

## Setup

**1. Clone the repository**
```bash
git clone <repo-url>
cd tiresignal
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Get a free FRED API key**

Register at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html). It's free and instant.

**4. Create your `.env` file**
```bash
cp .env.example .env
```
Edit `.env` and add your key:
```
FRED_API_KEY=your_key_here
```

**5. Run the pipeline**
```bash
python3 run.py
```

Open `output/report.html` in any browser when it finishes.

## Usage

```bash
# Normal run — uses cached data if less than 7 days old
python3 run.py

# Force re-fetch all data sources regardless of cache age
python3 run.py --refresh

# Skip fetching entirely — rebuild forecast and report from cached SQLite data
python3 run.py --no-fetch
```

## Project Structure

```
tiresignal/
├── run.py                  # Pipeline entry point and CLI
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── db/
│   └── tiresignal.db       # SQLite cache (created on first run)
├── output/
│   └── report.html         # Generated HTML report
├── data/
│   ├── fetch_trends.py     # Google Trends fetcher (falls back to synthetic data)
│   ├── fetch_fred.py       # FRED macroeconomic indicator fetcher
│   ├── fetch_stocks.py     # yfinance stock price and revenue fetcher
│   └── fetch_edgar.py      # SEC EDGAR quarterly revenue fetcher
├── analysis/
│   └── forecast.py         # Monthly panel alignment and linear regression model
└── report/
    └── build_report.py     # Self-contained HTML report generator
```

## Limitations and Future Improvements

**Current limitations:**

- **Google Trends data is synthetic.** The direct CSV export URL used by TireSignal returns HTTP 400 errors in practice, so the trends fetcher falls back to procedurally generated data with realistic seasonal patterns. The data is labeled `source=SYNTHETIC` in the database. A working Trends integration would require a browser session cookie or a paid SerpAPI/DataForSEO key.

- **Linear regression is intentionally simple.** The model fits on the last 36 months of monthly data with no lag features, no cross-validation, and no regularization. It is sufficient to demonstrate the pipeline and produce directional signals, but should not be treated as a production forecasting system.

- **Single company target.** The forecast target is Goodyear (GT) stock price as a demand proxy. This introduces idiosyncratic company risk (balance sheet, litigation, management) that is unrelated to industry demand.

**Suggested improvements:**

- Integrate real Google Trends data via a paid provider (SerpAPI, DataForSEO) or by authenticating with a Google account cookie
- Add more tire-sector tickers (Michelin, Bridgestone ADRs, Discount Tire parent) to build a broader industry index as the forecast target
- Add lagged features (e.g., 3-month lag on search trends) to better capture the lead-lag relationship between consumer intent and market pricing
- Replace linear regression with Ridge or a gradient-boosted model and add time-series cross-validation
- Schedule automated weekly runs and publish the report to a static host

## Tech Stack

| Library | Purpose |
|---------|---------|
| `requests` | HTTP client for Google Trends CSV and SEC EDGAR API |
| `pandas` | Data manipulation and monthly panel alignment |
| `fredapi` | FRED API client for macroeconomic series |
| `yfinance` | Yahoo Finance stock price and income statement data |
| `scikit-learn` | `LinearRegression`, `StandardScaler`, `r2_score` |
| `python-dotenv` | Loads `FRED_API_KEY` from `.env` file |
| `pytrends` | Listed for completeness — replaced by direct requests due to urllib3 incompatibility |
| Chart.js (CDN) | Interactive charts in the HTML report |
| SQLite (stdlib) | Local data cache via Python's built-in `sqlite3` |
