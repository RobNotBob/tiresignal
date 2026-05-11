# Required packages: scikit-learn, pandas
"""
Combines signals from all data sources and produces a tire demand forecast.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.preprocessing import StandardScaler

load_dotenv()

DB_PATH = Path(__file__).parent.parent / "db" / "tiresignal.db"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_table(conn: sqlite3.Connection, query: str) -> pd.DataFrame:
    df = pd.read_sql(query, conn)
    return df


def _load_all(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trends = _load_table(conn, "SELECT date, keyword, interest FROM trends")
    fred = _load_table(conn, "SELECT date, series_id, value FROM fred_indicators")
    stocks = _load_table(conn, "SELECT date, ticker, close_price FROM stock_prices WHERE ticker = 'GT'")
    edgar = _load_table(conn, "SELECT date, revenue FROM edgar_revenue WHERE form_type = '10-Q'")
    for df in (trends, fred, stocks, edgar):
        df["date"] = pd.to_datetime(df["date"])
    return trends, fred, stocks, edgar


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def _to_monthly(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    df = df.copy()
    df[date_col] = df[date_col].dt.to_period("M").dt.to_timestamp()
    return df


def _build_monthly_panel(
    trends: pd.DataFrame,
    fred: pd.DataFrame,
    stocks: pd.DataFrame,
    edgar: pd.DataFrame,
) -> pd.DataFrame:
    # Pivot each source to wide monthly format
    trends_wide = (
        _to_monthly(trends)
        .groupby(["date", "keyword"])["interest"]
        .mean()
        .unstack("keyword")
    )
    trends_wide.columns = [f"trend_{c}" for c in trends_wide.columns]

    fred_wide = (
        _to_monthly(fred)
        .groupby(["date", "series_id"])["value"]
        .mean()
        .unstack("series_id")
    )

    gt_prices = (
        _to_monthly(stocks)
        .groupby("date")["close_price"]
        .mean()
        .rename("GT_close")
    )

    # Edgar is quarterly — resample to monthly by forward-filling within each quarter
    edgar_monthly = (
        _to_monthly(edgar)
        .groupby("date")["revenue"]
        .mean()
        .rename("edgar_revenue")
        .resample("MS")
        .last()
    )

    # Build a complete monthly index spanning all sources
    all_dates = (
        list(trends_wide.index)
        + list(fred_wide.index)
        + list(gt_prices.index)
        + list(edgar_monthly.index)
    )
    idx = pd.date_range(min(all_dates), max(all_dates), freq="MS")

    panel = pd.DataFrame(index=idx)
    panel = panel.join(trends_wide.reindex(idx), how="left")
    panel = panel.join(fred_wide.reindex(idx), how="left")
    panel = panel.join(gt_prices.reindex(idx), how="left")
    panel = panel.join(edgar_monthly.reindex(idx), how="left")

    # Forward-fill sparse series (FRED monthly, Edgar quarterly)
    panel = panel.ffill().dropna()
    panel.index.name = "date"
    return panel


# ---------------------------------------------------------------------------
# Modelling
# ---------------------------------------------------------------------------

def _split(panel: pd.DataFrame, train_frac: float = 0.8):
    n = len(panel)
    split = int(n * train_frac)
    return panel.iloc[:split], panel.iloc[split:]


def _feature_cols(panel: pd.DataFrame) -> list[str]:
    return [c for c in panel.columns if c != "GT_close"]


def _train(train: pd.DataFrame) -> tuple[LinearRegression, StandardScaler]:
    features = _feature_cols(train)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[features])
    y_train = train["GT_close"].values
    model = LinearRegression()
    model.fit(X_train, y_train)
    return model, scaler


def _predict(model: LinearRegression, scaler: StandardScaler, X_df: pd.DataFrame) -> pd.Series:
    features = _feature_cols(X_df)
    X_scaled = scaler.transform(X_df[features])
    return pd.Series(model.predict(X_scaled), index=X_df.index)


def _forecast_panel(panel: pd.DataFrame, months: int = 6) -> pd.DataFrame:
    """Extend the panel by extrapolating the linear trend of the last 6 months per feature."""
    features = _feature_cols(panel)
    tail = panel[features].iloc[-6:]
    # Fit a per-feature slope over the trailing window (x = 0..5)
    x = pd.Series(range(len(tail)), index=tail.index, dtype=float)
    slopes = tail.apply(lambda col: col.cov(x) / x.var())
    last_vals = tail.iloc[-1]

    future_idx = pd.date_range(
        panel.index[-1] + timedelta(days=32),
        periods=months,
        freq="MS",
    )
    rows = [last_vals + slopes * (i + 1) for i in range(months)]
    return pd.DataFrame(rows, columns=features, index=future_idx)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _build_summary(
    feature_importance: pd.DataFrame,
    historical: pd.DataFrame,
    forecast: pd.DataFrame,
    score: float,
) -> str:
    top = feature_importance.iloc[0]
    recent_actual = historical["actual"].iloc[-6:].mean()
    forecast_mean = forecast["predicted"].mean()
    direction = "higher" if forecast_mean > recent_actual else "lower"
    pct_change = abs((forecast_mean - recent_actual) / recent_actual * 100)

    top_driver = top["feature"].replace("trend_", "search interest: ").replace("_", " ")
    if score < 0:
        projection_label = "illustrative projection"
        confidence_note = " Results should be treated as illustrative only."
    else:
        projection_label = "projection"
        confidence_note = ""
    return (
        f"The model (R²={score:.2f}) {projection_label}: Goodyear stock — used as a tire demand proxy — "
        f"may trend {direction} over the next 6 months, moving from a recent average of "
        f"${recent_actual:.2f} to a forecast average of ${forecast_mean:.2f} "
        f"({pct_change:.1f}% {'increase' if direction == 'higher' else 'decline'}). "
        f"The strongest demand signal is {top_driver} "
        f"(coefficient {top['coefficient']:.3f}).{confidence_note}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_forecast() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        print("[forecast] Loading data from SQLite...")
        trends, fred, stocks, edgar = _load_all(conn)
    finally:
        conn.close()

    print("[forecast] Aligning signals to monthly panel...")
    panel = _build_monthly_panel(trends, fred, stocks, edgar)
    panel = panel.iloc[-36:]
    print(f"[forecast] Panel: {len(panel)} months × {len(panel.columns)} columns (last 36 months).")

    train_df, test_df = _split(panel)
    print(f"[forecast] Training on {len(train_df)} months, testing on {len(test_df)} months.")

    model, scaler = _train(train_df)

    train_pred = _predict(model, scaler, train_df)
    test_pred = _predict(model, scaler, test_df)
    all_pred = pd.concat([train_pred, test_pred])

    historical = pd.DataFrame({
        "date": panel.index,
        "actual": panel["GT_close"].values,
        "predicted": all_pred.values,
    })

    score = float(r2_score(test_df["GT_close"], test_pred))
    print(f"[forecast] Test R²: {score:.3f}")
    if score < 0:
        print("[forecast] WARNING: R² is below 0 — model has low predictive power. Results should be treated as illustrative only.")

    future_panel = _forecast_panel(panel)
    future_pred = _predict(model, scaler, future_panel)
    forecast_df = pd.DataFrame({
        "date": future_panel.index,
        "predicted": future_pred.values,
    })

    features = _feature_cols(panel)
    importance = pd.DataFrame({
        "feature": features,
        "coefficient": model.coef_,
    }).sort_values("coefficient", key=abs, ascending=False).reset_index(drop=True)

    summary = _build_summary(importance, historical, forecast_df, score)
    print(f"[forecast] {summary}")

    return {
        "historical": historical,
        "forecast": forecast_df,
        "feature_importance": importance,
        "r2_score": score,
        "summary": summary,
        "last_updated": datetime.utcnow().isoformat(),
    }
