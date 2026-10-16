"""
Unit tests for the ETL and quality layers.

Standard-library unittest only, so no test framework to install:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hkma_monitor import db as dbmod          # noqa: E402
from hkma_monitor import quality as qmod      # noqa: E402
from hkma_monitor.transform import parse_number, parse_period, transform_dataset  # noqa: E402


class TestParseNumber(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(parse_number(7.85), 7.85)
        self.assertEqual(parse_number(0), 0.0)
        self.assertEqual(parse_number(-40), -40.0)

    def test_strings(self):
        self.assertEqual(parse_number("1,234.50"), 1234.50)
        self.assertEqual(parse_number("+0"), 0.0)
        self.assertEqual(parse_number("-40"), -40.0)
        self.assertEqual(parse_number(" 5.25 "), 5.25)

    def test_missing(self):
        for token in (None, "", "N.A.", "-", "—", "null", "."):
            self.assertIsNone(parse_number(token))

    def test_garbage_is_missing_not_crash(self):
        self.assertIsNone(parse_number("not-a-number"))


class TestParsePeriod(unittest.TestCase):
    def test_daily(self):
        self.assertEqual(parse_period("2026-09-16", "%Y-%m-%d"),
                         ("2026-09-16", "daily"))

    def test_monthly(self):
        self.assertEqual(parse_period("2026-09", "%Y-%m"),
                         ("2026-09-01", "monthly"))

    def test_annual_zero_month_convention(self):
        # The API spells year-end annual rows as "yyyy-00".
        self.assertEqual(parse_period("2025-00", "%Y-%m"),
                         ("2025-12-01", "annual"))

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            parse_period("not-a-date", "%Y-%m-%d")


class TestTransform(unittest.TestCase):
    def test_monetary_melt_and_nulls(self):
        records = [{
            "end_of_month": "2026-09",
            "monetary_base_total": 2090204,
            "m2_total": None,          # publication lag -> missing row
            "hibor_fixing_3m": 3.24167,
        }]
        rows = transform_dataset("monetary_monthly", records)
        metrics = {r["metric"] for r in rows}
        self.assertIn("monetary_base_total", metrics)
        self.assertIn("hibor_fixing_3m", metrics)
        self.assertNotIn("m2_total", metrics)  # null becomes a missing row
        self.assertTrue(all(r["freq"] == "monthly" for r in rows))
        self.assertTrue(all(r["date"] == "2026-09-01" for r in rows))

    def test_annual_rows_get_annual_freq(self):
        rows = transform_dataset("monetary_monthly", [{
            "end_of_month": "2023-00", "m2_total": 17195266.442,
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["freq"], "annual")
        self.assertEqual(rows[0]["date"], "2023-12-01")

    def test_missing_date_column_raises(self):
        with self.assertRaises(ValueError):
            transform_dataset("fx_daily", [{"usd": 7.84}])


class TestDatabaseIdempotency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = {"paths": {"database": str(Path(self.tmp.name) / "t.db")}}
        self.conn = dbmod.connect(self.cfg)
        dbmod.refresh_meta(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _row(self, date, value, freq="daily"):
        return {"dataset": "fx_daily", "metric": "usd", "freq": freq,
                "date": date, "value": value, "unit": "HKD per 1 USD",
                "label": "USD/HKD", "category": "exchange_rate"}

    def test_insert_then_idempotent(self):
        rows = [self._row("2026-09-29", 7.842), self._row("2026-09-30", 7.847)]
        first = dbmod.upsert_rows(self.conn, "fx_daily", rows, "test")
        self.assertEqual(first["inserted"], 2)
        self.assertEqual(first["updated"], 0)

        # Same rows again: nothing new inserted, everything updated.
        second = dbmod.upsert_rows(self.conn, "fx_daily", rows, "test")
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["updated"], 2)

        n = self.conn.execute(
            "SELECT COUNT(*) FROM observations WHERE dataset='fx_daily'").fetchone()[0]
        self.assertEqual(n, 2)

    def test_annual_and_monthly_can_share_date(self):
        rows = [self._row("2025-12-01", 1.0, "monthly"),
                self._row("2025-12-01", 2.0, "annual")]
        res = dbmod.upsert_rows(self.conn, "fx_daily", rows, "test")
        self.assertEqual(res["inserted"], 2)
        self.assertEqual(qmod.check_duplicates(self.conn), [])

    def test_hard_bound_flags(self):
        # USD/HKD hard bounds are 7.60..7.95; 7.99 is implausible.
        rows = [self._row("2026-09-30", 7.99)]
        dbmod.upsert_rows(self.conn, "fx_daily", rows, "test")
        violations = qmod.check_hard_bounds(self.conn)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["metric"], "usd")


class TestExpectedGrids(unittest.TestCase):
    def test_daily_grid_is_weekdays_only(self):
        import datetime as dt
        days = qmod._expected_daily_dates(dt.date(2026, 9, 14),
                                          dt.date(2026, 9, 20))
        self.assertEqual(len(days), 5)          # Mon-Fri only
        self.assertTrue(all(d.weekday() < 5 for d in days))

    def test_monthly_grid(self):
        import datetime as dt
        months = qmod._expected_monthly_dates(dt.date(2026, 1, 1),
                                              dt.date(2026, 3, 1))
        self.assertEqual([d.isoformat() for d in months],
                         ["2026-01-01", "2026-02-01", "2026-03-01"])


if __name__ == "__main__":
    unittest.main()
