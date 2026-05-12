"""
TireSignal pipeline entry point.
Runs: fetch → store → analyze → report
"""

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from data.fetch_trends import get_trends_data
from data.fetch_fred import get_fred_data
from data.fetch_stocks import get_stock_data
from data.fetch_edgar import get_edgar_revenue
from analysis.forecast import run_forecast
from report.build_report import build_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TireSignal — tire demand forecasting pipeline",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-fetch all data sources even if cache is fresh",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip all fetchers and run analysis + report from cached SQLite data only",
    )
    args = parser.parse_args()

    if args.refresh and args.no_fetch:
        print("Error: --refresh and --no-fetch are mutually exclusive.")
        sys.exit(1)

    try:
        if not args.no_fetch:
            print("[1/4] Fetching Google Trends...")
            get_trends_data(force_refresh=args.refresh)

            print("[2/4] Fetching FRED indicators...")
            get_fred_data(force_refresh=args.refresh)

            print("[3/4] Fetching stock data...")
            get_stock_data(force_refresh=args.refresh)

            print("[4/4] Fetching SEC EDGAR revenue...")
            get_edgar_revenue(force_refresh=args.refresh)
        else:
            print("[fetch] Skipping all fetchers (--no-fetch). Using cached data.")

        print("[forecast] Running forecast...")
        forecast = run_forecast()

        print("[report] Building report...")
        build_report(forecast)

        print("✓ TireSignal complete — open output/report.html")

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
