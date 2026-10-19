"""
Data-quality checks (standard library only).

None of these checks *delete* or *modify* data.  They only report findings so
that a human can decide whether a flagged value is:

  * a genuine market movement (correct, keep),
  * a publication lag (missing value that will be back-filled), or
  * a real error (to be corrected at the source and re-ingested).

Checks implemented
------------------
1. Duplicate rows   - grouped count on the primary key (should always be 0;
                      the upsert primary key prevents duplicates by design).
2. Hard-bound flags - values outside documented physical plausibility ranges
                      (see docs/DATA_CATALOG.md for the rationale).
3. Schedule gaps    - weekdays / month-starts inside the observed window that
                      have no row.  Daily gaps include public holidays and
                      storm-related closures, so they are REVIEW items, not
                      automatic errors.
4. MAD outliers     - robust, distribution-free outliers using the median and
                      the Median Absolute Deviation (threshold 0.6745*|x-
                      median|/MAD > 6).  Unlike standard deviation, MAD is not
                      dragged around by a few extreme days.
5. Rate level shifts- very large day-to-day moves in interest-rate series
                      (>= 1.0 percentage point), which usually mark a policy
                      change or a data oddity worth checking.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import statistics
from pathlib import Path

from .config import db_path, resolve
from .datasets import DATASETS

log = logging.getLogger(__name__)

# Robust outlier threshold (modified z-score).  6 is deliberately conservative:
# it flags only extreme departures, not ordinary high/low days.
MAD_Z_THRESHOLD = 6.0
MIN_POINTS_FOR_MAD = 8
# A one-percentage-point same-day move in an interest rate is unusually large.
RATE_LEVEL_SHIFT = 1.0


def _series(conn, dataset: str, metric: str, freq: str):
    """Return sorted [(date_obj, value)] for one metric/freq."""
    rows = conn.execute(
        """SELECT date, value FROM observations
           WHERE dataset=? AND metric=? AND freq=? ORDER BY date""",
        (dataset, metric, freq),
    ).fetchall()
    out = []
    for d, v in rows:
        try:
            out.append((dt.date.fromisoformat(d), float(v)))
        except ValueError:
            log.warning("Skipping unparsable date %r in %s/%s", d, dataset, metric)
    return out


def check_duplicates(conn) -> list[dict]:
    rows = conn.execute(
        """SELECT dataset, metric, freq, date, COUNT(*) AS n
           FROM observations
           GROUP BY dataset, metric, freq, date
           HAVING n > 1"""
    ).fetchall()
    return [dict(r) for r in rows]


def check_hard_bounds(conn) -> list[dict]:
    """Values outside the documented physical plausibility ranges."""
    rows = conn.execute(
        """SELECT o.dataset, o.metric, o.freq, o.date, o.value,
                  m.hard_min, m.hard_max, m.unit
           FROM observations o
           JOIN metric_meta m
             ON m.dataset = o.dataset AND m.metric = o.metric
           WHERE (m.hard_min IS NOT NULL AND o.value < m.hard_min)
              OR (m.hard_max IS NOT NULL AND o.value > m.hard_max)
           ORDER BY o.dataset, o.metric, o.date"""
    ).fetchall()
    return [dict(r) for r in rows]


def _expected_daily_dates(start: dt.date, end: dt.date) -> list[dt.date]:
    """Every weekday (Mon-Fri) between start and end, inclusive."""
    days = []
    cur = start
    one = dt.timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:  # 0=Mon ... 4=Fri
            days.append(cur)
        cur += one
    return days


def _expected_monthly_dates(start: dt.date, end: dt.date) -> list[dt.date]:
    """The first day of every month between start and end, inclusive."""
    out = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(dt.date(y, m, 1))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def check_schedule_gaps(conn) -> list[dict]:
    """Missing weekdays (daily feeds) and missing months (monthly feed)."""
    findings = []
    for ds_key, spec in DATASETS.items():
        freqs = [r[0] for r in conn.execute(
            "SELECT DISTINCT freq FROM observations WHERE dataset=? ORDER BY freq",
            (ds_key,)).fetchall()]
        for metric in spec["metrics"]:
            for freq in freqs:
                series = _series(conn, ds_key, metric, freq)
                if len(series) < 2:
                    continue
                present = {d for d, _ in series}
                start, end = series[0][0], series[-1][0]
                if freq == "daily":
                    expected = _expected_daily_dates(start, end)
                elif freq == "monthly":
                    expected = _expected_monthly_dates(start, end)
                else:
                    continue  # sparse annual series: no regular grid
                missing = [d for d in expected if d not in present]
                if missing:
                    findings.append({
                        "dataset": ds_key,
                        "metric": metric,
                        "freq": freq,
                        "missing_count": len(missing),
                        "window_start": start.isoformat(),
                        "window_end": end.isoformat(),
                        "missing_dates": [d.isoformat() for d in missing],
                        "note": (
                            "weekday gaps for daily feeds also include HK "
                            "public holidays and storm closures; verify "
                            "before treating as errors"
                        ) if freq == "daily" else
                        "month-start gaps often reflect publication lag",
                    })
    return findings


def check_mad_outliers(conn) -> list[dict]:
    findings = []
    for ds_key, spec in DATASETS.items():
        for metric, (_label, unit, category, _lo, _hi) in spec["metrics"].items():
            for freq in ("daily", "monthly", "annual"):
                series = _series(conn, ds_key, metric, freq)
                if len(series) < MIN_POINTS_FOR_MAD:
                    continue
                values = [v for _, v in series]
                median = statistics.median(values)
                mad = statistics.median([abs(v - median) for v in values])
                if mad == 0:
                    # More than half the values are identical; MAD cannot rank
                    # deviations, so skip rather than divide by zero.
                    continue
                for d, v in series:
                    z = 0.6745 * abs(v - median) / mad
                    if z > MAD_Z_THRESHOLD:
                        findings.append({
                            "dataset": ds_key, "metric": metric, "freq": freq,
                            "date": d.isoformat(), "value": v,
                            "median": round(median, 6),
                            "modified_z": round(z, 2),
                            "unit": unit,
                        })
    return findings


def check_rate_level_shifts(conn) -> list[dict]:
    """Very large same-day moves in interest-rate series (daily only)."""
    findings = []
    for ds_key, spec in DATASETS.items():
        if spec["freq"] != "daily":
            continue
        for metric, (label, unit, category, _lo, _hi) in spec["metrics"].items():
            if category != "interest_rate":
                continue
            series = _series(conn, ds_key, metric, "daily")
            for (d0, v0), (d1, v1) in zip(series, series[1:]):
                if (d1 - d0).days > 7:
                    continue  # do not compare across a long break
                move = v1 - v0
                if abs(move) >= RATE_LEVEL_SHIFT:
                    findings.append({
                        "dataset": ds_key, "metric": metric,
                        "from_date": d0.isoformat(), "to_date": d1.isoformat(),
                        "from_value": v0, "to_value": v1,
                        "change": round(move, 4), "unit": unit,
                        "label": label,
                    })
    return findings


def run_report(conn) -> dict:
    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "thresholds": {
            "mad_modified_z": MAD_Z_THRESHOLD,
            "rate_level_shift_pct_point": RATE_LEVEL_SHIFT,
        },
        "duplicates": check_duplicates(conn),
        "hard_bound_violations": check_hard_bounds(conn),
        "schedule_gaps": check_schedule_gaps(conn),
        "mad_outliers": check_mad_outliers(conn),
        "rate_level_shifts": check_rate_level_shifts(conn),
    }
    report["summary"] = {
        "duplicates": len(report["duplicates"]),
        "hard_bound_violations": len(report["hard_bound_violations"]),
        "series_with_schedule_gaps": len(report["schedule_gaps"]),
        "mad_outliers": len(report["mad_outliers"]),
        "rate_level_shifts": len(report["rate_level_shifts"]),
    }
    return report


def save_report(report: dict, cfg: dict) -> Path:
    out = resolve(cfg, "data/processed/quality_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    return out


def open_db(cfg):
    """Open the SQLite database for the quality checks.

    Quality checks are meaningless on an empty database, so this fails with an
    actionable message when the pipeline has not been run yet.  Without this
    guard, ``sqlite3.connect`` silently creates a zero-byte file (or raises a
    bare ``unable to open database file`` when the directory is missing) and
    the caller then crashes on ``no such table: observations``.
    """
    import sqlite3
    path = db_path(cfg)
    if not path.exists():
        raise FileNotFoundError(
            f"No database at {path}. Build it first with "
            "'python scripts/run_pipeline.py' (add --offline to replay the "
            "bundled cache in data/raw)."
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("SELECT 1 FROM observations LIMIT 1")
    except sqlite3.OperationalError as exc:
        conn.close()
        raise RuntimeError(
            f"Database at {path} has no 'observations' table, so it was not "
            "created by the pipeline. Re-run 'python scripts/run_pipeline.py'."
        ) from exc
    return conn
