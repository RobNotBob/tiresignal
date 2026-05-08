"""
TireSignal pipeline entry point.
Runs: fetch → store → analyze → report
"""

from data.fetch_trends import fetch_trends
from data.fetch_fred import fetch_fred
from data.fetch_stocks import fetch_stocks
from data.fetch_edgar import fetch_edgar
from analysis.forecast import run_forecast
from report.build_report import build_report


def main():
    print("=== TireSignal ===")

    print("[1/5] Fetching Google Trends...")
    fetch_trends()

    print("[2/5] Fetching FRED data...")
    fetch_fred()

    print("[3/5] Fetching stock data...")
    fetch_stocks()

    print("[4/5] Fetching SEC EDGAR filings...")
    fetch_edgar()

    print("[5/5] Running forecast and building report...")
    forecast = run_forecast()
    build_report(forecast)

    print("Done. Report saved to output/report.html")


if __name__ == "__main__":
    main()
