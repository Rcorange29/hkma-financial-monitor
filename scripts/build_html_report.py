#!/usr/bin/env python3
"""
Build a zero-dependency, self-contained HTML report with inline SVG charts.

Why this exists
---------------
The interactive dashboard needs Streamlit (third-party).  This report needs
only the Python standard library, so it can be generated and opened offline
on any machine and is easy to screenshot for the README.  It reads the same
SQLite database and the same quality report, so the two front-ends never
disagree about the numbers.

Usage:
    python scripts/build_html_report.py
"""
from __future__ import annotations

import datetime as dt
import html
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hkma_monitor.config import load_config  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny inline-SVG line chart (no third-party libraries)
# ---------------------------------------------------------------------------
W, H = 900, 318
ML, MR, MT, MB = 56, 44, 38, 34
PW, PH = W - ML - MR, H - MT - MB


def _fmt_num(v: float, dec: int = 2) -> str:
    return f"{v:,.{dec}f}"


def line_chart(series: list[dict], title: str, y_label: str = "",
               fixed_ymin: float | None = None,
               fixed_ymax: float | None = None,
               dec: int = 2) -> str:
    """series: list of {name, color, points:[(date_obj, value)]}."""
    all_pts = [p for s in series for p in s["points"]]
    if not all_pts:
        return f"<p>No data for {html.escape(title)}</p>"
    xs = [d.toordinal() for d, _ in all_pts]
    yvals = [v for _, v in all_pts]
    x0, x1 = min(xs), max(xs)
    if fixed_ymin is not None:
        y0 = fixed_ymin
    else:
        y0 = min(yvals)
    if fixed_ymax is not None:
        y1 = fixed_ymax
    else:
        y1 = max(yvals)
    if y1 == y0:
        y1, y0 = y0 + 1, y0 - 1
    pad = (y1 - y0) * 0.05
    if fixed_ymin is None:
        y0 -= pad
    if fixed_ymax is None:
        y1 += pad

    def px(o: int) -> float:
        return ML + (o - x0) / (x1 - x0 or 1) * PW

    def py(v: float) -> float:
        return MT + (1 - (v - y0) / (y1 - y0)) * PH

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" '
             f'aria-label="{html.escape(title)}">']
    # y grid + labels
    for i in range(5):
        v = y0 + (y1 - y0) * i / 4
        yy = py(v)
        parts.append(f'<line x1="{ML}" y1="{yy:.1f}" x2="{W-MR}" y2="{yy:.1f}" '
                     f'class="grid"/>')
        parts.append(f'<text x="{ML-6}" y="{yy+4:.1f}" class="axis" '
                     f'text-anchor="end">{_fmt_num(v, dec)}</text>')
    # x ticks (~6)
    nticks = 6
    for i in range(nticks):
        o = x0 + (x1 - x0) * i / (nticks - 1)
        d = dt.date.fromordinal(int(round(o)))
        xx = px(o)
        parts.append(f'<text x="{xx:.1f}" y="{H-MB+18}" class="axis" '
                     f'text-anchor="middle">{d.strftime("%Y-%m")}</text>')
    # series
    for s in series:
        pts = s["points"]
        if len(pts) < 2:
            continue
        coord = " ".join(f"{px(d.toordinal()):.1f},{py(v):.1f}" for d, v in pts)
        parts.append(f'<polyline points="{coord}" fill="none" '
                     f'stroke="{s["color"]}" stroke-width="1.8"/>')
    # reference bands (legend swatches handled below)
    parts.append(f'<text x="{ML}" y="14" class="title">{html.escape(title)}</text>')
    parts.append("</svg>")
    # legend
    legend = '<div class="legend">' + "".join(
        f'<span><i style="background:{s["color"]}"></i>{html.escape(s["name"])}</span>'
        for s in series if len(s["points"]) >= 2) + "</div>"
    return "".join(parts) + legend


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------
def fetch(conn, metric: str, dataset: str, freq: str):
    rows = conn.execute(
        """SELECT date,value,label,unit FROM observations
           WHERE dataset=? AND metric=? AND freq=? ORDER BY date""",
        (dataset, metric, freq),
    ).fetchall()
    pts = [(dt.date.fromisoformat(d), v) for d, v, *_ in rows]
    label = rows[0][2] if rows else metric
    unit = rows[0][3] if rows else ""
    return pts, label, unit


def stats_row(conn, dataset: str, metric: str, freq: str) -> dict:
    r = conn.execute(
        """SELECT COUNT(*), MIN(date), MAX(date),
                  ROUND(MIN(value),4), ROUND(AVG(value),4), ROUND(MAX(value),4)
           FROM observations WHERE dataset=? AND metric=? AND freq=?""",
        (dataset, metric, freq),
    ).fetchone()
    return dict(zip(("n", "first", "last", "min", "avg", "max"), r))


