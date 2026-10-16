"""
Cleaning / transformation layer (standard library only).

Turns the *wide* API records (one JSON object per date, many currency/rate
columns) into *tidy* long-form rows:

    (dataset, metric, date, freq, value, unit, label)

Long form is easier to load idempotently, to query in SQL, and to chart one
metric at a time in the dashboard.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from .datasets import DATASETS

log = logging.getLogger(__name__)

# Strings the HKMA feeds use to mean "no value".
_MISSING_TOKENS = {"", "na", "n.a.", "n/a", "-", "–", "—", "none", "null", "."}


def parse_number(raw: Any) -> float | None:
    """Parse an API cell into a float, or return None for a missing value.

    Handles numbers, sign-prefixed strings ("+0", "-40"), thousands separators
    ("1,234.50"), and common textual missing markers.
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # guard: bool is a subclass of int
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip().replace(",", "")
        if s.lower() in _MISSING_TOKENS:
            return None
        # Keep a leading sign; strip spaces that sometimes wrap the number.
        s = s.replace(" ", "")
        try:
            return float(s)
        except ValueError:
            log.warning("Could not parse numeric value %r -> treated as missing", raw)
            return None
    return None


def parse_period(raw_date: str, fmt: str) -> tuple[str, str]:
    """Normalise a date/period to (ISO yyyy-mm-dd, per-row frequency).

    Daily feeds use 'yyyy-mm-dd' and map to freq="daily".

    Monthly feeds normally use 'yyyy-mm'; we store the first day of that month
    so every series shares one comparable, sortable date format and map to
    freq="monthly".

    The monetary-statistics feed also returns *annual, year-end* rows spelled
    'yyyy-00' (month part 00).  These are kept as freq="annual" and dated
    yyyy-12-01.  Keeping a separate frequency (rather than dropping the rows)
    preserves the multi-year history the API exposes; analyses must filter on
    ``freq`` so annual and monthly points are never mixed as if equal.
    """
    if not isinstance(raw_date, str):
        raise ValueError(f"Bad date value: {raw_date!r}")
    raw_date = raw_date.strip()
    if fmt == "%Y-%m":
        if len(raw_date) == 7:  # yyyy-mm
            year, month = raw_date.split("-")
            if month == "00":  # API convention for an annual/year-end row
                return f"{year}-12-01", "annual"
            return f"{year}-{month}-01", "monthly"
        # some rows may already carry a full date
        iso = dt.datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        return iso, "monthly"
    # Validate daily dates explicitly so a format change surfaces early.
    iso = dt.datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
    return iso, "daily"


def transform_dataset(dataset_key: str, records: list[dict]) -> list[dict]:
    """Melt one dataset's raw records into tidy rows."""
    spec = DATASETS[dataset_key]
    date_field = spec["date_field"]
    date_fmt = spec["date_format"]
    metrics = spec["metrics"]

    rows: list[dict] = []
    null_count = 0
    for rec in records:
        if not isinstance(rec, dict):
            log.warning("[%s] skipping non-dict record: %r", dataset_key, rec)
            continue
        if date_field not in rec:
            raise ValueError(f"[{dataset_key}] record missing {date_field}: {rec}")
        date, row_freq = parse_period(rec[date_field], date_fmt)
        for field, (label, unit, category, _lo, _hi) in metrics.items():
            if field not in rec:
                # The API occasionally adds/removes columns. Treat a missing
                # column as a missing value, not a crash.
                null_count += 1
                continue
            value = parse_number(rec[field])
            if value is None:
                # Absent observations are represented as missing rows; the
                # data-quality layer detects gaps via the expected date grid.
                null_count += 1
                continue
            rows.append({
                "dataset": dataset_key,
                "metric": field,
                "date": date,
                "freq": row_freq,
                "value": value,
                "unit": unit,
                "label": label,
                "category": category,
            })
    log.info("[%s] transformed %d value rows (%d missing cells)",
             dataset_key, len(rows), null_count)
    return rows


def transform_all(raw_by_dataset: dict[str, list[dict]]) -> list[dict]:
    out: list[dict] = []
    for key, records in raw_by_dataset.items():
        out.extend(transform_dataset(key, records))
    return out
