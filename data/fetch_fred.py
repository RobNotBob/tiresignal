"""
Fetches macroeconomic indicators from the FRED API via fredapi
and stores results in SQLite.

Requires env var: FRED_API_KEY
"""


def fetch_fred():
    # TODO: pull series relevant to tire demand, e.g.:
    #   TRFVOLUSM227NFWA — vehicle miles traveled
    #   CPIAUCSL          — CPI (proxy for cost pressure)
    #   GASREGCOVW        — weekly retail gasoline price
    #   TOTALSA           — total vehicle sales
    # Write each series to the 'fred' table in db/tiresignal.db
    pass
