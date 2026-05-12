"""
Renders the demand forecast as a self-contained HTML report
saved to output/report.html.
"""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OUTPUT_PATH = Path(__file__).parent.parent / "output" / "report.html"

_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js"


def _fmt_date(ts) -> str:
    return str(ts)[:10]


def _chart1_data(forecast: dict) -> str:
    hist = forecast["historical"]
    fcast = forecast["forecast"]

    hist_dates = [_fmt_date(d) for d in hist["date"]]
    actual     = [round(float(v), 2) for v in hist["actual"]]
    predicted  = [round(float(v), 2) for v in hist["predicted"]]

    fcast_dates = [_fmt_date(d) for d in fcast["date"]]
    fcast_vals  = [round(float(v), 2) for v in fcast["predicted"]]

    # Forecast line starts from the last historical point so it visually connects
    all_dates      = hist_dates + fcast_dates
    null_pad       = [None] * len(hist_dates)
    fcast_line     = null_pad[:-1] + [predicted[-1]] + fcast_vals

    return json.dumps({
        "labels":    all_dates,
        "actual":    actual + [None] * len(fcast_dates),
        "predicted": predicted + [None] * len(fcast_dates),
        "fcast":     fcast_line,
    })


def _chart2_data(forecast: dict) -> str:
    imp = forecast["feature_importance"]
    labels = [r["feature"].replace("trend_", "search: ").replace("_", " ")
              for r in imp.to_dict("records")]
    coeffs = [round(float(r["coefficient"]), 4) for r in imp.to_dict("records")]
    colors = ["#e94560" if c >= 0 else "#4a90d9" for c in coeffs]
    return json.dumps({"labels": labels, "coefficients": coeffs, "colors": colors})


def _alert_banner(forecast: dict) -> str:
    if forecast["r2_score"] < 0:
        return (
            '<div class="alert">'
            '<strong>Low Confidence Warning</strong> &mdash; '
            'Model R&sup2; is below 0. These results have low predictive power '
            'and should be treated as illustrative only.'
            '</div>'
        )
    return ""


