# HKMA Financial Data Automation & Monitoring

A reproducible, end-to-end data pipeline that pulls **official Hong Kong
Monetary Authority (HKMA) open data** on exchange rates, interest rates,
interbank liquidity and monetary statistics, cleans and stores it in SQLite,
runs data-quality checks, and serves it in an interactive dashboard and a
self-contained HTML report.

The core pipeline uses **only the Python standard library** (no `pandas`,
`requests` or `pip install` needed to fetch, clean, store, quality-check and
report). The optional interactive Streamlit dashboard needs the two packages
in `requirements.txt`.

> Built as a learning / portfolio project for a financial-data role. It
> describes real data, not fabricated outcomes, and is not investment advice.

## What it does

1. **Fetch** three HKMA feeds with retry/backoff, envelope validation, and
   pagination. Every raw page is cached as JSON so a run is auditable and can
   be replayed offline (`--offline`).
2. **Clean** the wide API rows into tidy long-form rows, handling sign-prefixed
   numbers, thousands separators, missing values, date formats and the feed's
   mixed monthly/annual convention.
3. **Store** in SQLite with a composite primary key, so re-running the loader
   is **idempotent** (it upserts; it never creates duplicates).
4. **Quality-check** for duplicate keys, hard plausibility violations,
   schedule gaps, robust MAD outliers and large rate moves. Findings are
   flagged, never deleted.
5. **Visualise** in a Streamlit dashboard (metric + date-range picker, trend,
   stats, quality) and in a zero-dependency offline HTML report with inline
   SVG charts.

## Data flow

```text
HKMA public API  ──fetch (urllib, retries)──►  data/raw/*.json   (raw cache)
                                                      │
                                            transform (clean/melt)
                                                      ▼
                                          data/processed/hkma.db  (SQLite)
                                                      │
                     ┌────────────────────────────────┼───────────────────────┐
                     ▼                                ▼                        ▼
          SQL queries (sql/)             data-quality checks        Streamlit dashboard
          + HTML report (SVG)             (quality_report.json)     app/streamlit_app.py
```

## Data sources

| Dataset | Endpoint | Frequency | Docs |
|---|---|---|---|
| Exchange rates + EERI | `monthly-statistical-bulletin/er-ir/er-eeri-daily` | daily | [link](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/) |
| Interbank liquidity | `daily-monetary-statistics/daily-figures-interbank-liquidity` | daily | [link](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/daily-monetary-statistics/daily-figures-interbank-liquidity/) |
| Monetary statistics | `monthly-statistical-bulletin/financial/monetary-statistics` | monthly + annual | [link](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/financial/monetary-statistics/) |

Full field definitions, units, date ranges and threshold rationale are in
[`docs/DATA_CATALOG.md`](docs/DATA_CATALOG.md).

## Quick start (on a brand-new computer)

Requires Python 3.9+. Tested on Python 3.9 and 3.14.

```bash
# 1. Get the project
git clone <your-repo-url> hkma-financial-monitor
cd hkma-financial-monitor

# 2. (Optional) reproduce from the bundled raw cache with NO install:
python3 scripts/run_pipeline.py --offline
python3 scripts/run_quality.py
python3 scripts/build_html_report.py
#    then open docs/report.html in a browser
```

### Pull fresh data from the live API (needs internet)

```bash
python3 scripts/run_pipeline.py        # no --offline: pages through the live API
python3 scripts/run_quality.py
python3 scripts/build_html_report.py
```

Re-run `run_pipeline.py` as often as you like; the primary key prevents
duplicates (the second run reports `inserted=0`).

### Interactive dashboard (optional)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Pick a dataset, metric, frequency and date range; view the trend, summary
statistics and the data-quality tab.

### Tests

```bash
python3 -m unittest discover -s tests -v
```

## Configuration

Copy `config.example.json` to `config.json` and edit as needed. The pipeline
falls back to the example file if `config.json` does not exist.

```json
{
  "base_url": "https://api.hkma.gov.hk/public/market-data-and-statistics",
  "page_size": 100,
  "request_timeout_seconds": 30,
  "max_retries": 3,
  "retry_backoff_seconds": 2,
  "paths": { "raw_dir": "data/raw", "database": "data/processed/hkma.db" }
}
```

The HKMA API needs **no key or token**, so there are no secrets to manage.

## Project layout

```text
hkma-financial-monitor/
├── config.example.json          # configuration template (no secrets)
├── requirements.txt             # ONLY needed for the Streamlit dashboard
├── src/hkma_monitor/
│   ├── config.py                # config loading + path helpers
│   ├── datasets.py              # dataset registry: endpoints, fields, units, bounds
│   ├── fetch.py                 # HTTP fetch with retries + raw JSON cache
│   ├── transform.py             # wide -> tidy cleaning, number/date parsing
│   ├── db.py                    # SQLite schema + idempotent upsert
│   ├── pipeline.py              # orchestrates fetch -> transform -> load
│   └── quality.py               # duplicate / bound / gap / MAD / level-shift checks
├── scripts/
│   ├── run_pipeline.py          # ETL entry point (--offline)
│   ├── run_quality.py           # quality checks -> data/processed/quality_report.json
│   └── build_html_report.py     # self-contained docs/report.html (inline SVG)
├── app/streamlit_app.py         # interactive dashboard
├── sql/                         # hand-written, genuinely useful SQL queries
├── tests/                       # unittest (no framework to install)
├── data/
│   ├── raw/                     # raw API JSON pages (cached; public data)
│   └── processed/               # generated SQLite DB + quality report
└── docs/
    ├── DATA_CATALOG.md
    ├── PROJECT_SUMMARY.md
    ├── report.html              # generated
    └── screenshots/report_full.png
```

## Data model

Everything is stored in one tidy table, one row per
`(dataset, metric, freq, date)`:

| column | meaning |
|---|---|
| `dataset` | `fx_daily`, `interbank_daily`, `monetary_monthly` |
| `metric` | the field name (e.g. `hibor_overnight`) |
| `freq` | `daily`, `monthly` or `annual` |
| `date` | normalised ISO `YYYY-MM-DD` (monthly = first day; annual = year-end) |
| `value` | numeric value as `REAL` |
| `unit`, `label`, `category` | human-readable metadata |

`ingest_runs` audits every load (rows seen/inserted/updated); `metric_meta`
holds labels, units and the hard bounds.

## Example output

See [`docs/screenshots/report_full.png`](docs/screenshots/report_full.png) and
[`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md). On the bundled cache the
quality run reports **0 duplicates** and **0 hard-bound violations**; the
weekday schedule gaps coincide with Hong Kong public holidays.

## Reproducibility notes

- The same code runs live or offline; the offline cache is real API output
  captured at the time of the run (`ingest_runs.source` records which).
- The daily bundled windows cover ~8–9 months of 2026 and the monetary feed's
  long-horizon series are five annual points. To load more history, run the
  live pipeline; the code pages through all results.
- Numbers and observations in the report are derived from the database by
  SQL/Python; nothing is hand-entered.

## Limitations and disclaimer

Short windows, publication lag and the difference between association and
causation are documented in `docs/DATA_CATALOG.md`. This project is for
educational and portfolio purposes and is **not investment advice**.

## License

MIT (or your preference). Data © Hong Kong Monetary Authority, used under the
terms of its open data service.
