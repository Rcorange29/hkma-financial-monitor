"""
SQLite storage layer (standard library only).

Design
------
* One tidy table ``observations`` with a composite PRIMARY KEY
  (dataset, metric, freq, date).  The PK is what makes repeated runs
  idempotent: re-running the loader upserts instead of creating duplicates.
  ``freq`` is part of the key because the monthly monetary feed also contains
  annual ("yyyy-00") year-end rows that can share a date with a monthly row.
* ``ingest_runs`` records every load (how many rows were inserted vs updated)
  so runs are auditable.
* ``metric_meta`` caches the human label / unit / category for the dashboard.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

from .config import db_path
from .datasets import DATASETS

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    dataset TEXT NOT NULL,
    metric  TEXT NOT NULL,
    freq    TEXT NOT NULL,
    date    TEXT NOT NULL,
    value   REAL NOT NULL,
    unit    TEXT,
    label   TEXT,
    category TEXT,
    PRIMARY KEY (dataset, metric, freq, date)
);

CREATE INDEX IF NOT EXISTS idx_obs_dataset_metric
    ON observations (dataset, metric, freq);
CREATE INDEX IF NOT EXISTS idx_obs_date ON observations (date);

CREATE TABLE IF NOT EXISTS ingest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    dataset TEXT NOT NULL,
    rows_seen INTEGER NOT NULL,
    rows_inserted INTEGER NOT NULL,
    rows_updated INTEGER NOT NULL,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_meta (
    dataset TEXT NOT NULL,
    metric  TEXT NOT NULL,
    label   TEXT,
    unit    TEXT,
    category TEXT,
    hard_min REAL,
    hard_max REAL,
    PRIMARY KEY (dataset, metric)
);
"""


def connect(cfg: dict) -> sqlite3.Connection:
    path = db_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def refresh_meta(conn: sqlite3.Connection) -> None:
    """Populate metric_meta from the dataset registry."""
    rows = []
    for ds_key, spec in DATASETS.items():
        for metric, (label, unit, category, lo, hi) in spec["metrics"].items():
            rows.append((ds_key, metric, label, unit, category, lo, hi))
    conn.executemany(
        """INSERT INTO metric_meta
           (dataset, metric, label, unit, category, hard_min, hard_max)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(dataset, metric) DO UPDATE SET
             label=excluded.label, unit=excluded.unit,
             category=excluded.category, hard_min=excluded.hard_min,
             hard_max=excluded.hard_max""",
        rows,
    )
    conn.commit()


def upsert_rows(conn: sqlite3.Connection, dataset_key: str,
                rows: list[dict], source: str) -> dict:
    """Idempotently load one dataset's tidy rows.

    Returns counts: seen / inserted / updated.
    """
    inserted = updated = 0
    cur = conn.cursor()
    for r in rows:
        existing = cur.execute(
            "SELECT 1 FROM observations WHERE dataset=? AND metric=? AND freq=? AND date=?",
            (r["dataset"], r["metric"], r["freq"], r["date"]),
        ).fetchone()
        cur.execute(
            """INSERT INTO observations
               (dataset, metric, freq, date, value, unit, label, category)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(dataset, metric, freq, date) DO UPDATE SET
                 value=excluded.value,
                 unit=excluded.unit, label=excluded.label,
                 category=excluded.category""",
            (r["dataset"], r["metric"], r["freq"], r["date"], r["value"],
             r["unit"], r["label"], r["category"]),
        )
        if existing is None:
            inserted += 1
        else:
            updated += 1
    conn.execute(
        """INSERT INTO ingest_runs
           (run_at, dataset, rows_seen, rows_inserted, rows_updated, source)
           VALUES (?,?,?,?,?,?)""",
        (dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
         dataset_key, len(rows), inserted, updated, source),
    )
    conn.commit()
    return {"seen": len(rows), "inserted": inserted, "updated": updated}
