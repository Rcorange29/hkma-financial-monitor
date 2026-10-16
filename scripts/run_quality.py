#!/usr/bin/env python3
"""Run data-quality checks and print/save a report.

Usage:
    python scripts/run_quality.py
    python scripts/run_quality.py --config config.json
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hkma_monitor import quality as q
from hkma_monitor.config import load_config


def _print_section(title: str, rows: list[dict], limit: int = 12) -> None:
    print(f"\n## {title}: {len(rows)}")
    for r in rows[:limit]:
        print("  ", r)
    if len(rows) > limit:
        print(f"   ... {len(rows) - limit} more (see quality_report.json)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    cfg = load_config(args.config)
    conn = q.open_db(cfg)
    try:
        report = q.run_report(conn)
    finally:
        conn.close()

    out = q.save_report(report, cfg)

    print("=== Data quality summary ===")
    for k, v in report["summary"].items():
        print(f"  {k:30s} {v}")
    _print_section("Duplicate primary keys", report["duplicates"])
    _print_section("Hard-bound violations", report["hard_bound_violations"])
    _print_section("Series with schedule gaps", report["schedule_gaps"], limit=6)
    _print_section("MAD robust outliers", report["mad_outliers"])
    _print_section("Large rate level shifts", report["rate_level_shifts"])

    print(f"\nFull report written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
