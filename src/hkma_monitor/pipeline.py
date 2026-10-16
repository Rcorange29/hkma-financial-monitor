"""End-to-end pipeline orchestration: fetch -> transform -> load."""
from __future__ import annotations

import logging

from . import db as dbmod
from . import fetch as fetchmod
from . import transform as transformmod
from .config import load_config

log = logging.getLogger(__name__)


def run(config_path: str | None = None, *, offline: bool = False,
        datasets: list[str] | None = None) -> dict:
    cfg = load_config(config_path)
    chosen = datasets or cfg["datasets"]
    source = "offline-cache" if offline else "live-api"

    conn = dbmod.connect(cfg)
    dbmod.refresh_meta(conn)
    summary = {}
    try:
        for key in chosen:
            log.info("=== %s (%s) ===", key, source)
            raw = fetchmod.fetch_dataset(cfg, key, offline=offline)
            rows = transformmod.transform_dataset(key, raw)
            summary[key] = dbmod.upsert_rows(conn, key, rows, source)
    finally:
        conn.close()
    return summary
