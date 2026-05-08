"""
Renders the demand forecast as a self-contained HTML report
saved to output/report.html.
"""

import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "report.html")


def build_report(forecast: dict):
    # TODO: generate HTML from forecast dict
    # Include charts (e.g., via Plotly or Chart.js embedded as inline JS),
    # signal tables, and a plain-language summary.
    # Write the final HTML string to OUTPUT_PATH.
    html = "<html><body><h1>TireSignal Report</h1><p>No data yet.</p></body></html>"
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
