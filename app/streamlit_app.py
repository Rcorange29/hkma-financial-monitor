"""
Streamlit dashboard for the HKMA financial monitor.

Run (from the project root):
    pip install -r requirements.txt
    streamlit run app/streamlit_app.py

The dashboard only reads the local SQLite database.  It does not call the
network, so it works equally well on data loaded live or from the offline
cache.  The data-quality tab reads data/processed/quality_report.json when it
exists (run `python scripts/run_quality.py` first).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hkma_monitor.config import load_config  # noqa: E402
from hkma_monitor.datasets import DATASETS  # noqa: E402

st.set_page_config(page_title="HKMA Financial Monitor", layout="wide")


@st.cache_data
def get_db_path() -> str:
    return str(PROJECT_ROOT / load_config()["paths"]["database"])


@st.cache_data
def load_series(dataset: str, metric: str, freq: str) -> pd.DataFrame:
    conn = sqlite3.connect(get_db_path())
    try:
        df = pd.read_sql_query(
            """SELECT date, value, unit, label FROM observations
               WHERE dataset=? AND metric=? AND freq=?
               ORDER BY date""",
            conn, params=(dataset, metric, freq),
        )
    finally:
        conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def available_freqs(dataset: str, metric: str) -> list[str]:
    conn = sqlite3.connect(get_db_path())
    try:
        rows = conn.execute(
            """SELECT DISTINCT freq FROM observations
               WHERE dataset=? AND metric=? ORDER BY freq""",
            (dataset, metric),
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def metric_label(dataset: str, metric: str) -> str:
    return DATASETS[dataset]["metrics"][metric][0]


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.title("HKMA monitor")
dataset = st.sidebar.selectbox(
    "Dataset",
    list(DATASETS.keys()),
    format_func=lambda k: DATASETS[k]["title"],
)
metrics = list(DATASETS[dataset]["metrics"].keys())
metric = st.sidebar.selectbox(
    "Metric", metrics, format_func=lambda m: metric_label(dataset, m),
)
freqs = available_freqs(dataset, metric)
default_freq = DATASETS[dataset]["freq"]
freq = st.sidebar.selectbox(
    "Frequency", freqs,
    index=freqs.index(default_freq) if default_freq in freqs else 0,
)

df = load_series(dataset, metric, freq)

st.title("Hong Kong financial data monitor")
st.caption(
    "Source: HKMA public API (official). "
    "Data are loaded into local SQLite by the ETL pipeline. "
    "This is a learning project; nothing here is investment advice."
)

if df.empty:
    st.warning("No data for this selection. Run the pipeline first.")
    st.stop()

# Date range filter.
lo, hi = df["date"].min().date(), df["date"].max().date()
col1, col2 = st.columns(2)
with col1:
    start = st.date_input("Start", lo, min_value=lo, max_value=hi)
with col2:
    end = st.date_input("End", hi, min_value=lo, max_value=hi)
mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
view = df.loc[mask].copy()

unit = view["unit"].iloc[0]
label = view["label"].iloc[0]
st.subheader(f"{label}")
st.caption(f"Unit: {unit}  |  Frequency: {freq}  |  {len(view)} points")

# ---------------------------------------------------------------------------
# Trend chart
# ---------------------------------------------------------------------------
chart_df = view.set_index("date")[["value"]]
st.line_chart(chart_df, height=380)

# ---------------------------------------------------------------------------
# Basic statistics
# ---------------------------------------------------------------------------
stats = pd.DataFrame({
    "statistic": ["count", "first date", "last date", "min", "max",
                  "mean", "median", "range"],
    "value": [
        len(view),
        view["date"].min().date().isoformat(),
        view["date"].max().date().isoformat(),
        round(view["value"].min(), 4),
        round(view["value"].max(), 4),
        round(view["value"].mean(), 4),
        round(view["value"].median(), 4),
        round(view["value"].max() - view["value"].min(), 4),
    ],
})
st.dataframe(stats, use_container_width=True, hide_index=True)

with st.expander("Show raw rows (latest 20)"):
    st.dataframe(view.tail(20)[["date", "value"]].iloc[::-1],
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Data quality tab
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Data quality")
report_path = PROJECT_ROOT / "data" / "processed" / "quality_report.json"
if report_path.exists():
    report = json.loads(report_path.read_text(encoding="utf-8"))
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Duplicates", report["summary"]["duplicates"])
    c2.metric("Hard-bound flags", report["summary"]["hard_bound_violations"])
    c3.metric("Series with gaps", report["summary"]["series_with_schedule_gaps"])
    c4.metric("MAD outliers", report["summary"]["mad_outliers"])
    c5.metric("Rate level shifts", report["summary"]["rate_level_shifts"])
    st.caption(
        "Findings are review flags, not automatic deletions. Daily schedule "
        "gaps include public holidays and storm closures."
    )
    with st.expander("MAD robust outliers"):
        st.dataframe(pd.DataFrame(report["mad_outliers"]),
                     use_container_width=True, hide_index=True)
    with st.expander("Schedule gaps"):
        st.dataframe(pd.DataFrame(report["schedule_gaps"])[
            ["dataset", "metric", "freq", "missing_count",
             "window_start", "window_end", "note"]],
            use_container_width=True, hide_index=True)
else:
    st.info(
        "No quality report found. Run `python scripts/run_quality.py` "
        "to generate it."
    )
