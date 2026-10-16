#!/usr/bin/env python3
"""Run the full ETL pipeline.

Usage:
    python scripts/run_pipeline.py                # live API (needs internet)
    python scripts/run_pipeline.py --offline      # replay data/raw/*.json
    python scripts/run_pipeline.py --offline --datasets fx_daily
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from a fresh clone without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hkma_monitor.pipeline import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="HKMA data pipeline")
    parser.add_argument("--offline", action="store_true",
                        help="Use cached JSON in data/raw instead of the network")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--datasets", nargs="*", default=None,
                        help="Subset of dataset keys to run")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        summary = run(args.config, offline=args.offline, datasets=args.datasets)
    except Exception as exc:  # noqa: BLE001 - surface a clear CLI error
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        return 1

    print("\n=== Load summary (idempotent upsert) ===")
    for key, counts in summary.items():
        print(f"{key:20s} seen={counts['seen']:6d} "
              f"inserted={counts['inserted']:6d} updated={counts['updated']:6d}")
    print("\nRe-run the same command to confirm inserted=0 (no duplicates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