def _forecast_table(forecast: dict) -> str:
    rows = ""
    for _, row in forecast["forecast"].iterrows():
        rows += f"<tr><td>{_fmt_date(row['date'])}</td><td>${row['predicted']:.2f}</td></tr>\n"
    return f"""
    <table>
      <thead><tr><th>Date</th><th>Predicted GT Close</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def _render_html(forecast: dict) -> str:
    chart1 = _chart1_data(forecast)
    chart2 = _chart2_data(forecast)
    alert  = _alert_banner(forecast)
    table  = _forecast_table(forecast)
    summary   = forecast["summary"]
    updated   = str(forecast["last_updated"])[:19].replace("T", " ") + " UTC"
    r2_display = f"{forecast['r2_score']:.3f}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TireSignal Report</title>
<script src="{_CHARTJS_CDN}"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1a1a2e;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    padding: 24px 16px;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  header {{ border-bottom: 2px solid #e94560; padding-bottom: 16px; margin-bottom: 28px; }}
  header h1 {{ font-size: 2rem; color: #e94560; letter-spacing: 0.04em; }}
  header p.subtitle {{ font-size: 1rem; color: #999; margin-top: 4px; }}
  header p.updated {{ font-size: 0.8rem; color: #666; margin-top: 2px; }}
  .alert {{
    background: #3a3000;
    border-left: 4px solid #f0c040;
    color: #f0c040;
    padding: 12px 16px;
    border-radius: 4px;
    margin-bottom: 24px;
  }}
  .section {{ margin-bottom: 40px; }}
  .section h2 {{
    font-size: 1.1rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #e94560;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #2e2e4e;
  }}
  .summary-box {{
    background: #16213e;
    border-radius: 6px;
    padding: 16px 20px;
    color: #ccc;
    line-height: 1.7;
  }}
  .r2-badge {{
    display: inline-block;
    background: #2e2e4e;
    color: #aaa;
    font-size: 0.78rem;
    padding: 2px 8px;
    border-radius: 12px;
    margin-left: 8px;
    vertical-align: middle;
  }}
  .chart-wrap {{
    background: #16213e;
    border-radius: 6px;
    padding: 16px;
    position: relative;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }}
  th, td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #2e2e4e;
  }}
  th {{
    color: #e94560;
    font-weight: 600;
    background: #16213e;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #1e1e3a; }}
  footer {{
    border-top: 1px solid #2e2e4e;
    padding-top: 16px;
    color: #555;
    font-size: 0.8rem;
  }}
  footer strong {{ color: #777; }}
  @media (max-width: 600px) {{
    header h1 {{ font-size: 1.4rem; }}
  }}
</style>
</head>
<body>
<div class="container">

  <header>
    <h1>TireSignal</h1>
    <p class="subtitle">Tire Demand Forecasting Report</p>
    <p class="updated">Last updated: {updated}</p>
  </header>

  {alert}

  <div class="section">
    <h2>Summary <span class="r2-badge">R&sup2; {r2_display}</span></h2>
    <div class="summary-box">{summary}</div>
  </div>

  <div class="section">
    <h2>Historical vs Forecast &mdash; GT Stock Price</h2>
    <div class="chart-wrap">
      <canvas id="chart1"></canvas>
    </div>
  </div>

  <div class="section">
    <h2>Feature Importance (Coefficients)</h2>
    <div class="chart-wrap">
      <canvas id="chart2"></canvas>
    </div>
  </div>

  <div class="section">
    <h2>6-Month Forecast</h2>
    {table}
  </div>

  <footer>
    <strong>Data sources:</strong>
    Google Trends &bull; FRED (Federal Reserve Economic Data) &bull;
    yfinance (Yahoo Finance) &bull; SEC EDGAR
  </footer>

</div>
<script>
(function () {{
  const C1 = {chart1};
  const C2 = {chart2};

  const gridColor  = "rgba(255,255,255,0.06)";
  const tickColor  = "#666";
  const accent     = "#e94560";
  const predicted  = "#4a90d9";
  const fcastColor = "#f0c040";

  // Chart 1 — line chart
  new Chart(document.getElementById("chart1"), {{
    type: "line",
    data: {{
      labels: C1.labels,
      datasets: [
        {{
          label: "Actual GT close",
          data: C1.actual,
          borderColor: accent,
          backgroundColor: "rgba(233,69,96,0.08)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          spanGaps: false,
        }},
        {{
          label: "Predicted",
          data: C1.predicted,
          borderColor: predicted,
          borderWidth: 1.5,
          borderDash: [],
          pointRadius: 0,
          tension: 0.3,
          spanGaps: false,
        }},
        {{
          label: "6-month forecast",
          data: C1.fcast,
          borderColor: fcastColor,
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 3,
          pointBackgroundColor: fcastColor,
          tension: 0.2,
          spanGaps: false,
        }},
      ],
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: "index", intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: "#aaa", boxWidth: 14 }} }},
        tooltip: {{ backgroundColor: "#16213e", titleColor: "#e94560", bodyColor: "#ccc" }},
      }},
      scales: {{
        x: {{
          ticks: {{ color: tickColor, maxTicksLimit: 12, maxRotation: 0 }},
          grid: {{ color: gridColor }},
        }},
        y: {{
          ticks: {{ color: tickColor, callback: v => "$" + v }},
          grid: {{ color: gridColor }},
        }},
      }},
    }},
  }});

  // Chart 2 — horizontal bar chart
  new Chart(document.getElementById("chart2"), {{
    type: "bar",
    data: {{
      labels: C2.labels,
      datasets: [{{
        label: "Coefficient",
        data: C2.coefficients,
        backgroundColor: C2.colors,
        borderRadius: 3,
      }}],
    }},
    options: {{
      indexAxis: "y",
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ backgroundColor: "#16213e", titleColor: "#e94560", bodyColor: "#ccc" }},
      }},
      scales: {{
        x: {{
          ticks: {{ color: tickColor }},
          grid: {{ color: gridColor }},
        }},
        y: {{
          ticks: {{ color: "#ccc", font: {{ size: 11 }} }},
          grid: {{ color: gridColor }},
        }},
      }},
    }},
  }});
}})();
</script>
</body>
</html>"""


def build_report(forecast: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = _render_html(forecast)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[report] Written to {OUTPUT_PATH}")