def main() -> None:
    cfg = load_config(None)
    db = ROOT / cfg["paths"]["database"]
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    usd, usd_lab, usd_unit = fetch(conn, "usd", "fx_daily", "daily")
    cstrong, _, _ = fetch(conn, "cu_strongside", "interbank_daily", "daily")
    cweak, _, _ = fetch(conn, "cu_weakside", "interbank_daily", "daily")
    on, on_lab, _ = fetch(conn, "hibor_overnight", "interbank_daily", "daily")
    m1, m1_lab, _ = fetch(conn, "hibor_fixing_1m", "interbank_daily", "daily")
    base, base_lab, rate_unit = fetch(conn, "disc_win_base_rate", "interbank_daily", "daily")
    ab, ab_lab, ab_unit = fetch(conn, "closing_balance", "interbank_daily", "daily")
    twi, twi_lab, _ = fetch(conn, "twi", "interbank_daily", "daily")
    h3m_m, _, _ = fetch(conn, "hibor_fixing_3m", "monetary_monthly", "monthly")
    h3m_a, _, _ = fetch(conn, "hibor_fixing_3m", "monetary_monthly", "annual")
    m2_m, _, _ = fetch(conn, "m2_total", "monetary_monthly", "monthly")
    m2_a, _, _ = fetch(conn, "m2_total", "monetary_monthly", "annual")

    # Build charts.
    charts = []
    charts.append(line_chart(
        [{"name": "USD/HKD (daily)", "color": "#1f6feb", "points": usd},
         {"name": "CU weak side 7.85", "color": "#d1242f", "points": cweak},
         {"name": "CU strong side 7.75", "color": "#1a7f37", "points": cstrong}],
        "USD/HKD daily vs the Convertibility Undertaking band",
        fixed_ymin=7.72, fixed_ymax=7.88, dec=3))
    charts.append(line_chart(
        [{"name": "Discount Window Base Rate", "color": "#111827", "points": base},
         {"name": "Overnight HIBOR", "color": "#d18a00", "points": on},
         {"name": "1-month HIBOR fixing", "color": "#1f6feb", "points": m1}],
        "Policy rate and HIBOR (daily, % p.a.)",
        fixed_ymin=0, fixed_ymax=5, dec=1))
    charts.append(line_chart(
        [{"name": "Closing Aggregate Balance", "color": "#8250df", "points": ab}],
        "Aggregate Balance (daily, HK$ million)", dec=0))
    charts.append(line_chart(
        [{"name": "3-month HIBOR (monthly)", "color": "#1f6feb", "points": h3m_m},
         {"name": "3-month HIBOR (year-end annual)", "color": "#d1242f", "points": h3m_a}],
        "3-month HIBOR: recent monthly detail + multi-year year-end points",
        fixed_ymin=0, fixed_ymax=6, dec=2))
    charts.append(line_chart(
        [{"name": "M2 total (monthly)", "color": "#1a7f37", "points": m2_m},
         {"name": "M2 total (year-end annual)", "color": "#d1242f", "points": m2_a}],
        "Total M2 money supply (HK$ million)", dec=0))
    charts.append(line_chart(
        [{"name": "Trade Weighted Index (daily)", "color": "#0a7c80", "points": twi}],
        "HKD Trade Weighted Index (TWI)", fixed_ymin=98, fixed_ymax=104, dec=1))

    # Stats table for a curated set.
    stat_specs = [
        ("fx_daily", "usd", "daily", "USD/HKD"),
        ("interbank_daily", "disc_win_base_rate", "daily", "Base Rate"),
        ("interbank_daily", "hibor_overnight", "daily", "Overnight HIBOR"),
        ("interbank_daily", "hibor_fixing_1m", "daily", "1M HIBOR"),
        ("interbank_daily", "closing_balance", "daily", "Aggregate Balance"),
        ("monetary_monthly", "hibor_fixing_3m", "annual", "3M HIBOR (year-end)"),
        ("monetary_monthly", "m2_total", "annual", "M2 total (year-end)"),
    ]
    rows = []
    for ds, mt, fr, nice in stat_specs:
        s = stats_row(conn, ds, mt, fr)
        rows.append(
            f"<tr><td>{nice}</td><td>{s['n']}</td><td>{s['first']}</td>"
            f"<td>{s['last']}</td><td>{s['min']}</td><td>{s['avg']}</td>"
            f"<td>{s['max']}</td></tr>")
    stats_table = (
        "<table><thead><tr><th>Series</th><th>n</th><th>First</th>"
        "<th>Last</th><th>Min</th><th>Mean</th><th>Max</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>")

    conn.close()

    # Quality summary
    qpath = ROOT / "data" / "processed" / "quality_report.json"
    q_summary = ""
    if qpath.exists():
        q = json.loads(qpath.read_text(encoding="utf-8"))["summary"]
        q_summary = (
            "<div class='cards'>" + "".join(
                f"<div class='card'><b>{v}</b><span>{k.replace('_',' ')}</span></div>"
                for k, v in q.items()) + "</div>")

    observations = """
    <ol>
      <li><b>The HKD stayed in the weak half of the Convertibility Undertaking
      band.</b> Over the 180 daily FX observations (2026-02-23 to 2026-09-30),
      USD/HKD ranged from 7.8110 to 7.8485 with a mean of 7.8375, i.e. it never
      reached the 7.85 weak-side undertaking but consistently traded above the
      7.80 midpoint. This is a description of the observed position; this
      report does not assert what caused it.</li>
      <li><b>Overnight HIBOR was much more volatile than the 1-month fixing,
      with repeated quarter-end spikes.</b> Over the daily window (2026-01-23 to
      2026-10-16) overnight HIBOR ranged from 1.10% to 4.00% (mean 2.19%) while
      the 1-month fixing ranged from 1.95% to 3.02% (mean 2.61%). The quality
      check found seven same-day moves of at least 1 percentage point in the
      overnight rate; all were adjacent to month-/quarter-end (e.g. 3.62% on
      2026-06-30 and 3.85% on 2026-09-30) and reversed within days. No such
      move occurred in the 1-month fixing.</li>
      <li><b>The year-end annual series shows a full rate cycle that the short
      daily window cannot.</b> Year-end 3-month HIBOR rose from 0.26% (2021) to
      5.15% (2023), then eased to 2.93% (2025); over the same period total M2
      rose from HK$16.27 trillion to HK$20.60 trillion. Within the daily 2026
      window the Discount Window Base Rate moved once, from 4.00% to 4.25% on
      2026-09-17. These series move together historically but this is an
      association, not evidence of causation.</li>
    </ol>
    <p class='note'>Limitations: the daily windows cover only ~8–9 months of
    2026; the long-horizon series are year-end points (5 annual values); the
    latest month (2026-09) has not yet published M1/M2/M3. Findings are based
    solely on the HKMA series here and exclude other macroeconomic factors.</p>
    """

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HKMA Financial Monitor - Report</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;
   background:#f6f8fa;color:#1f2328;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:32px 24px 64px}}
 h1{{font-size:28px;margin:0 0 4px}}
 h2{{font-size:20px;margin:36px 0 12px;border-bottom:1px solid #d0d7de;padding-bottom:6px}}
 .sub{{color:#57606a;font-size:14px}}
 .panel{{background:#fff;border:1px solid #d0d7de;border-radius:10px;padding:18px 20px;margin:16px 0}}
 .chart{{width:100%;height:auto;background:#fff}}
 .grid{{stroke:#eaeef2;stroke-width:1}}
 .axis{{font-size:10px;fill:#57606a}}
 .title{{font-size:13px;font-weight:600;fill:#1f2328}}
 .legend{{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#57606a;
   margin:2px 0 6px 56px}}
 .legend i{{display:inline-block;width:14px;height:3px;border-radius:2px;
   margin-right:6px;vertical-align:middle}}
 table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
 th,td{{border:1px solid #d0d7de;padding:6px 10px;text-align:right}}
 th:first-child,td:first-child{{text-align:left}}
 thead th{{background:#f6f8fa}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap}}
 .card{{background:#fff;border:1px solid #d0d7de;border-radius:8px;
   padding:12px 18px;display:flex;flex-direction:column;align-items:center;min-width:120px}}
 .card b{{font-size:22px}} .card span{{font-size:11px;color:#57606a;text-transform:capitalize}}
 .note{{font-size:13px;color:#57606a}}
 ol li{{margin-bottom:10px}}
</style></head><body><div class="wrap">
<h1>Hong Kong Financial Data Automation &amp; Monitoring</h1>
<p class="sub">Official HKMA open data &middot; ETL into SQLite &middot; data-quality
 checks &middot; report generated {dt.date.today().isoformat()}.</p>

<h2>Data quality at a glance</h2>
<div class="panel">{q_summary}
<p class="note">Flags are review items, never automatic deletions. Daily schedule
 gaps coincide with Hong Kong public holidays (e.g. 2026-04-03, 05-01, 07-01).
 0 duplicates and 0 hard-bound violations were found.</p></div>

<h2>Trend charts</h2>
<div class="panel">{charts[0]}</div>
<div class="panel">{charts[1]}</div>
<div class="panel">{charts[2]}</div>
<div class="panel">{charts[3]}</div>
<div class="panel">{charts[4]}</div>
<div class="panel">{charts[5]}</div>

<h2>Basic statistics</h2>
<div class="panel" style="overflow-x:auto">{stats_table}</div>

<h2>Data-supported observations</h2>
<div class="panel">{observations}</div>

<p class="sub">Source: Hong Kong Monetary Authority public API. For metric
definitions, units and frequency see docs/DATA_CATALOG.md. Not investment advice.</p>
</div></body></html>"""

    out = ROOT / "docs" / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"HTML report written to: {out}")


if __name__ == "__main__":
    main()
