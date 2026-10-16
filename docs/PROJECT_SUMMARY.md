# Project Summary — HKMA Financial Data Automation & Monitoring

**What it is.** A reproducible pipeline that automatically collects official
Hong Kong Monetary Authority (HKMA) open data — daily exchange rates, the
effective exchange rate index, interbank liquidity (Aggregate Balance, HIBOR,
the policy Base Rate, CU band) and monthly monetary statistics (monetary base,
M1/M2/M3, deposit and bond yields) — then cleans it, loads it into SQLite,
data-quality checks it, and presents it in an interactive dashboard and a
self-contained HTML report.

**Engineering highlights.**
- **No fragile dependencies for the core pipeline** — fetching, cleaning,
  storage, quality checks and the HTML report use only the Python standard
  library, so the project runs identically on a fresh machine; Streamlit and
  pandas are used only for the optional dashboard.
- **Idempotent by design.** A composite primary key with an upsert guarantees
  that re-running the load produces no duplicate rows (verified: second run
  reports `inserted = 0`).
- **Robust to real-world messiness.** Handles retries with backoff, HTTP
  errors, empty/`null` values, sign-prefixed and thousands-separated numbers,
  varying date formats, and the monetary feed's mixed monthly/annual
  (`YYYY-00`) convention.
- **Raw-to-report auditability.** Every raw API page is cached as JSON and
  every ingest is logged (`ingest_runs`), so any number can be traced back to
  the source response.
- **Quality that does not destroy data.** Duplicate, hard-bound, schedule-gap,
  robust MAD outlier and rate-level-shift checks flag issues for review;
  nothing is auto-deleted. Thresholds are derived from the Linked Exchange Rate
  design (7.75–7.85 CU band) and observed magnitudes and are documented.

**Data-supported observations (with ranges and limits).**
1. Over 2026-02-23 → 2026-09-30 (180 daily points), USD/HKD ranged 7.8110–
   7.8485 (mean 7.8375), staying in the weak half of the 7.75–7.85 band
   without touching the 7.85 undertaking.
2. Over 2026-01-23 → 2026-10-16, overnight HIBOR ranged 1.10%–4.00% while the
   1-month fixing ranged only 1.95%–3.02%; all seven same-day moves of at least
   1 percentage point occurred in the overnight rate around month-/quarter-end.
3. Year-end annual values show 3-month HIBOR rising from 0.26% (2021) to 5.15%
   (2023) and easing to 2.93% (2025), while total M2 rose from HK$16.27tn to
   HK$20.60tn; in the 2026 daily window the Base Rate moved from 4.00% to
   4.25% on 2026-09-17. These are associations, not causal claims.

**Limitations.** Bundled daily windows are ~8–9 months of 2026; the long
horizon uses five annual points; the latest month's M1/M2/M3 are unpublished
(`null`). Findings reflect only the selected HKMA series and are not
investment advice.

**Tech stack:** Python (standard library: `urllib`, `sqlite3`, `json`,
`statistics`), SQL, Streamlit, pandas, inline SVG; tested with `unittest`.
