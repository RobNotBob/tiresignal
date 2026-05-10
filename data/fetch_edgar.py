"""
Fetches quarterly filings (10-Q, 10-K) for tire companies from SEC EDGAR
and stores key metrics in SQLite.
"""

from dotenv import load_dotenv

load_dotenv()

# SEC CIK numbers for major tire companies
COMPANIES = {
    "Goodyear": "0000042582",
}


def fetch_edgar():
    # TODO: use the EDGAR full-text search API or company facts API
    # (https://data.sec.gov/api/xbrl/companyfacts/) to pull
    # inventory, revenue, and unit volume disclosures.
    # Write results to the 'edgar' table in db/tiresignal.db.
    # Respect SEC rate limits: max 10 requests/second,
    # set User-Agent header to identify your app.
    pass
